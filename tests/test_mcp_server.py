import json
import os
import pathlib
import subprocess
import sys
import unittest

SERVER = pathlib.Path(__file__).resolve().parent.parent / "labs" / "mcp_server" / "server.py"


def talk(*lines, timeout: float = 10, env=None) -> tuple[list[dict], str, str]:
    """Send raw lines (str or bytes) to a fresh server; return (replies, stdout, stderr)."""
    data = b"".join((l if isinstance(l, bytes) else l.encode()) + b"\n" for l in lines)
    proc = subprocess.run(
        [sys.executable, str(SERVER)], input=data, capture_output=True, timeout=timeout,
        env={**os.environ, **(env or {})},
    )
    proc.stdout, proc.stderr = proc.stdout.decode(), proc.stderr.decode(errors="replace")
    replies = [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]
    return replies, proc.stdout, proc.stderr


def req(id_, method, params=None):
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


INIT = req(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
INITIALIZED = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})


class TestMcpServer(unittest.TestCase):
    def test_initialize(self):
        (r,), _, _ = talk(INIT)
        self.assertEqual(r["id"], 1)
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(r["result"]["serverInfo"]["name"], "claude-lab")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_initialize_unknown_version_falls_back(self):
        (r,), _, _ = talk(req(1, "initialize", {"protocolVersion": "1999-01-01"}))
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")

    def test_tools_list(self):
        replies, _, _ = talk(INIT, INITIALIZED, req(2, "tools/list"))
        tools = {t["name"]: t for t in replies[-1]["result"]["tools"]}
        self.assertEqual(set(tools), {"calculator", "count_lines"})
        self.assertEqual(tools["calculator"]["inputSchema"]["required"], ["expression"])

    def test_tools_call_calculator(self):
        replies, _, _ = talk(INIT, req(2, "tools/call", {"name": "calculator", "arguments": {"expression": "6*7"}}))
        result = replies[-1]["result"]
        self.assertEqual(result["content"], [{"type": "text", "text": "42"}])
        self.assertFalse(result["isError"])

    def test_tool_error_is_result(self):
        replies, _, _ = talk(INIT, req(2, "tools/call", {"name": "calculator", "arguments": {"expression": "__import__('os')"}}))
        r = replies[-1]
        self.assertNotIn("error", r)
        self.assertTrue(r["result"]["isError"])

    def test_huge_power_is_error_not_hang(self):
        replies, _, _ = talk(INIT, req(2, "tools/call", {"name": "calculator", "arguments": {"expression": "9**9**9"}}), timeout=5)
        self.assertTrue(replies[-1]["result"]["isError"])

    def test_unknown_tool_is_invalid_params(self):
        replies, _, _ = talk(INIT, req(2, "tools/call", {"name": "nope", "arguments": {}}))
        self.assertEqual(replies[-1]["error"]["code"], -32602)

    def test_unknown_method(self):
        replies, _, _ = talk(INIT, req(2, "resources/list"))
        self.assertEqual(replies[-1]["error"]["code"], -32601)

    def test_parse_error_keeps_running(self):
        replies, _, _ = talk("this is not json", req(5, "ping"))
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertIsNone(replies[0]["id"])
        self.assertEqual(replies[1], {"jsonrpc": "2.0", "id": 5, "result": {}})

    def test_bad_params_keep_running(self):
        replies, _, _ = talk(
            req(1, "tools/call", ["not", "an", "object"]),
            req(2, "tools/call", {"name": "calculator", "arguments": "2+2"}),
            req(3, "ping"),
        )
        self.assertEqual(replies[0]["error"]["code"], -32602)
        self.assertEqual(replies[1]["error"]["code"], -32602)
        self.assertEqual(replies[2]["result"], {})

    def test_deeply_nested_json_keeps_running(self):
        replies, _, _ = talk("[" * 200000, req(6, "ping"))
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[-1]["id"], 6)

    def test_invalid_utf8_keeps_running(self):
        replies, _, _ = talk(b"\xff\xfe not utf-8", req(7, "ping"), env={"PYTHONIOENCODING": "utf-8:strict"})
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[-1]["id"], 7)

    def test_huge_result_is_error_not_hang(self):
        replies, _, _ = talk(INIT, req(2, "tools/call", {"name": "calculator", "arguments": {"expression": "(((9**99)**99)**99)**99"}}), timeout=5)
        self.assertTrue(replies[-1]["result"]["isError"])

    def test_count_lines_special_file_is_error(self):
        replies, _, _ = talk(INIT, req(2, "tools/call", {"name": "count_lines", "arguments": {"path": "/dev/zero"}}), timeout=5)
        self.assertTrue(replies[-1]["result"]["isError"])

    def test_invalid_request(self):
        replies, _, _ = talk(
            "[1, 2, 3]",                                            # batch / not an object
            json.dumps({"jsonrpc": "2.0", "id": 8}),                # no method
            json.dumps({"jsonrpc": "2.0", "id": 9, "method": 42}),  # method not a string
            req(10, "ping"),
        )
        self.assertEqual([r["error"]["code"] for r in replies[:3]], [-32600, -32600, -32600])
        self.assertEqual([r["id"] for r in replies[:3]], [None, 8, 9])
        self.assertEqual(replies[3]["result"], {})

    def test_notification_no_reply(self):
        replies, _, _ = talk(INITIALIZED)
        self.assertEqual(replies, [])

    def test_stdout_only_jsonrpc(self):
        _, stdout, stderr = talk(INIT, INITIALIZED, req(2, "tools/list"), "garbage", req(3, "ping"))
        for line in stdout.splitlines():
            self.assertEqual(json.loads(line)["jsonrpc"], "2.0")
        self.assertIn("claude-lab", stderr)  # logs go to stderr


if __name__ == "__main__":
    unittest.main()
