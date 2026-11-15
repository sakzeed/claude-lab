# claude-lab — design

วันที่: 2026-11-15
สถานะ: อนุมัติแล้ว (ผู้ใช้: "ใช้ Repo: sakzeed/claude-lab") — ต้นฉบับอยู่ที่ `specs/`

## ทำไม

ผู้ใช้อยากเข้าใจ **การทำงานข้างใน** ของ AI (LLM), agent, MCP, `SKILL.md` และ plugin แบบ "zero to hero" — ไม่ใช่แค่วิธีใช้ แต่เห็นกลไกจริงทุกชั้น คนอ่านหลักคือผู้ใช้เอง (กำลังเรียน Python จาก 30 Days Of Python) และเผยแพร่เป็นเว็บภาษาไทยแบบเดียวกับ [opencode-lab](https://github.com/sakzeed/opencode-lab)

## เป้าหมาย

- repo ใหม่ **`sakzeed/claude-lab`** (public, MIT) — เว็บบทเรียน MkDocs Material บน GitHub Pages + โค้ด lab ที่รันได้จริง
- track เดียว **8 บท** เรียงจากศูนย์ แต่ละบทต่อยอดบทก่อน:

| บท | ไฟล์ | เข้าใจอะไร | ลงมือ |
|---|---|---|---|
| 1 | `docs/01-llm-basics.md` | LLM คืออะไร: token, context window, message, stateless, ทำไมตอบไม่เหมือนเดิม | `claude -p --output-format json` ดู `usage` (token เข้า/ออก) + ถามซ้ำให้เห็นว่าไม่จำ |
| 2 | `docs/02-tool-use.md` | model ไม่รันอะไรเอง — มัน "ขอ" ให้โปรแกรมรัน; tool schema (JSON Schema) | Python: model ปลอมที่คืน tool request → โปรแกรมรัน → ส่งผลกลับ |
| 3 | `docs/03-agent-loop.md` | agent = ลูป คิด → เรียก tool → ดูผล → ซ้ำ จนจบ; max turns, stop condition | `labs/mini_agent/` (~100 บรรทัด) + ดูลูปจริงของ Claude ผ่าน `claude -p --output-format stream-json --verbose` แล้วอ่านด้วย `labs/trace/` |
| 4 | `docs/04-context-subagents.md` | context จำกัด, compaction, subagent = context แยก + คืนแค่สรุป | สร้าง `.claude/agents/<name>.md` แล้วเห็น subagent call ใน stream-json |
| 5 | `docs/05-mcp.md` | MCP = JSON-RPC 2.0 ผ่าน stdio: `initialize`, `tools/list`, `tools/call` | `labs/mcp_server/` เขียนด้วย stdlib (ไม่ใช้ SDK), ทดสอบด้วยการ pipe JSON เอง แล้ว `claude mcp add` |
| 6 | `docs/06-skills.md` | `SKILL.md`: frontmatter `name`/`description`, โหลดเมื่อจำเป็น (progressive disclosure), ไฟล์ประกอบ | เขียน skill เอง, ดูว่าเมื่อไหร่ถูกเรียก/ไม่ถูกเรียก |
| 7 | `docs/07-hooks.md` | hook = โค้ดของเรารันก่อน/หลัง tool call; ต่างจาก skill (deterministic vs model ตัดสิน) | hook Python ที่ log/บล็อก tool call |
| 8 | `docs/08-plugins.md` | plugin = แพ็ก skill + agent + MCP + hook + manifest; marketplace | ประกอบ `labs/plugin/` จากบท 4–7, โหลดด้วย `--plugin-dir` / local marketplace, `claude plugin validate` |

- ของที่ copy ไปใช้ได้: subagent, skill, hook, MCP server และ plugin ที่สร้างในบท 4–8
- CI ตรวจ docs + โค้ด lab ทุก PR; deploy Pages เมื่อ push `main`

## สิ่งที่ไม่ทำ

- เรียก Claude API / ใช้ API key ใด ๆ, บริการเสียเงิน, LLM ฟรีของเจ้าอื่น (Gemini ฯลฯ), local model (Ollama)
- อธิบายการ train model เชิงลึก (math, transformer internals) — บท 1 แค่ภาพรวมพอให้เข้าใจพฤติกรรม
- Claude Agent SDK, remote MCP (HTTP/SSE), OAuth
- track อื่นนอก Claude Code

## ข้อจำกัด

- **ฟรีทั้งหมด**: model จริงมีแหล่งเดียวคือ `claude` CLI (Claude Code `2.1.325` บนเครื่องนี้) ซึ่งใช้ subscription ที่ผู้ใช้มีอยู่ → กินโควตา subscription; ใช้ `claude -p` ให้น้อยครั้ง สั้น และบันทึกผลไว้ใช้ซ้ำ
- โค้ด lab: **Python 3.12 stdlib เท่านั้น** (ไม่มี `mcp` SDK, `anthropic`, `requests`) — ทั้งเพื่อให้เห็น protocol ตรง ๆ และรันบน proot ได้
- เครื่อง: Ubuntu 24.04, proot บน Android, aarch64 — output ในบทมาจากเครื่องนี้และต้องบอกตามจริง
- **public**: ทุก output ต้องคัดข้อมูลส่วนตัวออก — ชื่อบัญชี GitHub อื่นนอกจาก `sakzeed`, email, path/ชื่อโปรเจกต์อื่นในเครื่อง, session id, ข้อมูลใน `~/.claude` (history, settings, memory)
- ภาษาไทย, ชื่อไฟล์อังกฤษ, H1 เดียวต่อบท; validator แบบ opencode-lab (chat text, Thai/Latin ติดกัน, fence)
- Pages ของบัญชีฟรีต้องเป็น repo public (ตรงกับที่เลือก)

## ทางเลือก

| ทาง | เนื้อหา | trade-off | สรุป |
|---|---|---|---|
| **1. Python stdlib + Claude Code เป็น model จริง** | model ปลอมสอนกลไก, `claude -p stream-json` ให้เห็นลูปจริง, MCP/skill/plugin สร้างเองแล้วต่อเข้า Claude Code | ฟรี (กินโควตา subscription), ทุกบทอิงระบบเดียวกัน; agent ที่เขียนเองไม่ได้ต่อ LLM จริง | **เลือก** (ผู้ใช้: "ทาง1") |
| 2. Gemini free tier ใน agent ที่เขียนเอง | agent ตัวเองคุยกับ LLM จริง | ต้องมี key ของ Google, rate limit, รูปแบบ tool call ไม่ตรงกับ Claude Code ในบท 5–8 | ไม่เลือก |
| 3. local model (Ollama) | ฟรีจริง | ช้า/กินแรมเกินบนมือถือ proot | ตัดทิ้ง |

## Decisions

### ผู้ใช้ตัดสิน

- จุดประสงค์: เข้าใจกลไก AI → agent → MCP → `SKILL.md` → plugin แบบ zero to hero
- ฟรีทั้งหมด, ทาง 1, repo public

### ฝ่ายเราตัดสิน (แก้ได้)

- บัญชี **`sakzeed`** (ชุดเดียวกับ opencode-lab; Pages ได้ทันที)
- โครงและ tooling ลอก opencode-lab: `mkdocs.yml` (Material, `language: th`), `tools/check_docs.py`, `ci.yml` (PR), `pages.yml` (push `main`), `specs/` + `specs/plans/`
- เป็น track เดียว 8 บท (ไม่แยกหลาย track) เพราะทุกเรื่องต่อกันเป็นสายเดียว

### โครง repo

```
README.md  LICENSE  mkdocs.yml  requirements.txt  .gitignore
docs/index.md  docs/01-…08-*.md
labs/
  mini_agent/     agent loop + model ปลอม (scripted) + tool 2–3 ตัว (เช่น อ่านไฟล์, คิดเลข)
  trace/          อ่าน stream-json ของ claude -p แล้วสรุปเป็นลำดับ turn/tool call
  mcp_server/     MCP server stdio, JSON-RPC 2.0, stdlib
  plugin/         claude-lab plugin: .claude-plugin/plugin.json, skills/, agents/, hooks/, .mcp.json
  fixtures/       stream-json ที่บันทึกจากเครื่องจริง (คัดข้อมูลส่วนตัวแล้ว) ใช้ใน test
tests/            unittest (stdlib)
tools/check_docs.py
specs/
```

### test และ CI

- `python -m unittest discover -s tests` — ครอบ mini_agent (ลูปจบ, max turns, tool error), trace parser (บน fixture), MCP server (ส่ง JSON-RPC เข้า subprocess แล้วตรวจคำตอบ: initialize, tools/list, tools/call, method ไม่รู้จัก → error -32601, JSON เสีย → -32700), plugin manifest (JSON ถูกต้อง, path ที่อ้างมีจริง)
- CI ไม่เรียก `claude` (ไม่มี subscription บน runner) — ทุก test ใช้ fixture
- `ci.yml`: job `check` (validator + `mkdocs build --strict`) และ job `labs` (unittest บน Python 3.12)

## Anti-goals

- อ้างเรื่องข้างในของ Claude/Claude Code ที่ไม่ได้สังเกตหรือไม่มีแหล่งอ้างอิง ราวกับเป็นข้อเท็จจริง — ต้องแยก "เห็นจากเครื่องจริง" กับ "คำอธิบาย/อุปมา" ให้ชัด
- คำสั่ง/flag ที่ไม่ได้ลองบน `2.1.325` (Claude Code เปลี่ยนเร็ว — ทุกคำสั่งในบทต้องรันจริง)
- output ที่มีข้อมูลส่วนตัวหลุดขึ้น repo public
- ตัวอย่างที่ต้องใช้ API key หรือเงิน
- บทที่ข้ามขั้น (ใช้ศัพท์ก่อนอธิบาย) — คนอ่านเริ่มจากศูนย์

## Left to builder

- ถ้อยคำ ลำดับย่อย ขนาดโค้ดที่แสดงในแต่ละบท; แบบฝึกหัด/คำถามเช็คความเข้าใจต่อบท (แนะนำ 3 + 2 แบบ opencode-lab)
- จำนวนครั้งที่เรียก `claude -p` (แนะนำ ≤ 15 ทั้ง track, prompt สั้น, `--max-turns` จำกัด)
- tool ของ mini_agent และ MCP server (แนะนำ: เครื่องคิดเลข + อ่าน/นับบรรทัดไฟล์ — ปลอดภัย ไม่แตะเน็ต)
- ชื่อ skill/agent/hook ใน plugin
- รายละเอียด schema ของ plugin/hook/skill ให้ยึดตามที่ `claude plugin validate` และ docs ปัจจุบันยอมรับบนเครื่องนี้

## Verification

- `python -m unittest discover -s tests` ผ่าน; `python3 tools/check_docs.py` → `ok: 8 pages`; `mkdocs build --strict` exit 0
- MCP server: `claude mcp list` แสดง server เชื่อมต่อได้ และ `claude -p` เรียก tool ของมันได้จริง (บันทึกผลในบท 5)
- plugin: `claude plugin validate labs/plugin` ผ่าน และ skill/agent/hook ของ plugin ทำงานใน session จริง
- grep ทั้ง repo ไม่เจอชื่อบัญชีอื่น, email, `session_id` จริง, path ส่วนตัว
- CI ทุก job success; Pages deploy success; 9/9 URL (index + 8 บท) = 200
