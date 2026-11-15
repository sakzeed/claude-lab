#!/usr/bin/env python3
"""PreToolUse hook: log every Bash call, block `rm -rf`.

Claude Code runs this before the tool, with the event as JSON on stdin.
Exit 0 = allow. Exit 2 = block; stderr is shown to Claude as the reason.
A hook is plain code: it runs every time, the model cannot skip it.
"""
import datetime
import json
import pathlib
import re
import sys


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # never block on input we do not understand
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}

    log_dir = pathlib.Path.home() / ".claude-lab"
    log_dir.mkdir(exist_ok=True)
    entry = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "tool": tool, "input": tool_input}
    with open(log_dir / "tool-log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    command = tool_input.get("command", "") if tool == "Bash" else ""
    if re.search(r"\brm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)\b", command):
        print("claude-lab hook: blocked `rm -rf` — delete files one by one or ask the user", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
