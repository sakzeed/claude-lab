"""Chapter 1 quotes three real `claude -p --output-format json` results.

This pins the numbers in docs/01-llm-basics.md to the redacted recording.
"""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "labs" / "fixtures" / "ch1-memory.jsonl"
LESSON = ROOT / "docs" / "01-llm-basics.md"


class TestChapter1Fixture(unittest.TestCase):
    def setUp(self):
        self.runs = [json.loads(line) for line in FIXTURE.read_text().splitlines()]

    def test_three_runs(self):
        self.assertEqual(len(self.runs), 3)
        first, fresh, resumed = self.runs
        self.assertEqual(first["result"], "OK")
        self.assertTrue(fresh["result"].startswith("I don't know"))
        self.assertEqual(resumed["result"], "7")

    def test_lesson_numbers_match_fixture(self):
        lesson = LESSON.read_text(encoding="utf-8")
        for run in self.runs:
            u = run["usage"]
            quoted = (f"'input_tokens': {u['input_tokens']}, 'cache_read_input_tokens': {u['cache_read_input_tokens']},")
            self.assertIn(quoted, " ".join(lesson.split()), f"lesson does not quote {quoted}")

    def test_resume_reads_first_prompt_from_cache(self):
        first, _, resumed = self.runs
        u = first["usage"]
        first_total = u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"]
        self.assertLessEqual(abs(resumed["usage"]["cache_read_input_tokens"] - first_total), 5)


if __name__ == "__main__":
    unittest.main()
