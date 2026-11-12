"""What an agent on this computer hands back, read whatever its own settings make of it (#130).

Claude Code with Verbose output on (its user's /config, a setting the scratch folder and --setting-sources leave
on) prints every message of a claude -p run, the result last, where it otherwise prints the result alone: both are
read. And the scratch folder an agent runs in is removed after its call where it can be: on Windows a process that
still has it as its working directory keeps it there (WinError 32), and that left the call's own outcome unread,
its reply or its error. The commands are looked at, not run: no agent and no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from textfold import agents, llm

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
SPEC = {"kind": "agent", "model": "m"}


def ask(runtime, run):
    with mock.patch.object(agents, "path_of", lambda r: f"/bin/{r}"), mock.patch.object(agents, "argv", lambda p: [p]), \
         mock.patch("subprocess.run", run), mock.patch.object(agents, "child_env", lambda: {}):
        return llm._once("Say ok.", SCHEMA, {**SPEC, "runtime": runtime, "id": f"x/{runtime}/m"}, 60, "You answer with JSON only.")


def claude_prints(got):
    return lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(got), stderr="")


VERBOSE = [{"type": "system", "subtype": "init", "model": "m"},
           {"type": "assistant", "message": {"content": [{"type": "text", "text": "…"}]}}]


class ClaudeVerbose(unittest.TestCase):
    def test_the_result_alone(self):
        got = {"type": "result", "is_error": False, "structured_output": {"ok": True}, "total_cost_usd": 0.02}
        self.assertEqual(ask("claude-code", claude_prints(got)), ({"ok": True}, 0.02))

    def test_every_message_the_result_last(self):
        got = VERBOSE + [{"type": "result", "is_error": False, "structured_output": {"ok": True}, "total_cost_usd": 0.02}]
        self.assertEqual(ask("claude-code", claude_prints(got)), ({"ok": True}, 0.02))

    def test_its_error_is_its_own(self):
        got = VERBOSE + [{"type": "result", "is_error": True, "result": "API Error: 529 overloaded"}]
        with self.assertRaisesRegex(RuntimeError, "claude -p error: API Error: 529"):
            ask("claude-code", claude_prints(got))

    def test_no_result_says_so(self):
        with self.assertRaisesRegex(RuntimeError, "claude -p: no result"):
            ask("claude-code", claude_prints(VERBOSE))


class Scratch(unittest.TestCase):
    """The folder stays where Windows would not remove it: rmtree as it is there, while a process is in it."""
    def setUp(self):
        self.left = []
        real = shutil.rmtree

        def windows(path, ignore_errors=False, **kw):
            self.left.append(path)
            if not ignore_errors:
                raise PermissionError(13, "[WinError 32] The process cannot access the file because it is being used by another process", path)

        p = mock.patch.object(agents.shutil, "rmtree", windows)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(lambda: [real(x, ignore_errors=True) for x in self.left])

    def test_codex_its_reply_read(self):
        def codex(cmd, **kw):
            Path(cmd[cmd.index("-o") + 1]).write_text('{"ok": true}', encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        self.assertEqual(ask("codex", codex), ({"ok": True}, None))
        self.assertEqual(len(self.left), 1)

    def test_codex_its_own_error(self):
        def late(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 900)
        with self.assertRaises(subprocess.TimeoutExpired):   # (where it read WinError 32)
            ask("codex", late)

    def test_claude_code_its_reply_read(self):
        got = {"type": "result", "is_error": False, "structured_output": {"ok": True}, "total_cost_usd": 0}
        self.assertEqual(ask("claude-code", claude_prints(got)), ({"ok": True}, 0))
        self.assertEqual(len(self.left), 1)


if __name__ == "__main__":
    unittest.main()
