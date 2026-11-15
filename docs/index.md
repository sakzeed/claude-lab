# Claude Lab

บทเรียนภาษาไทยที่พาจาก **"ไม่รู้ว่า AI ทำงานยังไง"** ไปจนถึง **"เขียน agent, MCP server, skill, hook และ plugin เองได้"** — ทุกบทลงมือจริง ไม่ใช่ทฤษฎีล้วน

## เรียนอะไร

| บท | เรื่อง | ลงมือ |
|---|---|---|
| [1](01-llm-basics.md) | LLM ทำงานยังไง: token, context, ไม่จำบทสนทนา | ดู token ที่ใช้จริงจาก `claude -p` |
| [2](02-tool-use.md) | tool use: model "ขอ" โปรแกรม "ทำ" | model ปลอมใน Python |
| [3](03-agent-loop.md) | agent loop | agent จิ๋วเขียนเอง + ดูลูปจริงของ Claude |
| [4](04-context-subagents.md) | context และ subagent | สร้าง subagent ใน `.claude/agents/` |
| [5](05-mcp.md) | MCP: JSON-RPC ผ่าน stdio | MCP server ด้วย stdlib แล้วต่อเข้า Claude Code |
| [6](06-skills.md) | `SKILL.md` | เขียน skill และดูว่าเมื่อไหร่ถูกเรียก |
| [7](07-hooks.md) | hooks | hook ที่ log และบล็อก tool call |
| [8](08-plugins.md) | plugins | รวมทุกอย่างเป็น plugin ตัวเดียว |

## ฟรีทั้งหมด

- ไม่ใช้ API key และไม่มีบริการเสียเงิน — model จริงมีแหล่งเดียวคือ Claude Code (`claude`) ที่ใช้ subscription ที่มีอยู่แล้ว
- โค้ด lab เป็น **Python stdlib ล้วน** ไม่มี SDK ให้ติดตั้ง จึงเห็น protocol ตรง ๆ ทุกชั้น

## สภาพแวดล้อม

output ในบทเรียนรันจริงบน **Ubuntu 24.04 (proot-distro บน Android, aarch64)** ด้วย Claude Code `2.1.325` และ Python 3.12 — Claude Code เปลี่ยนเร็ว เวอร์ชันอื่นอาจมี flag หรือรูปแบบ output ต่างไป

## โค้ด

[sakzeed/claude-lab](https://github.com/sakzeed/claude-lab) — โค้ด lab อยู่ใน `labs/`, test ใน `tests/`
