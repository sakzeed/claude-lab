# บทที่ 3: agent loop — หัวใจของ Claude Code

บทที่ 2 เห็นแล้วว่า model ขอ tool ได้ทีละครั้ง **agent** คือการเอาสิ่งนั้นมาวนลูป: ให้ model ขอ tool → รัน → ส่งผลกลับ → ให้ model ตัดสินใจต่อ วนไปจนกว่า model จะบอกว่าเสร็จ ทั้งหมดนี้คือสิ่งที่ Claude Code ทำทุกครั้งที่คุณพิมพ์คำสั่ง

บทนี้อ่านลูปที่เราเขียนเอง (`labs/mini_agent/agent.py`) แล้วเทียบกับลูปจริงของ Claude ที่ดูผ่าน `stream-json`

---

## 3.1 ลูปทั้งหมดในไม่ถึง 20 บรรทัด

```python
def run_agent(model, tools: list[Tool], prompt: str, max_turns: int = 10, on_event=None) -> AgentResult:
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
```

| ขั้น | เกิดอะไรขึ้น |
|---|---|
| 1. think | ส่ง **ประวัติทั้งหมด** + รายการ tool ให้ model (จำบทที่ 1 ได้ไหม — model ไม่จำ เราจึงต้องส่ง `messages` ทั้งก้อนทุกรอบ) |
| 2. act | ถ้า model ขอ tool ก็รันทุกตัวที่ขอ (model ขอหลายตัวในรอบเดียวได้) |
| 3. observe | ต่อผลเข้า `messages` ในฐานะ user แล้ววนกลับไปข้อ 1 |
| 4. done | model ตอบโดยไม่ขอ tool (`stop_reason == "end_turn"`) → จบ |

สองสิ่งที่ทำให้ลูปปลอดภัย:

- **`max_turns`** — ถ้า model ขอ tool ไม่หยุด (เช่น ติดวน) ลูปจะหยุดเองและบอกว่าหยุดเพราะ `max_turns` ไม่ใช่เพราะเสร็จ (`test_max_turns`)
- **error เป็นผลลัพธ์** — tool พังแล้วลูปเดินต่อ (บทที่ 2)

`messages` โตทุกรอบ: รอบที่ 3 ส่งข้อความ 5 ชิ้น รอบที่ 10 ส่ง 19 ชิ้น — นี่คือเหตุผลที่งานยาวกิน context เร็ว

## 3.2 ดูลูปจริงของ Claude: `stream-json`

`--output-format stream-json --verbose` ทำให้ `claude -p` พิมพ์ทุก event ออกมาเป็น JSON บรรทัดละหนึ่ง event ทันทีที่เกิด ทดลองให้ Claude นับบรรทัดในไฟล์ โดยอนุญาตแค่ `Read` กับ `Bash(wc *)`:

```sh
$ printf 'line one\nline two\nline three\nline four\nline five\n' > notes.txt
$ claude -p "How many lines are in notes.txt? Use a tool to check, then answer in one short sentence." \
    --output-format stream-json --verbose --max-turns 3 \
    --tools "Read,Bash" --allowedTools "Read" "Bash(wc *)" --permission-mode dontAsk \
    --strict-mcp-config --setting-sources project --disable-slash-commands --no-session-persistence \
    > count-lines.jsonl
```

ได้ 10 บรรทัด output ดิบมีข้อมูลบัญชี (rate limit, path, session id) จึงผ่าน `labs/trace/redact.py` ก่อน ซึ่งเก็บเฉพาะ field ที่ใช้สอน (whitelist) ผลอยู่ที่ `labs/fixtures/count-lines.jsonl`:

```json
{"type": "system", "subtype": "init", "cwd": "<cwd>", "model": "<model>", "tools": ["Bash", "Read"], "permissionMode": "dontAsk", "claude_code_version": "2.1.325"}
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_0136UJhEP8i3cBoZuSSp5JcE", "name": "Bash", "input": {"command": "wc -l notes.txt", "description": "Count lines in notes.txt"}}]}}
{"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_0136UJhEP8i3cBoZuSSp5JcE", "content": "5 notes.txt", "is_error": false}]}}
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "thinking"}]}}
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "`notes.txt` has 5 lines."}]}}
{"type": "result", "subtype": "success", "num_turns": 2, "stop_reason": "end_turn", "result": "`notes.txt` has 5 lines."}
```

