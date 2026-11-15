# บทที่ 2: tool use — model "ขอ" โปรแกรม "ทำ"

บทที่ 1 model ทำได้แค่เขียนข้อความ แล้วทำไม Claude Code ถึงอ่านไฟล์ รันคำสั่ง แก้โค้ดได้? คำตอบคือ **tool use**: model ไม่ได้รันอะไรเอง มันเขียนข้อความพิเศษที่แปลว่า "ช่วยรัน tool นี้ด้วย input นี้ให้หน่อย" แล้วโปรแกรมรอบนอกเป็นคนรันจริง

บทนี้เขียนส่วนนั้นเองด้วย Python ล้วน โดยใช้ **model ปลอม** แทน LLM — เพื่อให้เห็นกลไกชัด ๆ และไม่เสียเงิน โค้ดอยู่ที่ `labs/mini_agent/`

---

## 2.1 tool คืออะไรในสายตาของ model

model ไม่เห็นโค้ดของ tool เลย มันเห็นแค่ **ชื่อ คำอธิบาย และ schema ของ input** (เขียนเป็น JSON Schema):

```python
calculator = Tool(
    name="calculator",
    description="Evaluate an arithmetic expression with + - * / % ** and parentheses.",
    input_schema={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "e.g. 2*(3+4)"}},
        "required": ["expression"],
    },
    run=_calculate,  # โค้ดจริง — model ไม่เห็นส่วนนี้
)
```

```python
def schema(self) -> dict:
    """What the model sees: name, description, input_schema — never the code."""
    return {"name": self.name, "description": self.description, "input_schema": self.input_schema}
```

ผลที่ตามมา: **คำอธิบายของ tool คือสิ่งเดียวที่ model ใช้ตัดสินใจว่าจะเรียกเมื่อไหร่และส่งอะไร** ถ้าเขียนคำอธิบายกำกวม model ก็จะเรียกผิด — หลักเดียวกันนี้ใช้กับ MCP (บทที่ 5) และ skill (บทที่ 6)

## 2.2 รูปร่างของ "การขอ"

เมื่อ model อยากใช้ tool มันตอบกลับเป็นข้อความที่มี block ชนิด `tool_use` และ `stop_reason` เป็น `"tool_use"` (รูปแบบเดียวกับ Claude Messages API):

```json
{
  "stop_reason": "tool_use",
  "content": [
    {"type": "text", "text": "ต้องคิดเลขก่อน"},
    {"type": "tool_use", "id": "toolu_1", "name": "calculator",
     "input": {"expression": "(120+80)*3"}}
  ]
}
```

ณ จุดนี้ **ยังไม่มีอะไรถูกรัน** มันเป็นแค่ข้อความ หน้าที่ของโปรแกรมคือ:

1. หา tool ชื่อ `calculator`
2. รันด้วย `input` ที่ model ส่งมา
3. ส่งผลกลับไปเป็น block `tool_result` ที่อ้าง `id` เดิม

```json
{"role": "user", "content": [
  {"type": "tool_result", "tool_use_id": "toolu_1", "content": "600", "is_error": false}
]}
```

สังเกตว่าผลของ tool ถูกส่งกลับในฐานะข้อความจาก **user** — เพราะในบทสนทนามีแค่สองฝ่าย: model (assistant) กับทุกอย่างที่ไม่ใช่ model (user)

## 2.3 model ปลอม

`ScriptedModel` คืนคำตอบที่เขียนไว้ล่วงหน้าตามลำดับ ไม่ได้อ่านข้อความเลย:

```python
class ScriptedModel:
    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.calls = 0

    def respond(self, messages: list[dict], tools: list[dict]) -> dict:
        if self.calls >= len(self.replies):
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "(script ended)"}]}
        reply = self.replies[self.calls]
        self.calls += 1
        return reply
```

ความ "ฉลาด" ทั้งหมดอยู่ใน script ที่เราเขียน — ส่วนที่เหลือ (การรัน tool, การส่งผลกลับ) เป็นโค้ดจริงที่ใช้กับ LLM จริงได้เหมือนกันทุกบรรทัด เพราะ `run_agent` ไม่สนใจว่า `model` เป็นของจริงหรือของปลอม ขอแค่มี `respond(messages, tools)`

## 2.4 รันดู

```sh
$ python3 -m labs.mini_agent
user   → ข้าว 120 น้ำ 80 สั่ง 3 ชุด หาร 7 คน คนละเท่าไร
model  ← stop_reason=tool_use
          {"type": "text", "text": "ต้องคิดเลขก่อน"}
          {"type": "tool_use", "id": "toolu_1", "name": "calculator", "input": {"expression": "(120+80)*3"}}
tool   → toolu_1: '600' (is_error=False)
model  ← stop_reason=tool_use
          {"type": "tool_use", "id": "toolu_2", "name": "calculator", "input": {"expression": "600/7"}}
tool   → toolu_2: '85.71428571428571' (is_error=False)
model  ← stop_reason=end_turn
          {"type": "text", "text": "รวม 600 บาท หาร 7 คนได้คนละประมาณ 85.71 บาท"}
done: turns=3 stopped=end_turn
```

