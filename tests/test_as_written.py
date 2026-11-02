"""A unit that is no passage of the text stays as written (reported on a PDF read by the engine's fast tier: its
"Keywords:", its "1. Introduction" read as a line of text, its corresponding author and e-mail each came back as a
sentence of the model's, "Section one is the Introduction.", longer than the unit itself). The prompt lets the model
say so, by an empty takeaway, and such a unit's every level is its own words. A model that stands in for one, a data
folder of its own; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import ladder, llm, local, store
from textfold.tokens import plain

TEXT = """# Machine assistance

## Abstract

A framework helps designers decide under uncertainty. It was tested on many buildings.

Keywords:

E-mail address: someone@example.org (A. Author).
"""
CFG = {"kind": "api", "id": "fake/as-written", "effort": "none"}


class AsWritten(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        p = mock.patch.object(store, "DATA", self.tmp / "data")
        p.start()
        self.addCleanup(p.stop)
        self.doc = store.assemble(local.import_text(TEXT))
        self.U, self.A = self.doc["units"], self.doc["atoms"]

    def test_the_prompt_lets_a_unit_stay_as_written(self):
        chunk = next(c for c in self.doc["chunks"] if c["units"])
        self.assertIn('stays as written: give its takeaway, topic and reason as ""', ladder.prompt_for(self.doc, chunk))

    def test_an_empty_takeaway_keeps_the_unit_s_own_words(self):
        def model(prompt, schema, cfg, cache_dir, force=False, timeout=900, system=None):
            units = []
            for n, text in re.findall(r"^\[U(\d+)\] \w+\n  0: (.*)$", prompt, re.M):
                passage = text.startswith("A framework")
                units.append({"id": f"U{n}", "role": "method" if passage else "context",
                              "takeaway": "A framework guides design under uncertainty" if passage else "",
                              "topic": "A framework" if passage else "", "reason": "", "evidence": [0]})
            return {"out": {"section": {"takeaway": "A framework guides design", "topic": "A framework"}, "units": units},
                    "cost": 0}, False
        with mock.patch.object(llm, "call", model):
            ladder.build(self.doc, CFG, self.tmp / "cache", jobs=1, log=lambda *a: None)
        said = {plain(u["toks"], self.A): u["lad"] for u in self.U.values()}
        self.assertEqual(plain(said["A framework helps designers decide under uncertainty. It was tested on many buildings."]
                               ["brief"], self.A), "A framework guides design under uncertainty.")
        for text in ("Keywords:", "E-mail address: someone@example.org (A. Author)."):
            lad = said[text]
            self.assertEqual(lad["model"], "local")
            self.assertEqual(plain(lad["brief"], self.A), text)                    # its Key line: itself
            take = plain(lad["brief"][:lad["tn"]], self.A)                         # its takeaway: its words (the closing
            self.assertTrue(text.startswith(take))                                 # stop is the reader's)
            self.assertEqual(re.findall(r"\w+", take), re.findall(r"\w+", text))
            self.assertTrue(text.startswith(plain(lad["topic"], self.A)))          # its topic: its first words


if __name__ == "__main__":
    unittest.main()
