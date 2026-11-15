import os
import tempfile
import unittest

from labs.mini_agent.agent import AgentResult, ScriptedModel, Tool, run_agent
from labs.mini_agent.tools import calculator, count_lines


def ask(name, tool_input, tool_id="t1"):
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}],
    }


def say(text):
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}


def last_tool_result(result: AgentResult) -> dict:
    for msg in reversed(result.messages):
        if msg["role"] == "user" and isinstance(msg["content"], list):
            return msg["content"][0]
    raise AssertionError("no tool_result in messages")


class TestRunAgent(unittest.TestCase):
    def test_single_tool_round_trip(self):
        model = ScriptedModel([ask("calculator", {"expression": "6*7"}), say("ได้ 42")])
        result = run_agent(model, [calculator], "6 คูณ 7 เท่าไร")
        self.assertEqual(result.turns, 2)
        self.assertEqual(result.stopped, "end_turn")
        self.assertIn("42", result.final_text)
        tr = last_tool_result(result)
        self.assertEqual(tr["type"], "tool_result")
        self.assertEqual(tr["tool_use_id"], "t1")
        self.assertEqual(tr["content"], "42")
        self.assertFalse(tr["is_error"])

    def test_max_turns(self):
        model = ScriptedModel([ask("calculator", {"expression": "1+1"}, f"t{i}") for i in range(10)])
        result = run_agent(model, [calculator], "วนไปเรื่อย ๆ", max_turns=3)
        self.assertEqual(result.stopped, "max_turns")
        self.assertEqual(result.turns, 3)

    def test_unknown_tool_is_error_result(self):
        model = ScriptedModel([ask("rm_everything", {}), say("ขอโทษ ไม่มี tool นั้น")])
        result = run_agent(model, [calculator], "ลบทุกอย่าง")
        self.assertEqual(result.stopped, "end_turn")
        tr = last_tool_result(result)
        self.assertTrue(tr["is_error"])
        self.assertIn("rm_everything", tr["content"])

    def test_tool_exception_is_error_result(self):
        def boom(_):
            raise RuntimeError("disk on fire")

        broken = Tool("broken", "always fails", {"type": "object", "properties": {}}, boom)
        model = ScriptedModel([ask("broken", {}), say("tool พัง")])
        result = run_agent(model, [broken], "ลองดู")
        tr = last_tool_result(result)
        self.assertTrue(tr["is_error"])
        self.assertIn("disk on fire", tr["content"])

    def test_events_reported(self):
        seen = []
        model = ScriptedModel([ask("calculator", {"expression": "2+2"}), say("4")])
        run_agent(model, [calculator], "2+2", on_event=lambda kind, data: seen.append(kind))
        self.assertEqual(seen, ["model", "tool", "model"])

    def test_model_sees_tool_schemas(self):
        captured = {}

        class Spy(ScriptedModel):
            def respond(self, messages, tools):
                captured["tools"] = tools
                return super().respond(messages, tools)

        run_agent(Spy([say("hi")]), [calculator], "hi")
        self.assertEqual(captured["tools"][0]["name"], "calculator")
        self.assertIn("input_schema", captured["tools"][0])


class TestTools(unittest.TestCase):
    def test_calculator(self):
        self.assertEqual(calculator.run({"expression": "2*(3+4)"}), "14")
        self.assertEqual(calculator.run({"expression": "7/2"}), "3.5")
        self.assertEqual(calculator.run({"expression": "-3**2 % 5"}), "1")

    def test_calculator_rejects_names(self):
        for expr in ["__import__('os')", "x+1", "open('f')", "(1).real"]:
            with self.assertRaises(ValueError, msg=expr):
                calculator.run({"expression": expr})

    def test_calculator_rejects_huge_power(self):
        # 2**10**10 would run for minutes; the cap stops the obvious case (not every slow input)
        with self.assertRaises(ValueError):
            calculator.run({"expression": "2**10**10"})
        self.assertEqual(calculator.run({"expression": "2**10"}), "1024")

    def test_count_lines(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
            f.write("a\nb\nc\n")
        try:
            self.assertEqual(count_lines.run({"path": f.name}), "3")
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
