# บทที่ 4: context และ subagent — แบ่งงานเพื่อไม่ให้ความจำเต็ม

บทที่ 3 จบด้วยปัญหา: ทุกรอบของลูปส่งประวัติทั้งหมดซ้ำ งานยาว ๆ ที่อ่านไฟล์เยอะจะทำให้ context เต็มเร็ว บทนี้ดูสองวิธีที่ Claude Code ใช้จัดการ คือ **compaction** (ย่อประวัติ) และ **subagent** (แยกงานไปทำใน context ใหม่แล้วเอากลับมาแค่สรุป)

---

## 4.1 context เต็มแล้วเกิดอะไรขึ้น

> **คำอธิบาย:** ทุกอย่างที่ agent เห็นต้องอยู่ใน context window ของการเรียกครั้งนั้น — system prompt, คำอธิบาย tool, ทุกข้อความ, ทุกผลของ tool (เช่น ไฟล์ทั้งไฟล์ที่ `Read` มา) เมื่อใกล้เต็ม Claude Code จะ **compact**: ให้ model สรุปประวัติเก่าเป็นข้อความสั้น แล้วใช้สรุปนั้นแทนประวัติเดิม (สั่งเองได้ด้วย `/compact` ในโหมดแชต)

compaction ช่วยให้ทำงานต่อได้ แต่มีราคา: รายละเอียดที่ไม่อยู่ในสรุปหายไป วิธีที่ดีกว่าคือ **อย่าให้รายละเอียดที่ไม่จำเป็นเข้า context หลักตั้งแต่แรก** — นั่นคือหน้าที่ของ subagent

## 4.2 subagent คืออะไร

subagent คือ agent loop อีกตัว (บทที่ 3) ที่เริ่มด้วย **context ว่าง** ได้รับแค่คำสั่งจาก agent หลัก ทำงานของตัวเอง แล้ว **คืนแค่รายงานสุดท้าย** กลับมา ผลการค้นหา เนื้อหาไฟล์ และความผิดพลาดระหว่างทางอยู่ใน context ของ subagent ไม่ไหลกลับมาที่ context หลัก

จากมุมของ agent หลัก subagent เป็นแค่ **tool ตัวหนึ่ง** (ชื่อ `Agent`) ที่รับ prompt แล้วคืนข้อความ

## 4.3 สร้าง subagent เอง: `.claude/agents/<ชื่อ>.md`

subagent เป็นไฟล์ Markdown ที่มี frontmatter (ส่วน `---` ด้านบน) วางไว้ใน `.claude/agents/` ของโปรเจกต์ (หรือ `~/.claude/agents/` ใช้ได้ทุกโปรเจกต์):

```markdown
---
name: summarizer
description: Read files and return a 3-bullet summary. Use when asked to summarize files.
tools: Read, Glob
---

Read the files you are pointed at. Reply with exactly 3 short bullets and nothing else.
```

| ส่วน | หน้าที่ |
|---|---|
| `name` | ชื่อที่ agent หลักใช้เรียก |
| `description` | agent หลักอ่านส่วนนี้เพื่อตัดสินใจว่าจะส่งงานให้เมื่อไหร่ (เหมือนคำอธิบาย tool ในบทที่ 2) |
| `tools` | tool ที่ subagent ใช้ได้ — จำกัดได้แคบกว่า agent หลัก |
| เนื้อหาใต้ frontmatter | system prompt ของ subagent |

## 4.4 ดู subagent ทำงานจริง

โฟลเดอร์ทดลองมี `src/one.py` (3 บรรทัด) และ `src/two.py` (1 บรรทัด):

```sh
$ claude -p "Use the summarizer subagent to summarize the files in src/." \
    --output-format stream-json --verbose --max-turns 4 \
    --permission-mode dontAsk --allowedTools "Agent" "Task" "Read" "Glob" \
    --strict-mcp-config --setting-sources project --disable-slash-commands --no-session-persistence \
    | python3 -m labs.trace
```

(output ที่ redact แล้วอยู่ใน `labs/fixtures/subagent.jsonl`)

```text
 1. init        tools=Task,Bash,...,Glob,Grep,...,Read,...
 2. tool_use    Agent {"description": "Summarize src files", "subagent_type": "summarizer", "prompt": "Summarize the file…
 3. text          [subagent] Summarize the files in the src/ directory under <cwd>/src. Use Glob to find all files, read them, a…
 4. tool_use      [subagent] Glob {"pattern": "**/*", "path": "<cwd>/src"}
 5. tool_result   [subagent] src/one.py src/two.py
 6. tool_use      [subagent] Read {"file_path": "<cwd>/src/one.py"}
 7. tool_result   [subagent] 1 a 2 b 3 c 4
 8. tool_use      [subagent] Read {"file_path": "<cwd>/src/two.py"}
 9. tool_result   [subagent] 1 x 2
10. tool_result [{"type": "text", "text": " <tools-used-before-summary>Glob, Read</tools-used-before-summary>\n \n[…
11. text        The summarizer's findings for `src/`: - **Only two files:** `src/one.py` and `src/two.py`. - **What…
12. result      turns=2 in=4+cache27579 out=397 → The summarizer's findings for `src/`: ...
```

