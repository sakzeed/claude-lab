# claude-lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** สร้าง repo public `sakzeed/claude-lab`: เว็บบทเรียนไทย 8 บท (LLM → tool use → agent loop → subagent → MCP → skill → hook → plugin) + โค้ด lab Python stdlib ที่มี test และ CI/Pages

**Architecture:** โค้ด lab อยู่ใน package `labs/` (stdlib ล้วน) — `mini_agent` (ลูป agent + model ปลอม), `trace` (อ่าน stream-json ของ `claude -p`), `mcp_server` (JSON-RPC stdio), `plugin/claude-lab` (skill + agent + hook + MCP) — test ใน `tests/` ใช้ fixture ที่บันทึกจากเครื่องจริงแล้ว redact ดังนั้น CI ไม่ต้องเรียก `claude` เว็บใช้โครง opencode-lab (MkDocs Material, validator, `ci.yml`, `pages.yml`)

**Tech Stack:** Python 3.12 stdlib (`unittest`, `json`, `ast`, `subprocess`), Claude Code `2.1.325` CLI, MkDocs Material 9.x, GitHub Actions

**Spec:** `specs/2026-11-15-claude-lab-design.md`

## Global Constraints

- ฟรีทั้งหมด: ไม่มี API key, ไม่มี dependency นอก stdlib ในโค้ด lab (`requirements.txt` มีแค่ `mkdocs-material==9.*`)
- `claude -p` ทั้ง track ≤ 15 ครั้ง, prompt สั้น, `--max-turns` ≤ 5; ผลดิบเก็บใน scratchpad, ขึ้น repo เฉพาะที่ redact แล้ว
- redact ทุก output ก่อน commit: `session_id`/uuid → `<session>`/`<uuid>`, path บ้าน → `~`, ชื่อบัญชีอื่นนอก `sakzeed`, email, ชื่อโปรเจกต์อื่นในเครื่อง
- บท: ไทย, H1 เดียว, 3 แบบฝึกหัด + 2 คำถามเช็ค + สรุป; ทุกคำสั่งรันจริงบน `2.1.325`; แยก "เห็นจากเครื่องจริง" กับ "คำอธิบาย" ชัด
- ระบุเครื่อง: Ubuntu 24.04, proot บน Android, aarch64
- validator: `ok: 8 pages`; `mkdocs build --strict` ผ่าน
- commit แบบ conventional; ห้าม commit `site/`, `.venv/`, `*.log`, ผลดิบ

## Review Focus

- **MCP: บรรทัดที่ไม่ใช่ JSON / method ไม่รู้จัก / notification (ไม่มี `id`)** → `-32700` / `-32601` / ไม่ตอบเลย; server ต้องไม่ตาย — test `test_parse_error_keeps_running`, `test_notification_no_reply`
- **MCP: ห้ามพิมพ์อะไรลง stdout นอกจาก JSON-RPC** (log ไป stderr) ไม่งั้น client พัง — test `test_stdout_only_jsonrpc`
- **mini_agent: model ขอ tool ที่ไม่มี / tool โยน exception** → ส่ง `tool_result` ที่ `is_error: true` กลับให้ model ลูปเดินต่อ ไม่ crash — test `test_unknown_tool_is_error_result`, `test_tool_exception_is_error_result`
- **calculator ต้องไม่ใช่ `eval`** (input มาจาก model) — `"__import__('os')"` ต้องถูกปฏิเสธ — test `test_calculator_rejects_names`
- **fixture/บทเรียนรั่วข้อมูลส่วนตัว** — test `test_fixtures_redacted` grep หา `/root/`, `session_id` ที่ไม่ใช่ `<session>`, `@` แบบ email

---

### Task 1: repo scaffold + validator

**Files:**
- Create: `README.md`, `LICENSE` (MIT, `sakzeed`), `.gitignore` (ลอก opencode-lab + `__pycache__/`), `requirements.txt`, `mkdocs.yml`, `docs/index.md`, `tools/check_docs.py`, `labs/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: `tools/check_docs.py` (ลอกจาก opencode-lab) ที่ `EXPECTED` = `docs/01-llm-basics.md`, `02-tool-use.md`, `03-agent-loop.md`, `04-context-subagents.md`, `05-mcp.md`, `06-skills.md`, `07-hooks.md`, `08-plugins.md`; `mkdocs.yml` nav 8 บทตามลำดับนี้, `site_url: https://sakzeed.github.io/claude-lab/`

