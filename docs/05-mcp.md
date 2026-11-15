# บทที่ 5: MCP — ต่อ tool จากภายนอกด้วย JSON-RPC

บทที่ 2–4 tool ทั้งหมดเป็นของที่ Claude Code มีอยู่แล้ว (`Bash`, `Read`, `Agent`) ถ้าอยากเพิ่ม tool ของเราเองล่ะ? **MCP (Model Context Protocol)** คือมาตรฐานกลางที่ให้โปรแกรมใดก็ได้ประกาศว่า "ฉันมี tool เหล่านี้" แล้ว agent ตัวไหนที่พูด MCP ได้ก็ใช้ได้ทันที

บทนี้เขียน MCP server เองด้วย Python stdlib ล้วน (ไม่ใช้ SDK) จึงเห็นทุกข้อความที่วิ่งไปมา โค้ดอยู่ที่ `labs/mcp_server/server.py` ราว 202 บรรทัด

---

## 5.1 MCP คือ JSON-RPC ผ่าน stdin/stdout

แบบที่ง่ายที่สุดของ MCP (stdio transport):

- Claude Code (**client**) รัน server เป็น process ลูก
- ส่ง request เป็น JSON **บรรทัดละหนึ่งข้อความ** ทาง stdin ของ server
- server ตอบเป็น JSON บรรทัดละหนึ่งข้อความทาง stdout

รูปแบบข้อความคือ **JSON-RPC 2.0**:

| ชนิด | หน้าตา | ต้องตอบไหม |
|---|---|---|
| request | `{"jsonrpc": "2.0", "id": 1, "method": "...", "params": {...}}` | ต้อง — ด้วย `id` เดิม |
| response | `{"jsonrpc": "2.0", "id": 1, "result": {...}}` หรือ `"error": {"code", "message"}` | — |
| notification | `{"jsonrpc": "2.0", "method": "..."}` (**ไม่มี** `id`) | ห้ามตอบ |

server ที่มีแค่ tool ต้องรู้จัก 4 method:

```text
client → initialize                 ← protocolVersion, capabilities, serverInfo
client → notifications/initialized    (notification: ไม่ตอบ)
client → tools/list                 ← name, description, inputSchema ของทุก tool
client → tools/call                 ← content + isError
```

## 5.2 คุยกับ server ด้วยมือ

ไม่ต้องมี Claude ก็ทดสอบได้ — แค่ pipe JSON เข้าไป:

```sh
$ printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"me","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"calculator","arguments":{"expression":"(120+80)*3"}}}' \
  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"calculator","arguments":{"expression":"__import__(\"os\")"}}}' \
  'hello?' \
  '{"jsonrpc":"2.0","id":5,"method":"resources/list"}' \
  | python3 labs/mcp_server/server.py
[claude-lab] ready (stdio)
[claude-lab] initialize from me, protocol 2025-06-18
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "claude-lab", "version": "0.1.0"}}}
{"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "calculator", "description": "Evaluate an arithmetic expression with + - * / % ** and parentheses.", "inputSchema": {...}}, {"name": "count_lines", ...}]}}
[claude-lab] tools/call calculator -> ok
{"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "600"}], "isError": false}}
[claude-lab] tools/call calculator -> error
{"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": "ValueError: only numbers and + - * / % ** ( ) are allowed"}], "isError": true}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error: Expecting value: line 1 column 1 (char 0)"}}
{"jsonrpc": "2.0", "id": 5, "error": {"code": -32601, "message": "method not found: resources/list"}}
```

(ย่อ `inputSchema` ให้สั้นลง)

ดูทีละจุด:

