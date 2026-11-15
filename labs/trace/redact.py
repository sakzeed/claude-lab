"""Make a stream-json recording safe to publish.

Whitelist, not blacklist: for each event type keep only the fields the
lessons use. New fields that a future Claude Code adds are dropped by
default instead of leaking. Usage:

    python3 -m labs.trace.redact --cwd "$PWD" < raw.jsonl > labs/fixtures/x.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def _usage(u) -> dict | None:
    if not isinstance(u, dict):
        return None
    return {k: u[k] for k in _USAGE_KEYS if k in u}


def _block(b: dict) -> dict | None:
    kind = b.get("type")
    if kind == "text":
        return {"type": "text", "text": b.get("text", "")}
    if kind == "thinking":
        return {"type": "thinking"}  # never publish the thinking text or signature
    if kind == "tool_use":
        return {"type": "tool_use", "id": b.get("id"), "name": b.get("name"), "input": b.get("input", {})}
    if kind == "tool_result":
        return {"type": "tool_result", "tool_use_id": b.get("tool_use_id"),
                "content": b.get("content"), "is_error": b.get("is_error", False)}
    return None


def _message(event: dict) -> dict:
    msg = event.get("message", {})
    content = msg.get("content")
    if isinstance(content, list):
        content = [x for x in (_block(b) for b in content) if x is not None]
    out = {"type": event["type"], "message": {"role": msg.get("role"), "content": content}}
    if event["type"] == "assistant" and _usage(msg.get("usage")):
        out["message"]["usage"] = _usage(msg.get("usage"))
    if event.get("parent_tool_use_id"):
        out["parent_tool_use_id"] = event["parent_tool_use_id"]
    return out


def _keep(event: dict) -> dict | None:
    kind, sub = event.get("type"), event.get("subtype")
    if kind == "system" and sub == "init":
        return {"type": kind, "subtype": sub, "cwd": "<cwd>", "model": "<model>",
                "tools": event.get("tools", []), "agents": event.get("agents", []),
                "permissionMode": event.get("permissionMode"),
                "claude_code_version": event.get("claude_code_version")}
    if kind == "system":
        return {"type": kind, "subtype": sub}
    if kind in ("assistant", "user"):
        return _message(event)
    if kind == "result":
        out = {k: event[k] for k in ("subtype", "is_error", "num_turns", "stop_reason", "duration_ms", "result") if k in event}
        out = {"type": kind, **out}
        if _usage(event.get("usage")):
            out["usage"] = _usage(event["usage"])
        return out
    return None  # rate_limit_event and anything unknown


def _scrub(value, home: str, cwd: str | None):
    if isinstance(value, str):
        if cwd:
            value = value.replace(cwd, "<cwd>")
        return value.replace(home, "~")
    if isinstance(value, list):
        return [_scrub(v, home, cwd) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v, home, cwd) for k, v in value.items()}
    return value


def redact(line: str, home: str, cwd: str | None = None) -> str | None:
    """Return a safe JSON line, or None when the whole event should be dropped."""
    event = json.loads(line)
    kept = _keep(event)
    if kept is None:
        return None
    return json.dumps(_scrub(kept, home, cwd), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cwd", help="working directory of the recorded run (replaced by <cwd>)")
    args = ap.parse_args()
    home = os.path.expanduser("~")
    for line in sys.stdin:
        if line.strip():
            out = redact(line, home, args.cwd)
            if out is not None:
                print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
