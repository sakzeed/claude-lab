# บทที่ 7: hooks — โค้ดของเราที่รันทุกครั้ง ไม่ต้องให้ model ตัดสิน

tool, subagent และ skill ล้วนเป็นสิ่งที่ **model เลือก** ว่าจะใช้หรือไม่ (บทที่ 6) แต่บางเรื่องเราไม่อยากให้ขึ้นกับการตัดสินใจของ model เลย เช่น "ห้าม `rm -rf` เด็ดขาด" หรือ "log ทุกคำสั่งที่รัน" — **hook** คือโปรแกรมของเราที่ Claude Code รัน **ทุกครั้ง** ที่เกิดเหตุการณ์ที่กำหนด

hook ของบทนี้อยู่ที่ `labs/plugin/zero-to-agent/hooks/`

---

## 7.1 hook ทำงานตรงไหนของลูป

ย้อนกลับไปที่ลูปในบทที่ 3: ระหว่าง "model ขอ tool" กับ "รัน tool" Claude Code จะเรียก hook ชนิด **`PreToolUse`** ก่อน:

```text
model ← tool_use (Bash: rm -rf old-build)
          │
          ▼
   PreToolUse hook  ── exit 2 ──▶ ไม่รัน, ส่งเหตุผลกลับให้ model เป็น tool_result (error)
          │ exit 0
          ▼
   permission check ── ไม่อนุญาต ─▶ ไม่รัน, ส่งเหตุผลกลับ
          │ อนุญาต
          ▼
      รัน tool จริง  ──▶ tool_result
```

event อื่นที่ hook ผูกได้ เช่น `PostToolUse` (หลังรัน tool), `UserPromptSubmit` (ตอนผู้ใช้ส่งข้อความ), `SessionStart`, `Stop` — บทนี้ใช้แค่ `PreToolUse`

## 7.2 ตั้งค่า: `hooks.json`

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/log_tool.py\"" }
        ]
      }
    ]
  }
}
```

- `matcher` — ชื่อ tool ที่จะเรียก hook (ที่นี่เฉพาะ `Bash`)
- `command` — คำสั่ง shell ที่จะรัน; `${CLAUDE_PLUGIN_ROOT}` คือโฟลเดอร์ของ plugin และ **ต้องใส่ quote** ครอบ (ถ้า path มีช่องว่าง คำสั่งจะแตก — `claude plugin validate` เตือนเรื่องนี้)
- hook แบบเดียวกันนี้ใส่ใน `.claude/settings.json` ของโปรเจกต์ได้ด้วย (key `"hooks"` เหมือนกัน) — บทนี้ใส่ใน plugin เพื่อใช้ต่อในบทที่ 8

## 7.3 hook คือโปรแกรมธรรมดา

Claude Code ส่ง event เป็น JSON ทาง **stdin** แล้วดู **exit code**:

| exit code | ผล |
|---|---|
| `0` | อนุญาต ทำงานต่อ |
| `2` | **บล็อก** — ข้อความใน stderr ถูกส่งให้ model เป็นเหตุผล |
| อื่น ๆ | error ที่ไม่บล็อก (แสดงเป็นคำเตือน) |

```python
# rm with both -r/-R and -f in one flag group, in any order: -rf -fr -Rf -rfv ...
RM_RF = re.compile(r"\brm\s+-(?=[a-zA-Z]*[rR])(?=[a-zA-Z]*f)[a-zA-Z]+")


def blocked(tool: str, tool_input: dict) -> bool:
    command = tool_input.get("command", "") if tool == "Bash" else ""
    return isinstance(command, str) and bool(RM_RF.search(command))


def log(tool: str, tool_input: dict) -> None:
    try:
        log_dir = pathlib.Path.home() / ".claude-lab"
        log_dir.mkdir(exist_ok=True)
        entry = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "tool": tool, "input": tool_input}
        with open(log_dir / "tool-log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"zero-to-agent hook: could not write log: {exc}", file=sys.stderr)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # never block on input we do not understand
    if not isinstance(event, dict):
        return 0
    tool = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if blocked(tool, tool_input):
        log(tool, tool_input)
        print("zero-to-agent hook: blocked `rm -rf` — delete files one by one or ask the user", file=sys.stderr)
        return 2
    log(tool, tool_input)
    return 0
```

ลำดับสำคัญ: **ตรวจก่อน log** และ log ที่เขียนไม่ได้ (ดิสก์เต็ม, `HOME` เขียนไม่ได้) ต้องไม่ทำให้การบล็อกหลุด — ถ้า hook crash จะได้ exit code อื่นที่ไม่ใช่ 2 ซึ่ง Claude Code ถือว่า "error ที่ไม่บล็อก" แล้วรันคำสั่งต่อ guardrail ที่พังแล้วปล่อยผ่าน (fail open) ไม่ใช่ guardrail (test `test_hook_blocks_even_if_log_fails`)

เพราะเป็นโปรแกรมธรรมดา จึงทดสอบได้โดยไม่ต้องมี Claude เลย:

```sh
$ echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"wc -l notes.txt"}}' \
    | python3 labs/plugin/zero-to-agent/hooks/log_tool.py; echo "exit=$?"