- **notification (`notifications/initialized`) ไม่มีคำตอบ** — 7 ข้อความเข้า แต่มี 6 คำตอบ
- **tool พัง ≠ protocol พัง** — `id 4` เป็น `result` ที่ `isError: true` (model อ่านแล้วแก้ตัวได้ เหมือนบทที่ 2) ส่วน `error` ของ JSON-RPC ใช้กับความผิดระดับ protocol เท่านั้น
- **ขยะ (`hello?`) ไม่ทำให้ server ตาย** — ตอบ `-32700` แล้วรับข้อความถัดไปต่อ (รวมถึง JSON ที่ซ้อนลึกเป็นแสนชั้น และ byte ที่ไม่ใช่ UTF-8 — server อ่าน stdin เป็น byte แล้ว decode เอง; test `test_deeply_nested_json_keeps_running`, `test_invalid_utf8_keeps_running`)
- **บรรทัดที่ขึ้นต้นด้วย `[claude-lab]` มาจาก stderr** — ลองดูว่า stdout มีแต่ JSON-RPC จริงไหม:

```sh
$ printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized"}' '{"jsonrpc":"2.0","id":9,"method":"ping"}' \
  | python3 labs/mcp_server/server.py 2>/dev/null | wc -l
1
```

!!! warning "กฎข้อเดียวที่พังบ่อยที่สุด"
    stdout คือช่องทางของ protocol — ถ้าโค้ดใน server `print()` อะไรลง stdout (debug, คำเตือนจาก library) client จะ parse ไม่ได้และตัดการเชื่อมต่อ log ทุกอย่างต้องไป **stderr** (`print(..., file=sys.stderr)`) test `test_stdout_only_jsonrpc` คุมเรื่องนี้

## 5.3 แกนของ server

```python
METHODS = {
    "initialize": _initialize,
    "ping": lambda params: {},
    "tools/list": _tools_list,
    "tools/call": _tools_call,
}


def handle(msg: dict) -> dict | None:
    """Answer one request. Notifications (no "id") never get a reply."""
    is_request = "id" in msg
    method = msg.get("method")
    try:
        if method not in METHODS:
            if not is_request:
                return None  # e.g. notifications/initialized
            raise RpcError(METHOD_NOT_FOUND, f"method not found: {method}")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            raise RpcError(INVALID_PARAMS, "params must be an object")
        result = METHODS[method](params)
    except RpcError as exc:
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:  # a bug in a handler must not kill the server
        log(f"internal error in {method}: {exc!r}")
        if not is_request:
            return None
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": INTERNAL_ERROR, "message": "internal error"}}
    if not is_request:
        return None
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}
```

สองชั้นที่กันไม่ให้ server ตาย: `params` ที่ไม่ใช่ object ได้ `-32602` และ bug ใด ๆ ใน handler ได้ `-32603` (internal error) แทนการ crash (test `test_bad_params_keep_running`)

`initialize` ตอบ `protocolVersion` ที่ client ขอ ถ้า server รองรับ (มีรายการใน `SUPPORTED`) ไม่งั้นตอบเวอร์ชันล่าสุดที่ตัวเองมี แล้วให้ client ตัดสินใจเองว่าจะคุยต่อไหม

## 5.4 ต่อเข้า Claude Code

```sh
$ claude mcp add claude-lab -- python3 ~/github/claude-lab/labs/mcp_server/server.py
Added stdio MCP server claude-lab with command: python3 ~/github/claude-lab/labs/mcp_server/server.py to local config
File modified: ~/.claude.json [project: <cwd>]
$ claude mcp get claude-lab
claude-lab:
  Scope: Local config (private to you in this project)
  Status: ✔ Connected
  Type: stdio
  Command: python3
  Args: ~/github/claude-lab/labs/mcp_server/server.py
  Environment:

To remove this server, run: claude mcp remove claude-lab -s local
```

`Status: ✔ Connected` แปลว่า Claude Code รัน server แล้วผ่าน `initialize` สำเร็จ (scope `local` = ใช้ได้เฉพาะโปรเจกต์นี้ของเราคนเดียว)

!!! note "caveat: `claude mcp list` ช้าบนเครื่องที่มี MCP เยอะ"
    `claude mcp list` health-check **ทุก** server ที่ตั้งไว้ บนเครื่องนี้มี server แบบ remote หลายตัว คำสั่งจึงหมดเวลา (60 วินาที) ก่อนจะแสดงผล ใช้ `claude mcp get <ชื่อ>` เพื่อดูตัวเดียวแทน

ลองให้ Claude ใช้ tool ของเรา (ครั้งนี้ใช้ `--mcp-config` ชี้ไฟล์ JSON เพื่อให้มีแค่ server นี้ และ `--tools ""` ปิด tool ในตัวทั้งหมด):