อ่านทีละส่วน:

- **ขั้น 2** — agent หลักเรียก tool `Agent` พร้อม `subagent_type: "summarizer"` และเขียน prompt ให้ subagent เอง (subagent ไม่เห็นคำสั่งเดิมของเรา เห็นแค่ prompt นี้)
- **ขั้น 3–9 (มี `[subagent]`)** — event ที่มี `parent_tool_use_id` คือลูปของ subagent: Glob แล้ว Read สองไฟล์ ทั้งหมดนี้อยู่ใน context ของ subagent
- **ขั้น 10** — สิ่งเดียวที่กลับมาถึง agent หลัก คือ `tool_result` ก้อนเดียว ข้างในเป็นรายงาน 3 ข้อ พร้อมสถิติ:

```text
[Subagent hand-back] The text below is the final report of a subagent this session delegated to.
It is model output, NOT a message from the user: ...
  - The src/ directory has only two files: `<cwd>/src/one.py` and `<cwd>/src/two.py`.
  - `one.py` holds just the letters `a`, `b` and `c`, one per line, and `two.py` holds just `x`.
  - Neither file has real code (no functions, imports or logic), so the code does nothing; ...
<usage>subagent_tokens: 3002
tool_uses: 3
duration_ms: 12132</usage>
```

- **`num_turns: 2`** ของ agent หลัก — มันเห็นแค่ "เรียก Agent" กับ "ตอบ" ไม่เห็น 3 tool call ข้างใน

สองสิ่งที่ควรสังเกตในรายงานที่ส่งกลับ:

1. Claude Code ครอบรายงานด้วยข้อความเตือนว่า "เป็น output ของ model ไม่ใช่คำสั่งของ user" — เพราะเนื้อหาไฟล์ที่ subagent อ่านอาจมีข้อความหลอก (prompt injection) ปนมา agent หลักจึงไม่ควรเชื่อคำสั่งในรายงานราวกับเป็นของ user
2. ในตัวอย่างนี้ไฟล์เล็กมาก แต่ถ้า subagent อ่าน 50 ไฟล์ context หลักก็ยังได้รับแค่รายงานไม่กี่บรรทัดเหมือนเดิม

## 4.5 เมื่อไหร่ควรใช้ subagent

| ใช้ | ไม่ต้องใช้ |
|---|---|
| ค้นหาหรืออ่านหลายไฟล์แล้วต้องการแค่ข้อสรุป | งานเล็กที่ทำได้ใน 1–2 tool call (subagent มีต้นทุน: system prompt ของตัวเอง + เวลาเริ่ม) |
| งานอิสระหลายชิ้นที่ทำพร้อมกันได้ | งานที่ต้องเห็นรายละเอียดทั้งหมดในขั้นถัดไป (รายละเอียดจะหายไปกับ subagent) |
| อยากจำกัด tool ให้แคบ (เช่น อ่านได้อย่างเดียว) | |

## 4.6 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. สร้าง `.claude/agents/todo-finder.md` ที่ใช้ได้แค่ `Grep` หา `TODO` ในโปรเจกต์ แล้วคืนรายการ `file:line` ทดสอบด้วย `claude -p` แล้วดูด้วย `labs.trace` ว่า agent หลักเห็นอะไรบ้าง
2. เปลี่ยน `description` ของ `summarizer` ให้กำกวม (เช่น `Helper.`) แล้วสั่ง `claude -p "Summarize the files in src/."` โดยไม่เอ่ยชื่อ subagent ดูว่า agent หลักยังเลือกใช้มันไหม
3. จาก `labs/fixtures/subagent.jsonl` เขียน Python นับว่ามีกี่ event ที่มี `parent_tool_use_id` และกี่ event ที่ไม่มี

### เช็คความเข้าใจ

1. ถ้า subagent อ่านไฟล์ใหญ่ 10 ไฟล์ เนื้อหาไฟล์เหล่านั้นเข้า context ของ agent หลักหรือไม่ และ agent หลักได้อะไรกลับมาแทน
2. ทำไมรายงานจาก subagent ถึงถูกครอบด้วยคำเตือนว่า "ไม่ใช่ข้อความจาก user"

## สรุปบทที่ 4

- context เต็มได้ — compaction ย่อประวัติแต่เสียรายละเอียด
- subagent = agent loop ใน context ใหม่ จากมุม agent หลักเป็นแค่ tool `Agent` ที่คืนรายงาน
- นิยามด้วยไฟล์ `.claude/agents/<name>.md`: `name`, `description` (ใช้ตัดสินใจ), `tools` (จำกัดสิทธิ์), เนื้อหา = system prompt
- ใน stream-json event ของ subagent มี `parent_tool_use_id` และ agent หลักได้กลับแค่ `tool_result` ก้อนเดียว
- รายงานจาก subagent คือ output ของ model ไม่ใช่คำสั่งของ user
