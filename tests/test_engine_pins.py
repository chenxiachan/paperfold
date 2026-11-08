"""The PDF engine's libraries that MinerU allows to move on are kept where it converts (#107: docvortex 0.6 changed
what MinerU 4.0.10 calls). A new engine installs them pinned; one installed before, with a later version, has it put
back once, before a conversion; one with an earlier version is left as it is.

Everything is in a temporary folder and nothing is installed or run: the engine's commands are stubbed.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import engine


def site(e):
    lib = e / "venv" / ("Lib" if sys.platform == "win32" else "lib")
    s = lib / "site-packages" if sys.platform == "win32" else lib / "python3.12" / "site-packages"
    s.mkdir(parents=True, exist_ok=True)
    return s


def has(e, name, version):
    for d in site(e).glob(f"{name}-*.dist-info"):
        d.rmdir()
    (site(e) / f"{name}-{version}.dist-info").mkdir()


class Pins(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.e = Path(t.name) / "engine"

    def test_a_new_engine_installs_them_pinned_and_says_so(self):
        with mock.patch.object(engine, "target", return_value=self.e), mock.patch.object(engine, "_record"), \
                mock.patch.object(engine, "_uv", return_value="uv"), mock.patch.object(engine, "_run") as run, \
                mock.patch.object(engine, "status", return_value={}):
            engine.install()
        packages = next(c.args[0] for c in run.call_args_list if f"mineru=={engine.VERSION}" in c.args[0])
        self.assertIn("docvortex==0.5.16", packages)
        self.assertIn("docvortex==0.5.16", (self.e / engine.MARK).read_text(encoding="utf-8"))

    def test_a_later_version_is_put_back_and_an_earlier_one_left(self):
        has(self.e, "docvortex", "0.6.13")
        self.assertEqual(engine._past_pins(self.e), ["docvortex==0.5.16"])
        for version in ("0.5.10", "0.5.16", "0.5.18"):
            has(self.e, "docvortex", version)
            self.assertEqual(engine._past_pins(self.e), [], version)

    def test_put_back_before_a_conversion(self):
        has(self.e, "docvortex", "0.6.20")
        calls = []

        def run(cmd, *a, **k):
            calls.append([str(x) for x in cmd])
            if "parse" in calls[-1]:
                raise RuntimeError("stop here")   # (the conversion itself: not what this test is about)
        with mock.patch.object(engine, "where", return_value=self.e), mock.patch.object(engine, "_uv", return_value="uv"), \
                mock.patch.object(engine, "_run", side_effect=run):
            with self.assertRaisesRegex(RuntimeError, "stop here"):
                engine.convert("a.pdf", self.e.parent / "out")
        self.assertEqual(calls[0][:3], ["uv", "pip", "install"])
        self.assertIn("docvortex==0.5.16", calls[0])
        self.assertIn("parse", calls[1])

    def test_not_reachable_the_conversion_goes_on(self):
        has(self.e, "docvortex", "0.6.20")
        seen, lines = [], []

        def run(cmd, *a, **k):
            seen.append(cmd)
            if "install" in [str(x) for x in cmd]:
                raise RuntimeError("uv exited with 2")
            raise RuntimeError("stop here")   # (the conversion itself: not what this test is about)
        with mock.patch.object(engine, "where", return_value=self.e), mock.patch.object(engine, "_uv", return_value="uv"), \
                mock.patch.object(engine, "_run", side_effect=run):
            with self.assertRaisesRegex(RuntimeError, "stop here"):
                engine.convert("a.pdf", self.e.parent / "out", log=lines.append)
        self.assertEqual(len(seen), 2)
        self.assertTrue(any("could not install docvortex==0.5.16" in l for l in lines))


if __name__ == "__main__":
    unittest.main()
