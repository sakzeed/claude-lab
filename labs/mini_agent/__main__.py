"""python3 -m labs.mini_agent — watch one agent run with a scripted model."""
import json

from .agent import ScriptedModel, run_agent
from .tools import calculator, count_lines

SCRIPT = [
    {"stop_reason": "tool_use", "content": [
        {"type": "text", "text": "ต้องคิดเลขก่อน"},
        {"type": "tool_use", "id": "toolu_1", "name": "calculator", "input": {"expression": "(120+80)*3"}},
    ]},
    {"stop_reason": "tool_use", "content": [
        {"type": "tool_use", "id": "toolu_2", "name": "calculator", "input": {"expression": "600/7"}},
    ]},
    {"stop_reason": "end_turn", "content": [
        {"type": "text", "text": "รวม 600 บาท หาร 7 คนได้คนละประมาณ 85.71 บาท"},
    ]},
]


def show(kind, data):
    if kind == "model":
        print(f"model  ← stop_reason={data['stop_reason']}")
        for block in data["content"]:
            print("         ", json.dumps(block, ensure_ascii=False))
    else:
        for r in data:
            print(f"tool   → {r['tool_use_id']}: {r['content']!r} (is_error={r['is_error']})")


def main():
    prompt = "ข้าว 120 น้ำ 80 สั่ง 3 ชุด หาร 7 คน คนละเท่าไร"
    print(f"user   → {prompt}")
    result = run_agent(ScriptedModel(SCRIPT), [calculator, count_lines], prompt, on_event=show)
    print(f"done: turns={result.turns} stopped={result.stopped}")


if __name__ == "__main__":
    main()