```sh
$ cat mcp.json
{"mcpServers": {"claude-lab": {"command": "python3", "args": ["~/github/claude-lab/labs/mcp_server/server.py"]}}}
$ claude -p "Use the claude-lab calculator tool to compute (120+80)*3/7, then answer with the number only." \
    --output-format stream-json --verbose --max-turns 3 \
    --mcp-config mcp.json --strict-mcp-config --tools "" \
    --allowedTools "mcp__claude-lab__calculator" --permission-mode dontAsk \
    --setting-sources project --disable-slash-commands --no-session-persistence \
    | python3 -m labs.trace
 1. init        tools=mcp__claude-lab__calculator,mcp__claude-lab__count_lines
 2. tool_use    mcp__claude-lab__calculator {"expression": "(120+80)*3/7"}
 3. tool_result [{"type": "text", "text": "85.71428571428571"}]
 4. text        85.71428571428571
 5. result      turns=2 in=4+cache7234 out=75 → 85.71428571428571
```

(ใน `mcp.json` จริงต้องเป็น path เต็ม — `~` ในที่นี้แทน path บ้านที่ถูก redact; fixture อยู่ที่ `labs/fixtures/mcp-calculator.jsonl`)

- tool จาก MCP ถูกตั้งชื่อเป็น **`mcp__<server>__<tool>`** เพื่อไม่ให้ชนกับ tool อื่น และใช้ชื่อนี้ใน `--allowedTools`
- `tools=` ใน init มีแค่ tool ของเราสองตัว — Claude Code เรียก `tools/list` แล้วแปลงเป็นรายการ tool ให้ model (รูปแบบเดียวกับ `Tool.schema()` ในบทที่ 2)
- input token น้อยกว่าบทที่ 3 (7,234 เทียบกับ 11,413) ทั้งที่ทั้งสองครั้งมี tool แค่ 2 ตัว — บทที่ 3 คือ `Bash` กับ `Read` ซึ่งมีคำอธิบายในตัวยาว ส่วนที่นี่คือ tool ของเราที่คำอธิบายสั้นบรรทัดเดียว คำอธิบาย tool ทุกตัวกิน context

ลบออกเมื่อเลิกใช้:

```sh
$ claude mcp remove claude-lab
Removed MCP server "claude-lab" from local config
File modified: ~/.claude.json [project: <cwd>]
```

## 5.5 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. เพิ่ม tool `word_count` (นับคำในไฟล์) ใน `TOOLS` ของ `server.py` เขียน test แบบ `test_tools_call_calculator` แล้วทดสอบด้วยการ pipe JSON
2. ใส่ `print("debug")` (ลง stdout) ใน `_tools_call` ชั่วคราว รัน `python3 -m unittest tests.test_mcp_server` ดูว่า test ไหนพังและทำไม แล้วเปลี่ยนเป็น `log("debug")`
3. ส่ง `{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"count_lines","arguments":{"path":"/nope"}}}` เข้า server ดูว่าได้ `result` หรือ `error` และอธิบายว่าทำไม

### เช็คความเข้าใจ

1. notification ต่างจาก request อย่างไร และทำไม server ห้ามตอบ notification
2. tool ที่คำนวณไม่ได้ ควรตอบเป็น JSON-RPC `error` หรือ `result` ที่ `isError: true` เพราะอะไร

## สรุปบทที่ 5

- MCP แบบ stdio = JSON-RPC 2.0 บรรทัดละข้อความ ผ่าน stdin/stdout ของ process ลูก
- server ที่มีแค่ tool ต้องรู้จัก `initialize`, `notifications/initialized`, `tools/list`, `tools/call`
- stdout สงวนไว้ให้ protocol — log ไป stderr; ข้อความเสียต้องไม่ทำให้ server ตาย
- tool error คือ `result` + `isError: true`; JSON-RPC `error` ใช้กับความผิดระดับ protocol
- `claude mcp add/get/remove` จัดการ server; tool ปรากฏต่อ model เป็น `mcp__<server>__<tool>`
