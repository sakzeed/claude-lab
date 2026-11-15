#!/usr/bin/env python3
"""PreToolUse hook: block `rm -rf`, log every Bash call.

Claude Code runs this before the tool, with the event as JSON on stdin.
Exit 0 = allow. Exit 2 = block; stderr is shown to Claude as the reason.
A hook is plain code: it runs every time, the model cannot skip it.

The block check runs first and logging can never stop it: a guardrail that
fails open when the disk is full is not a guardrail.
"""
import datetime
import json
import pathlib
import re
import sys

# rm with both -r/-R and -f in one flag group, in any order: -rf -fr -Rf -rfv ...
RM_RF = re.compile(r"\brm\s+-(?=[a-zA-Z]*[rR])(?=[a-zA-Z]*f)[a-zA-Z]+")


def blocked(tool: str, tool_input: dict) -> bool:
    command = tool_input.get("command", "") if tool == "Bash" else ""
    return isinstance(command, str) and bool(RM_RF.search(command))


def log(tool: str, tool_input: dict) -> None:
    try:
        log_dir = pathlib.Path.home() / ".claude-lab"
        log_dir.mkdir(exist_ok=True)
        entry = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "tool": tool, "input": tool_input}
        with open(log_dir / "tool-log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"zero-to-agent hook: could not write log: {exc}", file=sys.stderr)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # never block on input we do not understand
    if not isinstance(event, dict):
        return 0
    tool = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if blocked(tool, tool_input):
        log(tool, tool_input)
        print("zero-to-agent hook: blocked `rm -rf` — delete files one by one or ask the user", file=sys.stderr)
        return 2
    log(tool, tool_input)
    return 0


if __name__ == "__main__":
    sys.exit(main())
