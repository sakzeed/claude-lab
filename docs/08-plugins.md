# บทที่ 8: plugins — รวมทุกอย่างเป็นชิ้นเดียวแล้วแจกจ่าย

บทที่ 4–7 สร้างของไว้สี่ชิ้น: subagent, MCP server, skill และ hook ถ้าอยากเอาไปใช้ที่เครื่องอื่นหรือแบ่งให้คนอื่น การบอกให้ copy ไฟล์ไปวางสี่ที่นั้นยุ่งและพังง่าย **plugin** คือโฟลเดอร์เดียวที่รวมทุกอย่างพร้อม manifest ให้ Claude Code โหลดได้ในครั้งเดียว

plugin ของบทเรียนนี้ชื่อ `zero-to-agent` อยู่ที่ `labs/plugin/zero-to-agent/`

---

## 8.1 โครงสร้าง

```text
labs/plugin/zero-to-agent/
  .claude-plugin/plugin.json                     manifest (บังคับ)
  agents/file-stats.md                           subagent      (บทที่ 4)
  .mcp.json  +  mcp/server.py                    MCP server    (บทที่ 5)
  skills/stream-json-explainer/SKILL.md          skill         (บทที่ 6)
  skills/stream-json-explainer/reference.md
  hooks/hooks.json  +  hooks/log_tool.py         hook          (บทที่ 7)
```

Claude Code หาของแต่ละชนิดจาก **ชื่อโฟลเดอร์มาตรฐาน** (`agents/`, `skills/`, `hooks/hooks.json`, `.mcp.json`) ไม่ต้องลงทะเบียนใน manifest

manifest มีแค่ข้อมูลของ plugin:

```json
{
  "name": "zero-to-agent",
  "version": "0.1.0",
  "description": "Lab plugin from the claude-lab lessons: a skill, a subagent, a hook and a stdlib MCP server.",
  "author": { "name": "sakzeed" },
  "homepage": "https://sakzeed.github.io/claude-lab/",
  "license": "MIT"
}
```

ส่วน `.mcp.json` ชี้ไปที่ server ภายในโฟลเดอร์ plugin ด้วย `${CLAUDE_PLUGIN_ROOT}` (plugin ถูกติดตั้งไปไว้ที่อื่นได้ จึงห้ามใช้ path ตายตัว):

```json
{
  "mcpServers": {
    "lab-tools": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"]
    }
  }
}
```

!!! note "ทำไม `mcp/server.py` เป็นสำเนา"
    plugin ต้องอยู่ได้ด้วยตัวเอง — อ้างไฟล์นอกโฟลเดอร์ไม่ได้ เพราะตอนติดตั้ง Claude Code จะ copy เฉพาะโฟลเดอร์ plugin `mcp/server.py` จึงเป็นสำเนาของ `labs/mcp_server/server.py` และ test `test_mcp_copy_in_sync` ตรวจว่าสองไฟล์ยังเหมือนกันทุก byte (server จึงเขียนให้ไม่ import อะไรจาก package อื่นตั้งแต่แรก)

## 8.2 ตรวจด้วย `claude plugin validate`

ครั้งแรกที่สร้าง plugin นี้ใช้ชื่อ `claude-lab` ตามชื่อ repo แล้ว validate ไม่ผ่าน:

```text
✘ Found 1 error:

  ❯ name: Plugin name "claude-lab" is reserved: it passes as one of Anthropic's own.
    A third party's plugin name cannot start with "claude-", "anthropic-", "anthropics-", or "cc-plugin-",
    be "claude", "anthropic", "anthropics", "claude-code", or "claude-mods",
    or put "official" beside "claude" or "anthropic". Name it for what it does. ...

⚠ Found 1 warning:

  ❯ hooks.PreToolUse: Shell command uses ${CLAUDE_PLUGIN_ROOT} without quotes: python3 ${CLAUDE_PLUGIN_ROOT}/hooks/log_tool.py.
    If the expanded path contains a space the command can split into several words and fail. ...
```

ได้บทเรียนสองข้อ: ชื่อที่ขึ้นต้นด้วย `claude-` ถูกสงวนไว้ (กันการแอบอ้างเป็นของ Anthropic) และ path ใน hook ต้องมี quote — แก้เป็น `zero-to-agent` และใส่ quote แล้ว:

```sh
$ claude plugin validate labs/plugin/zero-to-agent
Validating plugin manifest: ~/github/claude-lab/labs/plugin/zero-to-agent/.claude-plugin/plugin.json
⚠ Found 1 plugin directory warning:
  ❯ .claude-plugin/plugin.json icon: No icon (ICON_MISSING). ...
...
✔ Validation passed
```

คำเตือนเรื่อง icon มีผลแค่ตอนส่ง plugin เข้า directory สาธารณะ ไม่กระทบการใช้งาน

## 8.3 โหลดมาใช้: `--plugin-dir`

ระหว่างพัฒนา ไม่ต้องติดตั้ง — ชี้โฟลเดอร์ตรง ๆ ด้วย `--plugin-dir` (ใช้ได้ทั้ง `claude` แบบแชตและ `claude -p`) ทุกตัวอย่างในบทที่ 6–7 ทำแบบนี้ และจาก `init` event จะเห็นของจาก plugin โผล่ขึ้นมา:

```text
"agents": ["claude", "Explore", "general-purpose", "Plan", "statusline-setup", "zero-to-agent:file-stats"]
```

ของจาก plugin ถูกตั้งชื่อนำหน้าด้วยชื่อ plugin เพื่อไม่ให้ชนกับของที่มีอยู่:

