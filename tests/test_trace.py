import json
import pathlib
import re
import unittest

from labs.trace.redact import redact
from labs.trace.trace import summarize

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "labs" / "fixtures"
COUNT = FIXTURES / "count-lines.jsonl"


class TestSummarize(unittest.TestCase):
    def test_summarize_order(self):
        steps = summarize(COUNT.read_text().splitlines())
        kinds = [s.kind for s in steps]
        self.assertEqual(kinds[0], "init")
        self.assertEqual(kinds[-1], "result")
        i = kinds.index("tool_use")
        self.assertEqual(kinds[i + 1], "tool_result")
        self.assertIn("wc -l", steps[i].detail)
        self.assertIn("5", steps[i + 1].detail)
        self.assertIn("turns=2", steps[-1].detail)

    def test_unknown_event_ignored(self):
        steps = summarize(['{"type": "from_the_future", "x": 1}', '{"type": "result", "subtype": "success", "num_turns": 1, "result": "ok"}'])
        self.assertEqual([s.kind for s in steps], ["result"])

    def test_garbage_line_ignored(self):
        steps = summarize(["", "not json", "[1, 2]", '{"type": "result", "num_turns": 1, "result": "ok"}'])
        self.assertEqual(len(steps), 1)


class TestRedact(unittest.TestCase):
    HOME = "/home/alice"
    CWD = "/home/alice/work/demo"

    def r(self, event):
        out = redact(json.dumps(event), self.HOME, self.CWD)
        return None if out is None else json.loads(out)

    def test_redact_ids_and_paths(self):
        out = self.r({"type": "system", "subtype": "init", "session_id": "abc-123", "uuid": "u-1",
                      "cwd": self.CWD, "tools": ["Bash"], "model": "secret-model",
                      "plugins": [{"name": "private"}], "memory_paths": {"auto": "/home/alice/.claude/x"}})
        self.assertEqual(out["cwd"], "<cwd>")
        self.assertEqual(out["model"], "<model>")
        self.assertNotIn("plugins", out)
        self.assertNotIn("memory_paths", out)
        self.assertNotIn("abc-123", json.dumps(out))

    def test_redact_drops_rate_limit(self):
        self.assertIsNone(self.r({"type": "rate_limit_event", "rate_limit_info": {"utilization": 0.3}}))

    def test_redact_paths_inside_content(self):
        out = self.r({"type": "user", "session_id": "s", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t", "content": "/home/alice/work/demo/a.txt and /home/alice/b", "is_error": False}]}})
        text = out["message"]["content"][0]["content"]
        self.assertEqual(text, "<cwd>/a.txt and ~/b")

    def test_redact_hides_thinking(self):
        out = self.r({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "private chain", "signature": "sig"}]}})
        self.assertEqual(out["message"]["content"], [{"type": "thinking"}])


class TestFixturesRedacted(unittest.TestCase):
    def test_fixtures_redacted(self):
        files = sorted(FIXTURES.glob("*.jsonl"))
        self.assertTrue(files, "no fixtures")
        for path in files:
            text = path.read_text()
            for bad in ("/root", "/tmp/claude", "/home/", "rate_limit_info", "utilization", "credential_expires", "memory_paths", "claude-opus", "claude-sonnet"):
                self.assertNotIn(bad, text, f"{path.name} contains {bad!r}")
            self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), f"{path.name} has an email")
            for line in text.splitlines():
                ev = json.loads(line)
                self.assertNotIn("session_id", ev)
                self.assertNotIn("uuid", ev)
                self.assertNotEqual(ev.get("type"), "rate_limit_event", path.name)


if __name__ == "__main__":
    unittest.main()
