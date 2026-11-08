"""Stop ends an agent's call under way (agents.run): its whole process tree, at once, for every agent TextFold drives;
what that call had written is lost and nothing of it is cached. Without a stop a call runs as subprocess.run (#70).
No model, no network: a script that starts a child of its own and sleeps.

Run from the repo root:
    python3 -m unittest discover tests
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ladder_parts import CFG, Model   # noqa: E402
from textfold import agents, ladder, llm, local, store   # noqa: E402

# a parent that starts a child of its own (an agent's node, its sandbox), writes the child's pid, and both sleep
TREE = '''\
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open(sys.argv[1], "w").write(str(child.pid))
time.sleep(60)
'''


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class AgentRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "tree.py").write_text(TREE, encoding="utf-8")
        self.pidfile = self.tmp / "child.pid"

    def tree(self):
        return [sys.executable, str(self.tmp / "tree.py"), str(self.pidfile)]

    def stop_when_started(self, stop):
        def watch():
            for _ in range(200):
                if self.pidfile.exists() and self.pidfile.read_text():
                    break
                time.sleep(.05)
            stop.set()
        threading.Thread(target=watch, daemon=True).start()

    def test_stop_ends_the_call_and_the_processes_it_started(self):
        stop = threading.Event()
        self.stop_when_started(stop)
        t0 = time.monotonic()
        with self.assertRaises(llm.Stopped):
            agents.run(self.tree(), input="the prompt", capture_output=True, text=True, timeout=60, stop=stop)
        self.assertLess(time.monotonic() - t0, 20)   # (not the 60 s the call sleeps)
        if os.name != "nt":   # (Windows: taskkill /T, not checked here)
            child = int(self.pidfile.read_text())
            for _ in range(40):
                if not alive(child):
                    break
                time.sleep(.05)
            self.assertFalse(alive(child), "the agent's own child outlived the stop")

    def test_the_thread_s_stop_reaches_a_call_made_without_one(self):
        stop = threading.Event()
        self.stop_when_started(stop)
        with llm.stoppable(stop), self.assertRaises(llm.Stopped):
            agents.run(self.tree(), capture_output=True, text=True, timeout=60)
        self.assertIsNone(llm.stop_now())   # (and only within it)

    def test_stopped_before_it_starts_it_does_not_start(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(llm.Stopped):
            agents.run(self.tree(), capture_output=True, text=True, timeout=60, stop=stop)
        self.assertFalse(self.pidfile.exists())

    def test_a_call_that_is_not_stopped_returns_as_subprocess_run_does(self):
        # (an agent reads and writes UTF-8, whatever the locale: the test's runs in Latin-1 too)
        echo = [sys.executable, "-c", "import sys; s = sys.stdin.buffer.read().decode('utf-8'); "
                "sys.stdout.buffer.write(s.upper().encode('utf-8')); sys.stderr.write('note'); sys.exit(3)"]
        for stop in (None, threading.Event()):
            r = agents.run(echo, input="héllo", capture_output=True, text=True, encoding="utf-8", timeout=30, stop=stop)
            self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (3, "HÉLLO", "note"), stop)

    def test_a_timeout_still_ends_it(self):
        with self.assertRaises(__import__("subprocess").TimeoutExpired):
            agents.run(self.tree(), capture_output=True, text=True, timeout=1, stop=threading.Event())


class CallStopped(unittest.TestCase):
    """llm.call: a stopped call is not cached, and is not asked again without its reasoning level (as a failed one is)."""

    def test_not_cached_not_retried(self):
        asked = []

        def once(prompt, schema, spec, timeout, system):
            asked.append(spec.get("effort"))
            raise llm.Stopped()

        spec = {"id": "x/y/z", "kind": "agent", "runtime": "codex", "model": "z", "effort": "high"}
        with tempfile.TemporaryDirectory() as cache, mock.patch.object(llm, "_once", once), \
                mock.patch.object(llm, "spec_of", lambda m: m), mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)
            with self.assertRaises(llm.Stopped):
                llm.call("Fold this.", {"type": "object"}, spec, Path(cache))
            self.assertEqual(list(Path(cache).iterdir()), [])
        self.assertEqual(asked, ["high"])


class ReachesTheCalls(unittest.TestCase):
    """A generation's stop is the one its model calls are made under, the parts of a long section and its own line too."""

    def test_ladder(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(store, "DATA", Path(tmp) / "data"):
            long = "\n\n".join(f"Row {k} reads a value of its own." for k in range(60))
            pid = local.import_text(f"# A book\n\n## Long\n\n{long}\n\n## Short\n\nOne line here.\n")
            stop, seen, model = threading.Event(), [], Model()

            def call(*a, **kw):
                seen.append(llm.stop_now())
                return model(*a, **kw)

            with mock.patch.object(llm, "call", call):
                ladder.build(store.assemble(pid), CFG, Path(tmp) / "cache", jobs=3, log=lambda *a: None, stop=stop)
        self.assertGreaterEqual(len(seen), 3)   # (the long section's parts, its line, the short one)
        self.assertTrue(all(s is stop for s in seen))
        self.assertIsNone(llm.stop_now())


if __name__ == "__main__":
    unittest.main()