exit=0
$ echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf build"}}' \
    | python3 labs/plugin/zero-to-agent/hooks/log_tool.py; echo "exit=$?"
zero-to-agent hook: blocked `rm -rf` — delete files one by one or ask the user
exit=2
$ cat ~/.claude-lab/tool-log.jsonl
{"time": "2026-11-15T14:37:06", "tool": "Bash", "input": {"command": "wc -l notes.txt"}}
{"time": "2026-11-15T14:37:06", "tool": "Bash", "input": {"command": "rm -rf build"}}
```

(test `test_hook_logs`, `test_hook_blocks_rm_rf`, `test_hook_bad_input_does_not_block` ทำแบบเดียวกันโดยตั้ง `HOME` ชั่วคราว)

!!! warning "hook รันด้วยสิทธิ์ของคุณเต็ม ๆ"
    hook ไม่ได้อยู่ใน sandbox — มันคือคำสั่งที่รันบนเครื่องคุณทุกครั้งที่เกิด event ติดตั้ง plugin ที่มี hook จากคนอื่นจึงเท่ากับยอมให้โค้ดของเขารันบนเครื่อง อ่าน `hooks.json` และสคริปต์ก่อนเสมอ

    hook ตัวนี้ยังเก็บ **ทุกคำสั่ง Bash** ไว้ใน `~/.claude-lab/tool-log.jsonl` แบบไม่มีวันหมดอายุ — ถ้าเคยพิมพ์ token หรือรหัสผ่านไว้ในคำสั่ง มันจะอยู่ในไฟล์นี้ด้วย ลบไฟล์เมื่อเลิกทดลอง

## 7.4 hook ทำงานจริงใน session

สั่งให้ Claude นับบรรทัดผ่าน subagent ของ plugin แล้วลบโฟลเดอร์ด้วย `rm -rf` (โหลด plugin ด้วย `--plugin-dir`, fixture: `labs/fixtures/agent-hook.jsonl`)

!!! warning "ลองในโฟลเดอร์ทิ้งได้เท่านั้น"
    คำสั่งนี้อนุญาต `Bash(rm *)` ถ้า path ใน `--plugin-dir` ผิด (เช่น clone ไว้ที่อื่น) plugin จะไม่ถูกโหลด และ `rm -rf old-build` จะ **รันจริง** — ใช้ path ที่ clone ไว้จริงของคุณ และรันในโฟลเดอร์ทดลองที่ไม่มีอะไรสำคัญ

```sh
$ claude -p "First use the file-stats subagent to count lines in the .txt files here. Then delete the old-build folder with: rm -rf old-build" \
    --output-format stream-json --verbose --max-turns 6 \
    --plugin-dir ~/github/claude-lab/labs/plugin/zero-to-agent \
    --strict-mcp-config --setting-sources project --permission-mode dontAsk \
    --allowedTools "Agent" "Task" "Glob" "Read" "Bash(wc *)" "Bash(rm *)" --no-session-persistence \
    | python3 -m labs.trace
 ...
 9. text        The user explicitly asked to delete it; look at target first briefly.