(ย่อเพื่อให้อ่านง่าย: ตัด field `usage`, `agents` ใน init, `is_error` กับ `duration_ms` ใน result และ event `system` ที่เป็นแค่สถานะ — ไฟล์เต็มอยู่ใน fixture)

รูปร่าง **เหมือนกับ mini_agent ทุกอย่าง**: `tool_use` จาก assistant → `tool_result` จาก user → assistant ตอบ → จบ

## 3.3 อ่านง่ายขึ้นด้วย `labs/trace`

`labs/trace/trace.py` แปลง stream-json เป็นลำดับขั้น — ใช้ต่อ pipe ได้ตรง ๆ หรืออ่านจาก fixture:

```sh
$ python3 -m labs.trace < labs/fixtures/count-lines.jsonl
 1. init        tools=Bash,Read
 2. tool_use    Bash {"command": "wc -l notes.txt", "description": "Count lines in notes.txt"}
 3. tool_result 5 notes.txt
 4. thinking    (hidden)
 5. text        `notes.txt` has 5 lines.
 6. result      turns=2 in=4+cache11413 out=134 → `notes.txt` has 5 lines.
```

สิ่งที่เห็นจากเครื่องจริง:

- **model เลือก tool เอง** — มีทั้ง `Read` และ `Bash` ให้ใช้ มันเลือก `wc -l` เพราะงานนี้ใช้คำสั่งเดียวจบ
- **`thinking`** — model "คิด" ก่อนตอบ แต่ข้อความถูกซ่อน (และ redact ไม่เก็บไว้)
- **`num_turns: 2`** — นับรอบที่เรียก model (ขอ tool 1 รอบ + ตอบ 1 รอบ) ตรงกับ `turns` ของ mini_agent
- input รวม cache ราว 11,413 token สำหรับงานนับบรรทัด — ส่วนใหญ่คือ system prompt และคำอธิบาย tool ที่ถูกส่งซ้ำทั้งสองรอบ

!!! note "Claude Code ทำอะไรมากกว่า mini_agent"
    ลูปเหมือนกัน แต่ Claude Code เพิ่ม: system prompt ยาว, ระบบ permission ถามก่อนรัน (`--permission-mode`, `--allowedTools`), compaction เมื่อ context ใกล้เต็ม, การรัน tool หลายตัวพร้อมกัน และ event `system` ที่รายงานสถานะ (`task_summary`, `post_turn_summary`) — ส่วนที่เหลือของบทเรียนจะเจอทีละอย่าง

## 3.4 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. เขียน `ScriptedModel` ที่ขอ tool 2 ตัวใน reply เดียว (`calculator` และ `count_lines`) แล้วดูว่า `messages` รอบถัดไปมี `tool_result` กี่ block
2. รัน `claude -p` แบบในหัวข้อ 3.2 แต่ตัด `"Bash(wc *)"` ออกจาก `--allowedTools` แล้วดูด้วย `python3 -m labs.trace` ว่า model ทำอะไรแทน และ `tool_result` มี `(error)` หรือไม่
3. เพิ่ม `print(len(messages))` ก่อน `model.respond` ใน `run_agent` แล้วรัน `python3 -m labs.mini_agent` ดูว่า `messages` โตแบบไหน

### เช็คความเข้าใจ

1. ลูปรู้ได้อย่างไรว่า "เสร็จแล้ว" และถ้า model ไม่เคยหยุดขอ tool จะเกิดอะไรขึ้นกับ mini_agent และกับ `claude -p --max-turns 3`
2. ทำไม input token ของงานที่มี 2 turn ถึงเยอะกว่างานที่มี 1 turn หลายเท่า ทั้งที่คำถามสั้นเท่ากัน

## สรุปบทที่ 3

- agent = ลูป think → act → observe จนกว่า model จะตอบโดยไม่ขอ tool
- ทุกรอบส่งประวัติทั้งหมดซ้ำ `messages` จึงโตเรื่อย ๆ และ `max_turns` กันลูปไม่รู้จบ
- `stream-json` เผยลูปจริงของ Claude Code เป็น event ทีละบรรทัด — รูปร่างเดียวกับ mini_agent
- output ดิบมีข้อมูลบัญชี ต้อง redact แบบ whitelist ก่อนเผยแพร่
