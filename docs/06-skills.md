# บทที่ 6: SKILL.md — คำสั่งที่โหลดเมื่อจำเป็น

tool (บทที่ 2, 5) ให้ agent **ทำ** อะไรได้เพิ่ม ส่วน **skill** ให้ agent **รู้วิธี** ทำงานบางอย่างได้ดีขึ้น — เป็นคู่มือภาษาคนที่เขียนเป็นไฟล์ `SKILL.md` แล้ว Claude Code โหลดเข้า context เฉพาะตอนที่งานตรงกับ skill นั้น

บทนี้เขียน skill ที่อธิบาย trace แบบ stream-json (ต่อยอดบทที่ 3) อยู่ที่ `labs/plugin/zero-to-agent/skills/stream-json-explainer/`

---

## 6.1 ทำไมไม่ใส่ทุกอย่างไว้ใน system prompt

ทุกอย่างใน context กินพื้นที่และเงิน (บทที่ 1) ถ้ามีคู่มือ 50 เรื่องแล้วใส่ไว้ใน prompt ทั้งหมดทุกครั้ง งานส่วนใหญ่จะแบกคู่มือที่ไม่เกี่ยวไปด้วย skill แก้ด้วยการโหลดเป็นชั้น (**progressive disclosure**):

| ชั้น | อยู่ใน context เมื่อไหร่ | ขนาด |
|---|---|---|
| `name` + `description` (frontmatter) | **ทุกครั้ง** — model ใช้ตัดสินใจว่าจะเรียก skill ไหม | 1–3 บรรทัด |
| เนื้อหา `SKILL.md` | เมื่อ model เรียก skill | สั้น ๆ ไม่กี่สิบบรรทัด |
| ไฟล์ประกอบในโฟลเดอร์ (เช่น `reference.md`) | เมื่อเนื้อหาสั่งให้อ่าน และ model ตัดสินว่าจำเป็น | ยาวได้ |

## 6.2 หน้าตาของ skill

```text
skills/stream-json-explainer/
  SKILL.md        คำสั่งหลัก
  reference.md    ตารางอ้างอิง event ทุกชนิด (อ่านเมื่อจำเป็น)
```

```markdown
---
name: stream-json-explainer
description: Explain a Claude Code stream-json recording (output of claude -p --output-format stream-json --verbose) turn by turn. Use when the user shares or points to a .jsonl trace of a Claude Code run and asks what happened, why a tool was called, or where tokens went.
---

# Explaining a stream-json trace

A stream-json file has one JSON event per line. Read it in order and tell
the story of the agent loop:

1. **init** (`type: system, subtype: init`): which tools and model the run had.
2. For each **assistant** event: say what the model decided ...
3. For each **user** event with `tool_result`: what the tool returned ...
4. **result**: number of turns, final answer, and token usage.

...

If the trace has event types or fields you do not recognize, read
`reference.md` in this skill's folder before guessing.
```

`description` สำคัญที่สุด — มันคือสิ่งเดียวที่ model เห็นก่อนตัดสินใจ จึงต้องบอกทั้ง **ทำอะไร** และ **ใช้เมื่อไหร่** (ประโยค "Use when ...") เหมือนคำอธิบาย tool ในบทที่ 2 และ subagent ในบทที่ 4

ชื่อโฟลเดอร์ต้องตรงกับ `name` (test `test_skill_frontmatter` ตรวจ)

## 6.3 skill ถูกเรียกจริง

skill นี้อยู่ใน plugin `zero-to-agent` (บทที่ 8) จึงโหลดด้วย `--plugin-dir` ให้ Claude อธิบาย `trace.jsonl` (สำเนาของ `labs/fixtures/count-lines.jsonl`) โดยไม่ได้เอ่ยชื่อ skill เลย:

