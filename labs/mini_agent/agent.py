"""The agent loop, small enough to read in one sitting.

A "model" here is anything with respond(messages, tools) -> reply, where a
reply looks like a Claude Messages API response:

    {"stop_reason": "tool_use" | "end_turn",
     "content": [{"type": "text", "text": ...},
                 {"type": "tool_use", "id": ..., "name": ..., "input": {...}}]}

The model never runs anything. It only *asks*; run_agent does the work and
sends the result back as a "tool_result" block in the next user message.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict  # JSON Schema the model uses to build "input"
    run: Callable[[dict], str]

    def schema(self) -> dict:
        """What the model sees: name, description, input_schema — never the code."""
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


class ScriptedModel:
    """A fake model that returns pre-written replies in order.

    It does not read the messages. That is the point: everything "smart" is
    in the replies, so you can watch the loop itself without paying for an LLM.
    """

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.calls = 0

    def respond(self, messages: list[dict], tools: list[dict]) -> dict:
        if self.calls >= len(self.replies):
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "(script ended)"}]}
        reply = self.replies[self.calls]
        self.calls += 1
        return reply


@dataclass
class AgentResult:
    messages: list[dict]
    final_text: str
    turns: int
    stopped: str  # "end_turn" or "max_turns"


def _run_tool(tools: dict[str, Tool], block: dict) -> dict:
    """Run one tool_use block. Errors become results the model can read."""
    tool = tools.get(block["name"])
    if tool is None:
        content, is_error = f"unknown tool: {block['name']}", True
    else:
        try:
            content, is_error = tool.run(block.get("input", {})), False
        except Exception as exc:  # the model should see the failure, not crash the loop
            content, is_error = f"{type(exc).__name__}: {exc}", True
    return {"type": "tool_result", "tool_use_id": block["id"], "content": content, "is_error": is_error}


def run_agent(model, tools: list[Tool], prompt: str, max_turns: int = 10, on_event=None) -> AgentResult:
    """Ask the model, run the tools it asks for, repeat until it stops asking."""
    emit = on_event or (lambda kind, data: None)
    by_name = {t.name: t for t in tools}
    schemas = [t.schema() for t in tools]
    messages: list[dict] = [{"role": "user", "content": prompt}]
    final_text = ""

    for turn in range(1, max_turns + 1):
        reply = model.respond(messages, schemas)  # 1. think
        emit("model", reply)
        messages.append({"role": "assistant", "content": reply["content"]})
        final_text = "".join(b["text"] for b in reply["content"] if b["type"] == "text")

        calls = [b for b in reply["content"] if b["type"] == "tool_use"]
        if reply["stop_reason"] != "tool_use" or not calls:
            return AgentResult(messages, final_text, turn, "end_turn")  # 4. done

        results = [_run_tool(by_name, b) for b in calls]  # 2. act
        emit("tool", results)
        messages.append({"role": "user", "content": results})  # 3. observe

    return AgentResult(messages, final_text, max_turns, "max_turns")