- [x] **Step 1:** `git init -b main` ใน `~/github/claude-lab` (มี `specs/` อยู่แล้ว); เขียนไฟล์ข้างบน
- [x] **Step 2:** `python3 tools/check_docs.py` → `FAIL` + missing 8 หน้า (ยังไม่มีบท — คาดไว้)
- [x] **Step 3:** commit `chore: scaffold docs site and validator`

### Task 2: `labs/mini_agent` — tool use + agent loop

**Files:**
- Create: `labs/mini_agent/__init__.py`, `agent.py`, `tools.py`, `__main__.py`; `tests/test_mini_agent.py`

**Interfaces:**
- Produces:
  - `@dataclass Tool(name: str, description: str, input_schema: dict, run: Callable[[dict], str])`
  - `class ScriptedModel(replies: list[dict])` — `respond(messages: list[dict], tools: list[dict]) -> dict` คืน reply ถัดไปในรายการ; reply รูปแบบเดียวกับ Claude: `{"stop_reason": "tool_use"|"end_turn", "content": [{"type": "text", "text"}, {"type": "tool_use", "id", "name", "input"}]}`
  - `@dataclass AgentResult(messages: list[dict], final_text: str, turns: int, stopped: str)` — `stopped` ∈ `"end_turn"`, `"max_turns"`
  - `run_agent(model, tools: list[Tool], prompt: str, max_turns: int = 10, on_event=None) -> AgentResult` — ผล tool ส่งกลับเป็น user message `{"type": "tool_result", "tool_use_id", "content", "is_error"}`
  - `tools.calculator` (ใช้ `ast` รับแค่ตัวเลข + `+ - * / ** %` และวงเล็บ), `tools.count_lines` (`{"path"}` → จำนวนบรรทัด)
  - `python -m labs.mini_agent` เล่นบทตัวอย่าง (model ปลอมขอ calculator แล้วตอบ) พิมพ์ทีละ turn

- [x] **Step 1: tests** `test_single_tool_round_trip` (2 replies → `turns == 2`, `stopped == "end_turn"`, `final_text` มีผลคำนวณ), `test_max_turns` (model ขอ tool ตลอด, `max_turns=3` → `stopped == "max_turns"`, `turns == 3`), `test_unknown_tool_is_error_result`, `test_tool_exception_is_error_result`, `test_calculator` (`"2*(3+4)"` → `"14"`), `test_calculator_rejects_names`, `test_count_lines` (ไฟล์ temp 3 บรรทัด → `"3"`)
- [x] **Step 2:** `python3 -m unittest tests.test_mini_agent` → FAIL (import)
- [x] **Step 3:** implement → ok; `python3 -m labs.mini_agent` พิมพ์ลูปครบ
- [x] **Step 4:** commit `feat(mini_agent): add tool use loop with scripted model`

### Task 3: `labs/trace` — อ่านลูปจริงของ Claude + fixture

**Files:**
- Create: `labs/trace/__init__.py`, `trace.py`, `redact.py`, `__main__.py`; `labs/fixtures/*.jsonl`; `tests/test_trace.py`

**Interfaces:**
- Produces:
  - `@dataclass Step(kind: str, detail: str)` — `kind` ∈ `"init"`, `"text"`, `"tool_use"`, `"tool_result"`, `"result"`
  - `summarize(lines: Iterable[str]) -> list[Step]` — ข้ามบรรทัดว่าง/ไม่ใช่ JSON, ไม่ล้มกับ event type ที่ไม่รู้จัก
  - `redact(line: str, home: str) -> str` — `session_id`/`uuid` → `<session>`/`<uuid>`, `home` → `~`
  - CLI: `claude -p ... --output-format stream-json --verbose | python3 -m labs.trace` พิมพ์ลำดับ turn; `python3 -m labs.trace.redact < raw > fixture`

