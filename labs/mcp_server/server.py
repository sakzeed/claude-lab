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
the plugin in labs/plugin/claude-lab can ship an exact copy of it.
"""
from __future__ import annotations

import ast
import json
import operator
import sys

SERVER_INFO = {"name": "claude-lab", "version": "0.1.0"}
SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]

PARSE_ERROR, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32601, -32602


def log(message: str) -> None:
    print(f"[claude-lab] {message}", file=sys.stderr, flush=True)


# --- tools (same logic as labs/mini_agent/tools.py) ---------------------------

_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
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
    with open(args["path"], encoding="utf-8", errors="replace") as f:
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
    try:
        text, is_error = fn(params.get("arguments") or {}), False
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


def handle(msg: dict) -> dict | None:
    """Answer one request. Notifications (no "id") never get a reply."""
    is_request = "id" in msg
    method = msg.get("method")
    try:
        if method not in METHODS:
            if not is_request:
                return None  # e.g. notifications/initialized
            raise RpcError(METHOD_NOT_FOUND, f"method not found: {method}")
        result = METHODS[method](msg.get("params") or {})
    except RpcError as exc:
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": exc.code, "message": str(exc)}}
    if not is_request:
        return None
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


def serve(stdin=sys.stdin, stdout=sys.stdout) -> None:
    log("ready (stdio)")
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                raise ValueError("not an object")
        except ValueError as exc:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": f"parse error: {exc}"}}
        else:
            reply = handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    serve()