```sh
$ claude -p "What happened in trace.jsonl? Explain the run." \
    --output-format stream-json --verbose --max-turns 4 \
    --plugin-dir ~/github/claude-lab/labs/plugin/zero-to-agent \
    --strict-mcp-config --setting-sources project \
    --permission-mode dontAsk --allowedTools "Skill" "Read" --no-session-persistence \
    | python3 -m labs.trace
 1. init        tools=Task,Bash,...,Read,...,Skill,...
 2. tool_use    Skill {"skill": "zero-to-agent:stream-json-explainer", "args": "trace.jsonl"}
 3. tool_result Launching skill: zero-to-agent:stream-json-explainer
 4. text        Base directory for this skill: ~/github/claude-lab/labs/plugin/zero-to-agent/skills/stream-json-exp…
 5. tool_use    Bash {"command": "wc -l trace.jsonl && cut -c1-1500 trace.jsonl", "description": "Show trace file conten…
 6. tool_result 9 trace.jsonl {"type": "system", "subtype": "init", "cwd": "<cwd>", "model": "<model>", "tools": ["…
 7. thinking    (hidden)
 8. text        There are event types here I don't recognise (`task_summary`, `post_turn_summary`), so I'm checking…
 9. tool_use    Read {"file_path": "~/github/claude-lab/labs/plugin/zero-to-agent/skills/stream-json-explainer/reference…
10. tool_result 1 # stream-json reference (Claude Code 2.1.x) 2 3 | event | meaning | 4 |---|---| 5 | `system` / `i…
11. thinking    (hidden)
12. text        This was a short, successful run. The model was asked how many lines are in `notes.txt`, ran one sh…
13. result      turns=5 in=10+cache64057 out=1321 → This was a short, successful run. ...
```

(fixture: `labs/fixtures/skill.jsonl`)

เห็นทั้งสามชั้นของ progressive disclosure:

1. **ขั้น 2** — model เห็นแค่ `description` แล้วตัดสินใจเรียก tool `Skill` เอง (ชื่อเต็มคือ `<plugin>:<skill>`)
2. **ขั้น 4** — เนื้อหา `SKILL.md` ถูกใส่เข้ามาเป็นข้อความ (ขึ้นต้นด้วย `Base directory for this skill: ...` เพื่อให้ model รู้ว่าไฟล์ประกอบอยู่ที่ไหน)
3. **ขั้น 8–10** — เจอ event ที่ไม่รู้จัก (`task_summary`) จึงทำตามคำสั่งในข้อสุดท้าย: อ่าน `reference.md` — ถ้า trace มีแต่ event ที่รู้จัก ไฟล์นี้จะไม่ถูกโหลดเลย

สังเกตว่า skill **ไม่ได้ให้สิทธิ์อะไรเพิ่ม** — การอ่านไฟล์ยังต้องผ่าน tool (`Bash`, `Read`) และระบบ permission ตามปกติ (ที่นี่ `wc` กับ `cut` ผ่านเพราะ Claude Code ถือว่าเป็นคำสั่งอ่านอย่างเดียว)

## 6.4 และเมื่อไม่ควรถูกเรียก

คำถามที่ไม่เกี่ยวกับ trace — plugin เดิม skill เดิม:

```sh
$ claude -p "What is 17 * 23? Answer with the number only." \
    --output-format stream-json --verbose --max-turns 2 \
    --plugin-dir ~/github/claude-lab/labs/plugin/zero-to-agent ... | python3 -m labs.trace
 1. init        tools=Task,Bash,...,Skill,...
 2. text        391
 3. result      turns=1 in=2+cache15056 out=3 → 391
```

(fixture: `labs/fixtures/no-skill.jsonl`)

ไม่มี `Skill` — เนื้อหา `SKILL.md` ไม่เคยเข้า context ต้นทุนของ skill ที่ไม่ได้ใช้คือแค่ `description` บรรทัดเดียว

## 6.5 skill vs tool vs subagent

| | tool / MCP | subagent | skill |
|---|---|---|---|
| คืออะไร | โค้ดที่รันได้ | agent loop อีกตัวใน context ใหม่ | ข้อความคำสั่ง (Markdown) |
| เพิ่มความสามารถ | ทำสิ่งใหม่ได้ (เรียก API, คำนวณ) | แยกงาน ไม่ให้รก context หลัก | รู้ขั้นตอนที่ดี |
| อยู่ใน context | schema ทุกครั้ง | `description` ทุกครั้ง, งานข้างในไม่เข้า | `description` ทุกครั้ง, เนื้อหาเมื่อเรียก |
| ใครตัดสินใจใช้ | model | model | model |

ทั้งสามอย่าง model เป็นคนตัดสินใจ — ถ้าอยากให้บางอย่าง **เกิดขึ้นทุกครั้งแน่นอน** ต้องใช้ hook (บทที่ 7)

## 6.6 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. เขียน skill `commit-message` ที่สอนรูปแบบ commit แบบ conventional (`feat:`, `fix:`, ...) พร้อม `description` ที่บอกว่าใช้เมื่อไหร่ วางใน `.claude/skills/commit-message/SKILL.md` ของโปรเจกต์ทดลอง แล้วสั่ง `claude -p` ให้เขียน commit message ดูว่า skill ถูกเรียกไหม
2. เปลี่ยน `description` ของ `stream-json-explainer` เป็น `Helps with files.` แล้วรันคำสั่งในหัวข้อ 6.3 อีกครั้ง ดูว่ายังถูกเรียกหรือไม่ (เสร็จแล้วคืนค่าเดิม)
3. ลบบรรทัดสุดท้ายที่สั่งให้อ่าน `reference.md` ออก แล้วดูว่า model อธิบาย `task_summary` อย่างไร — ถูกหรือเดา

### เช็คความเข้าใจ

1. ส่วนไหนของ skill อยู่ใน context ตลอด ส่วนไหนโหลดเมื่อจำเป็น และทำไมถึงออกแบบแบบนี้
2. skill ทำให้ agent รันคำสั่งที่ปกติไม่ได้รับอนุญาตได้ไหม เพราะอะไร

## สรุปบทที่ 6

- skill = คู่มือ Markdown (`SKILL.md` + ไฟล์ประกอบ) ที่ model เลือกโหลดเอง
- progressive disclosure: `description` อยู่ตลอด → เนื้อหาเมื่อเรียก → ไฟล์ประกอบเมื่อจำเป็น
- `description` ต้องบอกทั้ง "ทำอะไร" และ "ใช้เมื่อไหร่" เพราะเป็นสิ่งเดียวที่ model ใช้ตัดสินใจ
- skill ไม่เพิ่มสิทธิ์ — ทุกการกระทำยังผ่าน tool และ permission
- tool, subagent, skill ล้วนเป็นการตัดสินใจของ model; ถ้าต้องการความแน่นอนใช้ hook
