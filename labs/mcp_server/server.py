#!/usr/bin/env python3
"""claude-lab MCP server: JSON-RPC 2.0 over stdio, standard library only.

The whole protocol for a tools-only server fits in this file:

  client -> {"method": "initialize"}          <- protocolVersion, capabilities
  client -> {"method": "notifications/initialized"}   (no reply: no "id")
  client -> {"method": "tools/list"}          <- name, description, inputSchema
  client -> {"method": "tools/call"}          <- content + isError

One JSON message per line on stdin/stdout. stdout is the protocol channel:
anything else printed there breaks the client, so logs go to stderr.

This file is self-contained on purpose (no imports from the labs package) so
the plugin in labs/plugin/zero-to-agent can ship an exact copy of it.
"""
from __future__ import annotations

import ast
import json
import operator
import os
import sys

SERVER_INFO = {"name": "claude-lab", "version": "0.1.0"}
SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603


def log(message: str) -> None:
    print(f"[claude-lab] {message}", file=sys.stderr, flush=True)


# --- tools (same logic as labs/mini_agent/tools.py) ---------------------------

_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: None}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


MAX_EXPONENT = 100
MAX_RESULT_BITS = 100_000  # about 30,000 decimal digits


def _pow(base, exponent):
    # 2**10**10 would keep the CPU busy for minutes: a model could hang us.
    # Capping the exponent alone is not enough: ((9**99)**99)**99 uses small
    # exponents but builds a number with millions of digits, so also cap the
    # size of an integer result before computing it.
    if abs(exponent) > MAX_EXPONENT:
        raise ValueError(f"exponent too large (max {MAX_EXPONENT})")
    if isinstance(base, int) and isinstance(exponent, int) and exponent > 0 and abs(base) > 1:
        if abs(base).bit_length() * exponent > MAX_RESULT_BITS:
            raise ValueError("result too large")
    return base ** exponent


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            return _pow(left, right)
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / % ** ( ) are allowed")


def calculator(args: dict) -> str:
    try:
        value = _eval(ast.parse(str(args.get("expression", "")), mode="eval"))
    except SyntaxError as exc:
        raise ValueError(f"bad expression: {exc.msg}") from exc
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def count_lines(args: dict) -> str:
    path = args["path"]
    # only regular files: /dev/zero never ends a line, /dev/stdin would read our own input
    if not os.path.isfile(path):
        raise ValueError(f"not a regular file: {path}")
    with open(path, encoding="utf-8", errors="replace") as f:
        return str(sum(1 for _ in f))


TOOLS = {
    "calculator": (calculator, {
        "description": "Evaluate an arithmetic expression with + - * / % ** and parentheses.",
        "inputSchema": {"type": "object",
                        "properties": {"expression": {"type": "string", "description": "e.g. 2*(3+4)"}},
                        "required": ["expression"]},
    }),
    "count_lines": (count_lines, {
        "description": "Count the lines in a text file.",
        "inputSchema": {"type": "object",
                        "properties": {"path": {"type": "string", "description": "path to the file"}},
                        "required": ["path"]},
    }),
}


# --- JSON-RPC ----------------------------------------------------------------

class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _initialize(params: dict) -> dict:
    wanted = params.get("protocolVersion")
    version = wanted if wanted in SUPPORTED else SUPPORTED[0]
    client = params.get("clientInfo", {}).get("name", "?")
    log(f"initialize from {client}, protocol {version}")
    return {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}


def _tools_list(params: dict) -> dict:
    return {"tools": [{"name": name, **meta} for name, (_, meta) in TOOLS.items()]}


def _tools_call(params: dict) -> dict:
    name = params.get("name")
    if name not in TOOLS:
        raise RpcError(INVALID_PARAMS, f"unknown tool: {name}")
    fn, _ = TOOLS[name]
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise RpcError(INVALID_PARAMS, "arguments must be an object")
    try:
        text, is_error = fn(arguments), False
    except Exception as exc:  # a tool failure is a *result* the model can read
        text, is_error = f"{type(exc).__name__}: {exc}", True
    log(f"tools/call {name} -> {'error' if is_error else 'ok'}")
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


METHODS = {
    "initialize": _initialize,
    "ping": lambda params: {},
    "tools/list": _tools_list,
    "tools/call": _tools_call,
}


def handle(msg) -> dict | None:
    """Answer one request. Notifications (no "id") never get a reply."""
    if not isinstance(msg, dict):  # e.g. a JSON-RPC batch [...] — not supported here
        return {"jsonrpc": "2.0", "id": None, "error": {"code": INVALID_REQUEST, "message": "invalid request: expected a JSON object"}}
    is_request = "id" in msg
    method = msg.get("method")
    if not isinstance(method, str):
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": INVALID_REQUEST, "message": "invalid request: missing method"}}
    try:
        if method not in METHODS:
            if not is_request:
                return None  # e.g. notifications/initialized
            raise RpcError(METHOD_NOT_FOUND, f"method not found: {method}")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            raise RpcError(INVALID_PARAMS, "params must be an object")
        result = METHODS[method](params)
    except RpcError as exc:
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:  # a bug in a handler must not kill the server
        log(f"internal error in {method}: {exc!r}")
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": INTERNAL_ERROR, "message": "internal error"}}
    if not is_request:
        return None
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


def _parse(line):
    """Decode and parse one line; raise ValueError if it is not valid JSON."""
    if isinstance(line, bytes):
        line = line.decode("utf-8")  # UnicodeDecodeError is a ValueError
    try:
        return json.loads(line)
    except RecursionError:  # e.g. "[[[[..." nested 200k deep
        raise ValueError("JSON nested too deeply") from None


def serve(stdin=None, stdout=None) -> None:
    # Read raw bytes so invalid UTF-8 becomes a parse error instead of
    # crashing the loop (text-mode stdin raises inside "for line in stdin").
    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else sys.stdout
    log("ready (stdio)")
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = _parse(line)
        except ValueError as exc:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": f"parse error: {exc}"}}
        else:
            reply = handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    serve()