- [x] **Step 1:** รัน `claude -p` จริง 1 ครั้ง (prompt ให้นับบรรทัดไฟล์ใน repo, `--max-turns 3`, allowedTools จำกัด) เก็บดิบใน scratchpad; ดูรูปแบบ event จริง
- [x] **Step 2: tests** บน fixture ที่ redact แล้ว: `test_summarize_order` (ลำดับ kind เริ่ม `init` จบ `result`, มี `tool_use` ตามด้วย `tool_result`), `test_unknown_event_ignored`, `test_garbage_line_ignored`, `test_redact` (string ที่มี session_id + home → แทนครบ), `test_fixtures_redacted`
- [x] **Step 3:** FAIL → implement → ok; commit `feat(trace): summarize claude stream-json`

### Task 4: `labs/mcp_server` — MCP stdio ด้วย stdlib

**Files:**
- Create: `labs/mcp_server/__init__.py`, `server.py`, `__main__.py`; `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `labs.mini_agent.tools.calculator`, `count_lines` (logic เดียวกัน — แต่ใน plugin ต้องเป็นไฟล์เดี่ยว ดู Task 5 จึงให้ `server.py` **ไม่ import** จาก package อื่น: copy ฟังก์ชันสองตัวเข้าไปเอง)
- Produces: `handle(msg: dict) -> dict | None`; `serve(stdin, stdout)` อ่านทีละบรรทัด (newline-delimited JSON); methods `initialize` (ตอบ `protocolVersion` ที่ client ขอถ้าอยู่ใน `SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]` ไม่งั้นตัวแรก, `capabilities: {"tools": {}}`, `serverInfo: {"name": "claude-lab", "version": "0.1.0"}`), `notifications/initialized` (ไม่ตอบ), `ping`, `tools/list`, `tools/call` (ผลเป็น `{"content": [{"type": "text", "text"}], "isError": bool}`); error codes `-32700` parse, `-32601` method, `-32602` params; รันได้ด้วย `python3 labs/mcp_server/server.py`

- [x] **Step 1: tests** (subprocess จริง) `test_initialize`, `test_tools_list` (มี `calculator`, `count_lines` พร้อม `inputSchema`), `test_tools_call_calculator`, `test_tool_error_is_result` (`isError: true` ไม่ใช่ JSON-RPC error), `test_unknown_method`, `test_parse_error_keeps_running` (ส่งขยะแล้วตามด้วย ping → ได้คำตอบ ping), `test_notification_no_reply`, `test_stdout_only_jsonrpc`
- [x] **Step 2:** FAIL → implement → ok
- [x] **Step 3:** ทดสอบกับ Claude Code: `claude mcp add --scope local claude-lab -- python3 labs/mcp_server/server.py`, `claude mcp list` เห็น connected, `claude -p` (1 ครั้ง) เรียก tool ได้; บันทึกผล (redact); `claude mcp remove claude-lab`
- [x] **Step 4:** commit `feat(mcp_server): add stdlib MCP server over stdio`

### Task 5: `labs/plugin/claude-lab` — skill + agent + hook + MCP

**Files:**
- Create: `labs/plugin/claude-lab/.claude-plugin/plugin.json`, `skills/<skill>/SKILL.md`, `agents/<agent>.md`, `hooks/hooks.json`, `hooks/log_tool.py`, `.mcp.json`, `mcp/server.py` (สำเนาของ `labs/mcp_server/server.py`); `tests/test_plugin.py`

**Interfaces:**
- Produces: plugin ชื่อ `claude-lab`; `.mcp.json` รัน `python3 ${CLAUDE_PLUGIN_ROOT}/mcp/server.py`; hook `PreToolUse` เรียก `log_tool.py` ที่อ่าน JSON จาก stdin แล้ว append บรรทัดลง `~/.claude-lab/tool-log.jsonl` (ไม่บล็อก, exit 0) และบล็อก (exit 2 + เหตุผลทาง stderr) เมื่อคำสั่ง Bash มี `rm -rf`
- Schema: ยึดตามที่ `claude plugin validate` ยอมรับบนเครื่องนี้

- [x] **Step 1: tests** `test_manifest_json` (JSON ถูก, มี `name == "claude-lab"`), `test_referenced_paths_exist`, `test_mcp_copy_in_sync` (`mcp/server.py` byte-identical กับ `labs/mcp_server/server.py`), `test_skill_frontmatter` (`name`, `description` มีค่า), `test_hook_logs` (ส่ง JSON PreToolUse เข้า `log_tool.py` ด้วย `HOME` ชั่วคราว → exit 0 + มีบรรทัดใน log), `test_hook_blocks_rm_rf` (→ exit 2)
- [x] **Step 2:** FAIL → implement → ok; `claude plugin validate labs/plugin/claude-lab` ผ่าน
- [x] **Step 3:** ทดสอบใน session จริงด้วย `--plugin-dir` (≤ 3 ครั้ง `claude -p`): skill ถูกเรียก, agent ใช้ได้, hook เขียน log/บล็อก
- [x] **Step 4:** commit `feat(plugin): bundle skill, agent, hook and MCP server`

### Task 6: บทเรียน 8 บท

**Files:**
- Create: `docs/01-llm-basics.md` … `docs/08-plugins.md`; Modify: `docs/index.md`, `README.md`

- [x] **Step 1:** เก็บ output จริงที่บทต้องใช้ (บท 1: `--output-format json` ดู `usage` + ถามซ้ำ; บท 4: subagent ใน stream-json; บท 6: skill ถูก/ไม่ถูกเรียก) — นับรวม `claude -p` ทั้ง track ไม่เกิน 15; redact ทั้งหมด
- [x] **Step 2:** เขียน 8 บทตามตารางใน design; โค้ดที่แสดงตัดมาจาก `labs/` จริง
- [x] **Step 3:** `python3 tools/check_docs.py` → `ok: 8 pages`; `mkdocs build --strict` → exit 0
- [x] **Step 4:** grep ทั้ง repo หา `/root/`, ชื่อบัญชีอื่น, email, session id จริง → ไม่เจอ
- [x] **Step 5:** commit `docs: add chapters 1-8`

### Task 7: CI, repo, Pages

**Files:**
- Create: `.github/workflows/ci.yml` (job `check` = validator + `mkdocs build --strict` บน 3.11/3.12 ลอก opencode-lab; job `labs` = `python -m unittest discover -s tests -t .` บน 3.12; paths รวม `labs/**`, `tests/**`), `.github/workflows/pages.yml` (ลอก opencode-lab)

- [x] **Step 1:** เขียน workflow; parse YAML ผ่าน; รัน unittest + validator + mkdocs ในเครื่องผ่าน; commit `ci: add checks and pages deploy`
- [x] **Step 2:** (ใช้บัญชี `sakzeed`) `gh repo create sakzeed/claude-lab --public --source . --push`; ตั้ง Pages source = GitHub Actions; สลับ `gh` กลับบัญชีเดิม
- [x] **Step 3:** ตาม run `pages.yml` → success; 9/9 URL = 200; รัน `ci.yml` ด้วย `workflow_dispatch` → success

## สิ่งที่เปลี่ยนจาก plan ระหว่างลงมือ

- plugin เปลี่ยนชื่อ `claude-lab` → `zero-to-agent` เพราะ `claude plugin validate` สงวนชื่อที่ขึ้นต้นด้วย `claude-`; MCP server ใน plugin ชื่อ `lab-tools`
- `redact` เป็น whitelist ต่อชนิด event และคืน `None` เพื่อทิ้ง event (rate limit ฯลฯ); ชื่อ model ถูกแทนด้วย `<model>`; `Step.kind` เพิ่ม `thinking`
- `claude -p` แยกจาก setup ส่วนตัวด้วย scratch dir + `--strict-mcp-config --setting-sources project --disable-slash-commands` (`--bare` ต้องใช้ API key จึงใช้ไม่ได้); ใช้ไป 9 ครั้ง
- ตรวจ MCP ด้วย `claude mcp get` แทน `claude mcp list` (list ไล่ health-check ทุก server แล้วหมดเวลา)
- บทที่ 8 โหลด plugin ด้วย `--plugin-dir` อย่างเดียว ไม่ติดตั้งผ่าน marketplace เพื่อไม่ให้ config หลักของเครื่องเปลี่ยน
- แก้บั๊กที่พบระหว่างเขียนบท: calculator จำกัดเลขชี้กำลังไว้ที่ 100 (`2**10**10` ทำให้ค้าง), MCP server ไม่ crash เมื่อ `params` ไม่ใช่ object
- `ci.yml` รันตอน push เข้า `main` ด้วย (สำหรับ `labs/**`, `tests/**`) เพราะ repo นี้ทำงานบน `main` ตรง ๆ
