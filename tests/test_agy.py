"""Antigravity CLI (agy): scanned on PATH and in its usual install folders, its models as `agy models` lists them
(tab-separated id and display name), clear sign-in and proxy error messages, and one answer through an agent of our
own (`.agents/agents/textfold.md`: `inheritMcp: false`, `inheritCustomizations: false`, `tools: [finish]`) and
`--output-format stream-json`: the finish call's or the result's, the call ended once it is in. No model, no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from textfold import agents, llm, models

CLI = '''\
import json, os, sys, time
args = sys.argv[1:]
log = os.environ.get("FAKE_AGY_LOG")
if log:
    agent_md = ""
    p = os.path.join(os.getcwd(), ".agents", "agents", "textfold.md")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fp:
            agent_md = fp.read()
    stdin = sys.stdin.read() if "--output-format" in args else ""
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"args": args, "cwd": os.getcwd(), "stdin": stdin, "agent_md": agent_md, "pid": os.getpid()}) + "\\n")
def say(d):
    print(json.dumps(d), flush=True)
if "--version" in args:
    print("agy version 1.4.12")
elif "models" in args:
    if os.environ.get("FAKE_AGY_SIGNED_OUT"):
        sys.stderr.write("Error: You are not logged into Antigravity. Please sign in.\\n")
        sys.exit(1)
    if os.environ.get("FAKE_AGY_NET_ERR"):
        sys.stderr.write("Post https://daily-cloudcode-pa.googleapis.com: connectex: connection timed out\\n")
        sys.exit(1)
    print("gemini-3.8-flash-high\\tGemini 3.8 Flash (High)")
    print("gemini-3.8-flash-low\\tGemini 3.8 Flash (Low)")
    print("claude-sonnet-5-5-high\\tClaude Sonnet 5.5 (High)")
elif "--output-format" in args:
    mode = os.environ.get("FAKE_AGY_MODE", "")
    if mode == "signed-out":
        sys.stderr.write("Error: You are not logged into Antigravity.\\n")
        sys.exit(1)
    if mode == "error":
        say({"event": "result", "result": {"status": "ERROR", "error": "quota exhausted"}})
        sys.exit(1)
    if mode == "slow":   # (nothing yet: a Stop ends it)
        time.sleep(60)
    say({"event": "init", "conversation_id": "cid-1"})
    if mode == "text":   # the JSON as its reply, not by the finish tool
        say({"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": '{"takeaway": '}})
        say({"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": '"As text"}'}})
        say({"event": "result", "result": {"status": "SUCCESS"}})
        sys.exit(0)
    say({"event": "step_update", "step_update": {   # (the call under way: its parameters not yet in)
        "conversation_id": "cid-1", "step_index": 2, "state": "PENDING", "step_type": "tool", "tool_name": "finish",
        "tool_info": {"name": "finish", "parameters": {}}}})
    time.sleep(.6)
    say({"event": "step_update", "step_update": {
        "conversation_id": "cid-1", "step_index": 2, "state": "ACTIVE", "step_type": "tool", "tool_name": "finish",
        "tool_info": {"name": "finish", "parameters": {"takeaway": "Folded"}}}})
    if mode == "lingers":   # answered, then on with work of its own (a title), the result long after
        time.sleep(60)
    say({"event": "step_update", "step_update": {"conversation_id": "cid-1", "step_index": 2, "state": "DONE", "step_type": "finish"}})
    say({"event": "result", "result": {"conversation_id": "cid-1", "status": "SUCCESS", "structured_output": {"takeaway": "Folded"}}})
'''

SCHEMA = {"type": "object", "properties": {"takeaway": {"type": "string"}}, "required": ["takeaway"]}


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Agy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir(parents=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir(parents=True)
        self.cli = self.bin / ("agy.exe" if os.name == "nt" else "agy")
        self.script = self.tmp / "fake_agy.py"
        self.script.write_text(textwrap.dedent(CLI), encoding="utf-8")
        self.cli.write_text(f"#!{sys.executable}\n" + textwrap.dedent(CLI), encoding="utf-8")
        self.cli.chmod(0o755)
        self.log = self.tmp / "calls.jsonl"
        orig_argv = agents.argv

        def fake_argv(path):
            if Path(path) == self.cli:
                return [sys.executable, str(self.script)]
            return orig_argv(path)

        state = dict(agents.STATE)
        self.addCleanup(agents.STATE.update, state)
        for p in (mock.patch.object(agents, "HOME", self.home),
                  mock.patch.object(agents, "argv", side_effect=fake_argv),
                  mock.patch.object(agents, "path_of", return_value=str(self.cli)),
                  mock.patch.dict(os.environ, {"FAKE_AGY_LOG": str(self.log)})):
            p.start()
            self.addCleanup(p.stop)
        for k in ("FAKE_AGY_SIGNED_OUT", "FAKE_AGY_NET_ERR", "FAKE_AGY_MODE"):
            os.environ.pop(k, None)

    def calls(self):
        return [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def mode(self, m):
        return mock.patch.dict(os.environ, {"FAKE_AGY_MODE": m})

    def test_models_list_and_errors(self):
        got = agents._agy_models(str(self.cli))
        self.assertEqual([m["id"] for m in got], ["agy/gemini-3.8-flash-high", "agy/gemini-3.8-flash-low", "agy/claude-sonnet-5-5-high"])
        self.assertEqual((got[0]["name"], got[0]["model"], got[0]["efforts"]), ("Antigravity · Gemini 3.8 Flash (High)", "gemini-3.8-flash-high", []))
        with mock.patch.dict(os.environ, {"FAKE_AGY_SIGNED_OUT": "1"}), self.assertRaisesRegex(RuntimeError, "Antigravity CLI is not signed in"):
            agents._agy_models(str(self.cli))
        with mock.patch.dict(os.environ, {"FAKE_AGY_NET_ERR": "1"}), self.assertRaisesRegex(RuntimeError, "could not reach Google"):
            agents._agy_models(str(self.cli))

    def test_scan_and_resolve(self):
        with mock.patch.object(agents, "REGISTRY", [("agy", "Antigravity", "agy", [str(self.bin)], True)]), mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)
            row = agents.scan()["agents"][0]
        self.assertEqual((row["runtime"], row["label"], row["version"], row["error"]), ("agy", "Antigravity", "agy version 1.4.12", None))
        self.assertEqual(len(row["models"]), 3)
        spec = models.resolve("agy/gemini-3.8-flash-high", {"model": None})
        self.assertEqual((spec["kind"], spec["runtime"], spec["model"]), ("agent", "agy", "gemini-3.8-flash-high"))

    def test_an_agent_of_our_own_and_the_answer_by_finish(self):
        out, cost = agents.run_agy("gemini-3.8-flash-high", "Fold this.", SCHEMA, "The system. Answer with JSON only.", "off", 30)
        self.assertEqual((out, cost), ({"takeaway": "Folded"}, None))
        call = self.calls()[-1]
        args, md = call["args"], call["agent_md"]
        self.assertEqual(args[args.index("--agent") + 1], "textfold")
        self.assertEqual(args[args.index("--output-format") + 1], "stream-json")
        self.assertIn("--sandbox", args)
        self.assertNotIn("--effort", args)   # (the model's name sets its reasoning)
        for line in ("inheritMcp: false", "inheritCustomizations: false", "  - finish\n", "The system. Answer with JSON only.\n"):
            self.assertIn(line, md)
        self.assertNotIn("search_web", md)
        self.assertEqual(call["stdin"], "Fold this.")
        self.assertFalse(Path(call["cwd"]).exists())   # (its scratch directory, removed)

    def test_web_tools_when_asked(self):
        agents.run_agy("gemini-3.8-flash-low", "Look up.", SCHEMA, "System.", None, 30, tools=True)
        md = self.calls()[-1]["agent_md"]
        for tool in ("finish", "search_web", "read_url_content"):
            self.assertIn(f"  - {tool}\n", md)

    def test_a_reasoning_level_for_a_model_without_one_in_its_name(self):
        agents.run_agy("gemini-3.8-flash", "Fold.", SCHEMA, "Sys", "off", 30)
        agents.run_agy("gemini-3.8-flash", "Fold.", SCHEMA, "Sys", "high", 30)
        self.assertEqual([c["args"][c["args"].index("--effort") + 1] for c in self.calls()], ["low", "high"])

    def test_the_call_ends_once_finish_is_called(self):
        t0 = time.monotonic()
        with self.mode("lingers"):
            out, _ = agents.run_agy("gemini-3.8-flash-high", "Fold.", SCHEMA, "Sys", None, 60)
        self.assertEqual(out, {"takeaway": "Folded"})
        self.assertLess(time.monotonic() - t0, 20)   # (not the 60 s it goes on for)
        if os.name != "nt":
            pid = self.calls()[-1]["pid"]
            for _ in range(40):
                if not alive(pid):
                    break
                time.sleep(.05)
            self.assertFalse(alive(pid))

    def test_the_answer_as_its_reply(self):
        with self.mode("text"):
            out, _ = agents.run_agy("gemini-3.8-flash-high", "Fold.", SCHEMA, "Sys", None, 30)
        self.assertEqual(out, {"takeaway": "As text"})

    def test_errors_said_as_they_are(self):
        with self.mode("error"), self.assertRaisesRegex(RuntimeError, "agy error: quota exhausted"):
            agents.run_agy("gemini-3.8-flash-high", "Fold.", SCHEMA, "Sys", None, 30)
        with self.mode("signed-out"), self.assertRaisesRegex(RuntimeError, "Antigravity CLI is not signed in"):
            agents.run_agy("gemini-3.8-flash-high", "Fold.", SCHEMA, "Sys", None, 30)

    def test_stop_ends_it(self):
        stop = threading.Event()
        threading.Timer(1, stop.set).start()
        t0 = time.monotonic()
        with self.mode("slow"), llm.stoppable(stop), self.assertRaises(llm.Stopped):
            agents.run_agy("gemini-3.8-flash-high", "Fold.", SCHEMA, "Sys", None, 60)
        self.assertLess(time.monotonic() - t0, 20)

    def test_a_custom_agent_that_speaks_as_antigravity(self):
        spec = {"id": "custom/mine/gemini-3.8-flash-high", "kind": "agent", "runtime": "custom", "protocol": "agy",
                "command": "myagy", "agent": "Mine", "model": "gemini-3.8-flash-high", "effort": None}
        with mock.patch.object(agents, "command_of", return_value=([sys.executable, str(self.script)], str(self.cli))):
            out, _ = llm._once("Fold.", SCHEMA, spec, 30, "Sys")
        self.assertEqual(out, {"takeaway": "Folded"})
        self.assertIn("Antigravity", agents.PROTOCOLS.values())


if __name__ == "__main__":
    unittest.main()
