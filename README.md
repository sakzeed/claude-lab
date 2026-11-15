# claude-lab

บทเรียนภาษาไทย **เข้าใจ AI, agent, MCP, `SKILL.md` และ plugin แบบ zero to hero** พร้อมโค้ด lab Python stdlib ที่รันได้จริง

📖 **https://sakzeed.github.io/claude-lab/**

## มีอะไรในนี้

| ที่อยู่ | คืออะไร |
|---|---|
| `docs/` | บทเรียน 8 บท (MkDocs Material) |
| `labs/mini_agent/` | agent loop + model ปลอม + tool (บท 2–3) |
| `labs/trace/` | อ่าน `claude -p --output-format stream-json` เป็นลำดับ turn (บท 3–4) |
| `labs/mcp_server/` | MCP server ผ่าน stdio ด้วย stdlib (บท 5) |
| `labs/plugin/zero-to-agent/` | plugin: skill + subagent + hook + MCP server (บท 4–8) |
| `labs/fixtures/` | output จริงที่ตัดข้อมูลส่วนตัวแล้ว ใช้ใน test |
| `tests/` | `unittest` — CI ไม่ต้องเรียก `claude` |

## รันในเครื่อง

```sh
python3 -m unittest discover -s tests -t .   # test โค้ด lab
python3 -m labs.mini_agent                   # ดู agent loop กับ model ปลอม

# เว็บ
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 tools/check_docs.py
.venv/bin/mkdocs serve                       # http://127.0.0.1:8000
```

ทุกอย่างฟรี: ไม่ใช้ API key — ส่วนที่ต้องใช้ model จริงเรียกผ่าน Claude Code (`claude`) ที่มีอยู่

## License

MIT