สามรอบ: ขอ tool → ขอ tool อีก → ตอบ (`end_turn`) — การวนแบบนี้คือ **agent loop** ที่บทที่ 3 จะเจาะลึก

## 2.5 เมื่อ tool พัง หรือ model ขอสิ่งที่ไม่มี

model อาจขอ tool ที่ไม่มีอยู่ หรือ tool อาจโยน exception ถ้าปล่อยให้ crash ทั้งโปรแกรมจะพัง วิธีที่ถูกคือ **แปลง error เป็นผลลัพธ์** ให้ model อ่านแล้วตัดสินใจใหม่:

```python
def _run_tool(tools: dict[str, Tool], block: dict) -> dict:
    tool = tools.get(block["name"])
    if tool is None:
        content, is_error = f"unknown tool: {block['name']}", True
    else:
        try:
            content, is_error = tool.run(block.get("input", {})), False
        except Exception as exc:  # the model should see the failure, not crash the loop
            content, is_error = f"{type(exc).__name__}: {exc}", True
    return {"type": "tool_result", "tool_use_id": block["id"], "content": content, "is_error": is_error}
```

test คุมทั้งสองกรณี (`test_unknown_tool_is_error_result`, `test_tool_exception_is_error_result`)

## 2.6 input มาจาก model = input ที่ไว้ใจไม่ได้

`calculator` รับ `expression` จาก model ถ้าเขียนแบบขี้เกียจด้วย `eval(expression)` model (หรือข้อความที่หลอก model) ส่ง `__import__('os').system('...')` มาก็รันคำสั่งอะไรก็ได้บนเครื่อง

`labs/mini_agent/tools.py` จึงแปลง expression เป็น syntax tree ด้วย `ast` แล้วยอมเฉพาะตัวเลขกับเครื่องหมาย:

```python
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
            return _pow(left, right)  # caps the exponent at 100
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise ValueError(f"not allowed in calculator: {ast.dump(node)[:60]}")
```

ไม่ใช่แค่ "รันโค้ดอันตราย" เท่านั้น input ที่ดูปลอดภัยก็ทำร้ายได้: `2**10**10` เป็นแค่ตัวเลข แต่คำนวณนานหลายนาที ทำให้ agent (หรือ MCP server ในบทที่ 5) ค้าง จึงมี `_pow` ที่จำกัดเลขชี้กำลังไว้ที่ 100:

```python
>>> calculator.run({"expression": "2**10**10"})
ValueError: exponent too large (max 100)
```

นี่คือเหตุผลเดียวกับที่ Claude Code ถามก่อนรันคำสั่ง และมีระบบ permission (บทที่ 7 จะเห็นอีกชั้นคือ hook)

## 2.7 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. แก้ `SCRIPT` ใน `labs/mini_agent/__main__.py` ให้ model ขอ `count_lines` กับไฟล์ `README.md` แล้วตอบจำนวนบรรทัด รันดูผล
2. เขียน script ที่ model ขอ tool ชื่อ `weather` (ไม่มีอยู่จริง) แล้วรอบถัดไปตอบขอโทษ ดูว่า `tool_result` ที่ได้มีหน้าตาอย่างไร
3. ลบการตรวจใน `_pow` ชั่วคราวแล้วรัน `timeout 5 python3 -c "from labs.mini_agent.tools import calculator; print(calculator.run({'expression': '2**10**10'}))"` ดูว่าโดน timeout (exit 124) จากนั้นคืนโค้ดเดิม แล้วหา input อื่นที่ยังทำให้ช้าได้แม้มีการจำกัดนี้

### เช็คความเข้าใจ

1. model "รัน" tool เองหรือไม่ ถ้าไม่ แล้วใครรัน และ model รู้ผลได้อย่างไร
2. ทำไม error ของ tool ควรกลับไปหา model ในรูป `tool_result` ที่ `is_error: true` แทนที่จะให้โปรแกรม crash

## สรุปบทที่ 2

- model เห็นแค่ชื่อ คำอธิบาย และ JSON Schema ของ tool — คำอธิบายจึงสำคัญมาก
- `tool_use` คือคำขอ (ยังไม่มีอะไรรัน) ส่วน `tool_result` คือผลที่โปรแกรมส่งกลับในฐานะ user
- model ปลอมพิสูจน์ว่ากลไก tool use เป็นโค้ดธรรมดา ไม่ใช่เวทมนตร์ของ model
- error ต้องกลายเป็นผลลัพธ์ให้ model อ่าน ไม่ใช่ crash
- input จาก model ไว้ใจไม่ได้ — ห้าม `eval`
