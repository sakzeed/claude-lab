"""Two safe tools: arithmetic and counting lines in a file."""
from __future__ import annotations

import ast
import operator

from .agent import Tool

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: None,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


MAX_EXPONENT = 100


def _pow(base, exponent):
    # 2**10**10 would keep the CPU busy for minutes: a model could hang us.
    if abs(exponent) > MAX_EXPONENT:
        raise ValueError(f"exponent too large (max {MAX_EXPONENT})")
    return base ** exponent


def _eval(node: ast.AST):
    # Walk the syntax tree ourselves and allow only numbers and operators.
    # Never eval(): the expression comes from a model and could be anything.
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
    raise ValueError(f"not allowed in calculator: {ast.dump(node)[:60]}")


def _calculate(args: dict) -> str:
    expr = str(args.get("expression", ""))
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"bad expression: {expr!r}") from exc
    value = _eval(tree)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _count_lines(args: dict) -> str:
    with open(args["path"], encoding="utf-8", errors="replace") as f:
        return str(sum(1 for _ in f))


calculator = Tool(
    name="calculator",
    description="Evaluate an arithmetic expression with + - * / % ** and parentheses.",
    input_schema={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "e.g. 2*(3+4)"}},
        "required": ["expression"],
    },
    run=_calculate,
)

count_lines = Tool(
    name="count_lines",
    description="Count the lines in a text file.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "path to the file"}},
        "required": ["path"],
    },
    run=_count_lines,
)
