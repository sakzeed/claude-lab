import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "labs" / "plugin" / "zero-to-agent"
HOOK = PLUGIN / "hooks" / "log_tool.py"


def frontmatter(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def run_hook(event: dict, home: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": home}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, env=env, timeout=10)


class TestPlugin(unittest.TestCase):
    def test_manifest_json(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "zero-to-agent")
        self.assertTrue(manifest.get("description"))

    def test_referenced_paths_exist(self):
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
        mcp = json.loads((PLUGIN / ".mcp.json").read_text())
        commands = [h["command"] for groups in hooks["hooks"].values() for g in groups for h in g["hooks"]]
        commands += [" ".join([s["command"], *s.get("args", [])]) for s in mcp["mcpServers"].values()]
        for command in commands:
            for rel in [p.strip(chr(34)) for p in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"]+)", command)]:
                self.assertTrue((PLUGIN / rel).is_file(), f"missing {rel} referenced by {command!r}")

    def test_mcp_copy_in_sync(self):
        self.assertEqual((PLUGIN / "mcp" / "server.py").read_bytes(),
                         (ROOT / "labs" / "mcp_server" / "server.py").read_bytes(),
                         "run: cp labs/mcp_server/server.py labs/plugin/zero-to-agent/mcp/server.py")

    def test_skill_frontmatter(self):
        skills = list((PLUGIN / "skills").glob("*/SKILL.md"))
        self.assertTrue(skills)
        for path in skills:
            fm = frontmatter(path)
            self.assertEqual(fm.get("name"), path.parent.name)
            self.assertGreater(len(fm.get("description", "")), 20)

    def test_agent_frontmatter(self):
        agents = list((PLUGIN / "agents").glob("*.md"))
        self.assertTrue(agents)
        for path in agents:
            fm = frontmatter(path)
            self.assertEqual(fm.get("name"), path.stem)
            self.assertTrue(fm.get("description"))

    def test_hook_logs(self):
        with tempfile.TemporaryDirectory() as home:
            event = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                     "tool_input": {"command": "wc -l notes.txt"}, "session_id": "s", "cwd": "/x"}
            proc = run_hook(event, home)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            log = pathlib.Path(home, ".claude-lab", "tool-log.jsonl").read_text().splitlines()
            entry = json.loads(log[-1])
            self.assertEqual(entry["tool"], "Bash")
            self.assertEqual(entry["input"], {"command": "wc -l notes.txt"})
            self.assertNotIn("session_id", entry)

    def test_hook_blocks_rm_rf(self):
        with tempfile.TemporaryDirectory() as home:
            event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}
            proc = run_hook(event, home)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("rm -rf", proc.stderr)

    def test_hook_bad_input_does_not_block(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HOME": home}
            proc = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True,
                                  text=True, env=env, timeout=10)
            self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