| ชนิด | ชื่อที่เห็นจริง | มาจาก |
|---|---|---|
| subagent | `zero-to-agent:file-stats` | `labs/fixtures/agent-hook.jsonl` |
| skill | `zero-to-agent:stream-json-explainer` | `labs/fixtures/skill.jsonl` |
| hook | ข้อความ `This hook comes from the zero-to-agent@inline plugin.` | `labs/fixtures/agent-hook.jsonl` |

(`@inline` คือ plugin ที่โหลดจาก `--plugin-dir` ไม่ได้มาจาก marketplace)

ใน session เดียวของบทที่ 7 ส่วนประกอบของ plugin ทำงานร่วมกัน: agent หลักส่งงานให้ subagent ของ plugin → subagent รัน `wc` → hook ของ plugin log คำสั่งนั้น → agent หลักสั่ง `rm -rf` → hook บล็อก

## 8.4 แจกจ่าย: marketplace

> **คำอธิบาย (ไม่ได้ทดลองในบทเรียนนี้ เพื่อไม่ให้ config หลักของเครื่องเปลี่ยน):** การติดตั้งถาวรทำผ่าน **marketplace** คือ repo หรือโฟลเดอร์ที่มีไฟล์ `.claude-plugin/marketplace.json` ระบุรายการ plugin ผู้ใช้เพิ่ม marketplace ด้วย `claude plugin marketplace add <repo หรือ path>` แล้วติดตั้งด้วย `claude plugin install <plugin>@<marketplace>` — หลังติดตั้งแล้ว `claude plugin list` และ `claude plugin details <plugin>` จะแสดง plugin (`details` ใช้ไม่ได้กับ plugin ที่โหลดด้วย `--plugin-dir`)

ก่อนติดตั้ง plugin ของคนอื่น ให้นึกถึงบทที่ 5 และ 7: **MCP server และ hook คือโค้ดที่รันบนเครื่องคุณ** ด้วยสิทธิ์ของคุณ — อ่าน `.mcp.json`, `hooks/hooks.json` และสคริปต์ที่มันเรียกก่อนเสมอ ส่วน skill และ agent เป็นแค่ข้อความ แต่ก็สั่งให้ model ทำสิ่งที่ไม่ต้องการได้

## 8.5 ภาพรวมทั้งบทเรียน

```text
บทที่ 1  LLM: ทำนาย token, ไม่จำ, ทุกอย่างอยู่ใน context
บทที่ 2  tool use: model ขอ (tool_use) → โปรแกรมทำ → ส่งผลกลับ (tool_result)
บทที่ 3  agent: วนข้อ 2 จนกว่า model จะหยุดขอ
บทที่ 4  subagent: agent loop อีกตัวใน context ใหม่ คืนแค่รายงาน
บทที่ 5  MCP: tool จากโปรแกรมภายนอก ผ่าน JSON-RPC
บทที่ 6  skill: คู่มือที่โหลดเมื่อจำเป็น
บทที่ 7  hook: โค้ดของเราที่รันทุกครั้ง model เลี่ยงไม่ได้
บทที่ 8  plugin: แพ็กข้อ 4–7 เป็นโฟลเดอร์เดียว
```

ทุกชั้นเป็นแค่สองอย่าง: **ข้อความที่ส่งให้ model** (prompt, คำอธิบาย tool, skill, agent) กับ **โค้ดธรรมดาที่รันรอบ ๆ model** (agent loop, tool, MCP server, hook) — ไม่มีเวทมนตร์ที่มองไม่เห็นอีกแล้ว

## 8.6 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. เพิ่ม skill ที่สองใน `zero-to-agent` (เช่น skill `commit-message` จากบทที่ 6) รัน `python3 -m unittest tests.test_plugin` และ `claude plugin validate` ให้ผ่าน
2. โหลด plugin ด้วย `--plugin-dir` โดยไม่ใส่ `--strict-mcp-config` แล้วดูรายการ `tools` ใน init event ว่า tool ของ `lab-tools` ใช้ชื่ออะไร (ระวัง: ถ้าเครื่องมี MCP server อื่น ชื่อของมันจะโผล่ใน output ด้วย อย่าเผยแพร่ output ดิบ)
3. ลองเปลี่ยนชื่อ plugin ใน `plugin.json` เป็น `anthropic-tools` แล้วรัน `claude plugin validate` อ่าน error แล้วคืนค่าเดิม

### เช็คความเข้าใจ

1. ทำไม `.mcp.json` และ `hooks.json` ใน plugin ต้องใช้ `${CLAUDE_PLUGIN_ROOT}` แทน path ตายตัว และทำไมต้องมี quote
2. ส่วนไหนของ plugin เป็น "โค้ดที่รันบนเครื่อง" และส่วนไหนเป็น "ข้อความที่ส่งให้ model" — แต่ละส่วนมีความเสี่ยงต่างกันอย่างไร

## สรุปบทที่ 8

- plugin = โฟลเดอร์เดียว + `.claude-plugin/plugin.json`; ของแต่ละชนิดอยู่ในโฟลเดอร์มาตรฐาน
- plugin ต้องอยู่ได้ด้วยตัวเอง ใช้ `${CLAUDE_PLUGIN_ROOT}` (มี quote) และห้ามอ้างไฟล์นอกโฟลเดอร์
- `claude plugin validate` จับปัญหาจริง: ชื่อสงวน (`claude-...`) และ path ไม่มี quote
- `--plugin-dir` สำหรับพัฒนา; ของจาก plugin ถูกตั้งชื่อ `<plugin>:<ชื่อ>`
- marketplace สำหรับแจกจ่าย — MCP server และ hook ใน plugin คือโค้ดที่รันบนเครื่องผู้ติดตั้ง
