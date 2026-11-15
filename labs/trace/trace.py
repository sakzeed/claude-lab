"""Turn `claude -p --output-format stream-json --verbose` into readable steps.

Each line of stream-json is one event. The agent loop shows up as:
init -> assistant(tool_use) -> user(tool_result) -> ... -> assistant(text) -> result
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable


@dataclass
class Step:
    kind: str  # init | thinking | text | tool_use | tool_result | result
    detail: str


def _short(value, limit: int = 100) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _blocks(event: dict) -> list[Step]:
    content = event.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    who = "  [subagent] " if event.get("parent_tool_use_id") else ""
    steps = []
    for b in content:
        kind = b.get("type")
        if kind == "thinking":
            steps.append(Step("thinking", who + "(hidden)"))
        elif kind == "text":
            steps.append(Step("text", who + _short(b.get("text", ""))))
        elif kind == "tool_use":
            steps.append(Step("tool_use", f"{who}{b.get('name')} {_short(b.get('input', {}))}"))
        elif kind == "tool_result":
            flag = " (error)" if b.get("is_error") else ""
            steps.append(Step("tool_result", f"{who}{_short(b.get('content'))}{flag}"))
    return steps


def summarize(lines: Iterable[str]) -> list[Step]:
    steps: list[Step] = []
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            steps.append(Step("init", "tools=" + ",".join(event.get("tools", []))))
        elif kind in ("assistant", "user"):
            steps.extend(_blocks(event))
        elif kind == "result":
            usage = event.get("usage") or {}
            steps.append(Step("result", f"turns={event.get('num_turns')} "
                                        f"in={usage.get('input_tokens', '?')}+cache{usage.get('cache_read_input_tokens', 0) + usage.get('cache_creation_input_tokens', 0)} "
                                        f"out={usage.get('output_tokens', '?')} → {_short(event.get('result', ''))}"))
    return steps