10. tool_use    Bash {"command": "ls -la old-build && rm -rf old-build && ls", ...}
11. tool_result PreToolUse:Bash hook error: [python3 "~/github/claude-lab/labs/plugin/zero-to-agent/hooks/log_tool.… (error)
12. thinking    (hidden)
13. tool_use    Bash {"command": "find old-build", "description": "List everything inside old-build"}
14. tool_result old-build
15. thinking    (hidden)
16. text        It's an empty directory, so `rmdir` removes it without needing `rm -rf`.
17. tool_use    Bash {"command": "rmdir old-build && ls", ...}
18. tool_result Permission to use Bash has been denied because Claude Code is running in don't ask mode. ... (error)
 ...
```

ข้อความเต็มที่ model ได้รับในขั้น 11 (บันทึกก่อนที่ข้อความของ hook จะเปลี่ยนจาก `claude-lab hook` เป็น `zero-to-agent hook`):

```text
PreToolUse:Bash hook error: [python3 "~/github/claude-lab/labs/plugin/zero-to-agent/hooks/log_tool.py"]: claude-lab hook: blocked `rm -rf` — delete files one by one or ask the user

This hook comes from the zero-to-agent@inline plugin.
```

สิ่งที่เห็นจากเครื่องจริง:

- **`"Bash(rm *)"` อยู่ใน `--allowedTools` แต่ก็ยังถูกบล็อก** — hook รันก่อนและบล็อกได้แม้ permission จะอนุญาต นี่คือความต่างระหว่าง "model/การตั้งค่าอนุญาต" กับ "โค้ดของเราที่รันทุกครั้ง"
- **stderr ของ hook กลายเป็นเหตุผลที่ model อ่าน** — model จึงหาทางอื่น (`rmdir`) ซึ่งไปติด **permission** อีกชั้น (`rmdir` ไม่อยู่ใน allowedTools และโหมด `dontAsk` ไม่ถามผู้ใช้)
- model จบงานด้วยการรายงานตามจริงว่าลบไม่ได้เพราะอะไร แทนที่จะพยายามหาทางเลี่ยงต่อ

และ hook log ทุก Bash call — **รวมถึงของ subagent** ด้วย (บรรทัดแรกมาจาก subagent `file-stats`):

```text
{"time": "2026-11-15T14:32:17", "tool": "Bash", "input": {"command": "wc -l notes.txt todo.txt raw/err.txt", "description": "Count lines in the txt files"}}
{"time": "2026-11-15T14:32:27", "tool": "Bash", "input": {"command": "ls -la old-build && rm -rf old-build && ls", "description": "Show old-build contents, delete it, list remaining files"}}
{"time": "2026-11-15T14:32:33", "tool": "Bash", "input": {"command": "find old-build", "description": "List everything inside old-build"}}
{"time": "2026-11-15T14:32:38", "tool": "Bash", "input": {"command": "rmdir old-build && ls", "description": "Remove empty old-build directory and list remaining"}}
```

!!! note "hook ไม่ใช่กำแพงที่สมบูรณ์"
    regex ของเราจับ `rm -rf`, `rm -fr`, `rm -Rf`, `rm -rfv` แต่ไม่จับ `rm -r -f`, `rm --recursive --force`, `find . -delete` หรือ Python ที่ลบไฟล์ hook ที่ดีจึงใช้เป็น "ราวกันตก" ร่วมกับ permission ไม่ใช่ใช้แทน

## 7.5 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. ขยาย regex ให้บล็อก `rm -r -f` ด้วย เขียน test `test_hook_blocks_split_flags` ให้ fail ก่อนแล้วค่อยแก้
2. เขียน hook `PostToolUse` ที่ append ความยาวของ output (`tool_response`) ลง log แล้วทดสอบด้วยการ pipe JSON เข้าไปเอง
3. เพิ่ม hook ใน `.claude/settings.json` ของโปรเจกต์ทดลอง (ไม่ใช่ plugin) ที่บล็อกการแก้ไฟล์ `*.env` ด้วย matcher `Edit|Write` แล้วลองสั่ง `claude -p` ให้แก้ `.env`

### เช็คความเข้าใจ

1. hook ต่างจาก skill อย่างไรในแง่ "ใครเป็นคนตัดสินใจว่าจะทำงาน"
2. ในตัวอย่าง 7.4 `rm -rf` ถูกบล็อกโดย hook ส่วน `rmdir` ถูกบล็อกโดย permission — อธิบายว่าแต่ละอย่างตรวจที่ขั้นไหนของลูป

## สรุปบทที่ 7

- hook = โปรแกรมของเราที่ Claude Code รันทุกครั้งที่เกิด event (เช่น `PreToolUse`) model เลี่ยงไม่ได้
- รับ event เป็น JSON ทาง stdin; exit `0` อนุญาต, exit `2` บล็อกและส่ง stderr ให้ model เป็นเหตุผล
- hook รันก่อน permission และบล็อกได้แม้ allowedTools จะอนุญาต — ทำงานกับ tool call ของ subagent ด้วย
- hook รันด้วยสิทธิ์ของผู้ใช้เต็ม ๆ — อ่านก่อนติดตั้งเสมอ และใช้เป็นราวกันตกร่วมกับ permission
