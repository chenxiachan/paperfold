"""A reply kept on disk is read back only when it is a reply.

A process that died in the middle of writing one left half a file, and every generation after it read that half:
json.loads raised, the section it belonged to fell back to a local ladder, and only deleting the file by hand asked the
model again. The reply is now written whole, and a file that is not a reply is dropped and asked for again.

A model stands in for one, a cache folder of its own; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import llm

SPEC = {"id": "fake/model", "kind": "api", "protocol": "openai", "base": "http://127.0.0.1:9", "api_key": "", "model": "fake"}
SCHEMA = {"type": "object", "properties": {"out": {"type": "array"}}, "required": ["out"]}


class Cache(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache = Path(tmp.name) / "llm-cache"

    def ask(self, out, **kw):
        """One call, answered by a stand-in model that gives out: (reply, cached, times the model was asked)."""
        asked = []

        def once(prompt, schema, spec, timeout, system):
            asked.append(prompt)
            return out, 0

        with mock.patch.object(llm, "_once", once), mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)   # (the build runs the tests with it: the model here is a stand-in)
            rec, cached = llm.call("a prompt", SCHEMA, SPEC, self.cache, **kw)
        return rec, cached, len(asked)

    def files(self, suffix=".json"):
        return sorted(p for p in self.cache.iterdir() if p.suffix == suffix) if self.cache.exists() else []

    def test_a_reply_kept_is_read_back_without_asking(self):
        first, cached, asked = self.ask({"links": [1]})
        self.assertEqual((cached, asked), (False, 1))
        again, cached, asked = self.ask({"links": [2]})
        self.assertEqual((cached, asked), (True, 0))
        self.assertEqual(again["out"], {"links": [1]})   # (the reply kept, not the model's second answer)
        self.assertEqual(again["file"], first["file"])

    def test_a_reply_half_written_when_the_process_died_is_asked_again(self):
        first, _, _ = self.ask({"links": [1]})
        whole = Path(first["file"]).read_bytes()
        Path(first["file"]).write_bytes(whole[:len(whole) // 2])
        again, cached, asked = self.ask({"links": [2]})
        self.assertEqual((cached, asked), (False, 1))
        self.assertEqual(again["out"], {"links": [2]})
        self.assertEqual(json.loads(Path(first["file"]).read_text(encoding="utf-8"))["out"], {"links": [2]})   # (in its place)
        self.assertEqual(self.ask({"links": [3]})[1:], (True, 0))   # (and it is a reply again)

    def test_a_file_that_is_no_reply_at_all_is_dropped(self):
        first, _, _ = self.ask({"links": [1]})
        path, reply = Path(first["file"]), Path(first["file"]).read_bytes()
        for nothing in (b"", b'{"hello": 1}', b"[1, 2]", b'{"cost": 0}'):
            path.write_bytes(nothing)
            again, cached, asked = self.ask({"links": [2]})
            self.assertEqual((cached, asked, again["out"]), (False, 1, {"links": [2]}), nothing)
            path.write_bytes(reply)

    def test_the_reply_is_written_whole(self):
        self.ask({"links": [1]})
        self.assertEqual(len(self.files()), 1)
        self.assertEqual(self.files(".tmp"), [])   # (nothing half written is left beside it)

    def test_a_write_that_dies_leaves_the_reply_before_it_readable(self):
        first, _, _ = self.ask({"links": [1]})
        with mock.patch.object(llm.os, "replace", side_effect=OSError("no space left")):
            with self.assertRaises(OSError):
                self.ask({"links": [2]}, force=True)
        again, cached, asked = self.ask({"links": [3]})
        self.assertEqual((cached, asked, again["out"]), (True, 0, first["out"]))


if __name__ == "__main__":
    unittest.main()
