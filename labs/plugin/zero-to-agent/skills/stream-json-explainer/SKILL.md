---
name: stream-json-explainer
description: Explain a Claude Code stream-json recording (output of claude -p --output-format stream-json --verbose) turn by turn. Use when the user shares or points to a .jsonl trace of a Claude Code run and asks what happened, why a tool was called, or where tokens went.
---

# Explaining a stream-json trace

A stream-json file has one JSON event per line. Read it in order and tell
the story of the agent loop:

1. **init** (`type: system, subtype: init`): which tools and model the run had.
2. For each **assistant** event: say what the model decided — text, or a
   `tool_use` block (name + input). A tool_use means the model *asked*;
   nothing ran yet.
3. For each **user** event with `tool_result`: what the tool returned, and
   whether `is_error` is true.
4. **result**: number of turns, final answer, and token usage.

Present it as a numbered list, one line per step, then a 2–3 line summary
of why the run took the path it did.

If the trace has event types or fields you do not recognize, read
`reference.md` in this skill's folder before guessing.
