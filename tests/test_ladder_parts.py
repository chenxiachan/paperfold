"""A long section's levels are asked in parts (reported in #98: a book's chapter of 351 paragraphs, asked in one call,
outran the model's output). The reply writes the same lines for every unit, however short, so a section of more than
ladder.PART_UNITS units is asked in parts, and its own line is then written from its units' takeaways, in one more
call. A section of PART_UNITS or fewer is asked as before, its line with its units. A model that stands in for one, a
data folder of its own; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from textfold import ladder, llm, local, store
from textfold.tokens import plain

CFG = {"kind": "api", "id": "fake/levels", "effort": "none"}


class Model:
    """Answers the level prompts: every unit it is shown, its takeaway "Point <its first words>"; a section's line
    asked alone, "The whole section". fail: the first words of a unit whose call fails."""
    def __init__(self, fail=None):
        self.fail, self.asked, self.lines = fail, [], []
        self.lock = threading.Lock()

    def __call__(self, prompt, schema, model, cache_dir, force=False, timeout=900, system=None):
        sec = re.search(r"^This section: (.*)$", prompt, re.M).group(1)
        if "units" not in schema["properties"]:
            with self.lock:
                self.lines.append((sec, re.findall(r"^- (Point .*)$", prompt, re.M)))
            return {"out": {"section": {"takeaway": "The whole section", "topic": "whole section"}}, "cost": 0}, False
        units = re.findall(r"^\[U(\d+)\][^\n]*\n  0: ([^\n]*)", prompt, re.M)
        with self.lock:
            self.asked.append((sec, [t for _, t in units]))
        if self.fail and any(t.startswith(self.fail) for _, t in units):
            raise RuntimeError("timed out")
        return {"out": {"section": {"takeaway": f"A part of {len(units)} units", "topic": "part"},
                        "units": [{"id": f"U{n}", "role": "claim", "takeaway": "Point " + " ".join(t.split()[:3]),
                                   "topic": "Point", "reason": "", "evidence": [0]} for n, t in units]}, "cost": 0}, False


class Parts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        p = mock.patch.object(store, "DATA", self.tmp / "data")
        p.start()
        self.addCleanup(p.stop)
        long = "\n\n".join(f"Row {k} reads a value of its own." for k in range(90))
        self.pid = local.import_text(f"# A book\n\n## Long\n\n{long}\n\n## Short\n\nOne line here. And one more.\n\nA second one.\n")

    def build(self, model):
        doc = store.assemble(self.pid)
        with mock.patch.object(llm, "call", model):
            ladder.build(doc, CFG, self.tmp / "cache", jobs=3, log=lambda *a: None)
        return doc, {c["title"]: c for c in doc["chunks"]}

    def test_a_long_section_in_parts_its_line_from_their_takeaways(self):
        model = Model()
        doc, c = self.build(model)
        long = [u for s, u in model.asked if s == "Long"]
        self.assertEqual(sorted(len(u) for u in long), [30, 30, 30])   # (90 units: three parts of about equal length)
        self.assertEqual(sorted(t for u in long for t in u), sorted(plain(doc["units"][u]["toks"], doc["atoms"]) for u in c["Long"]["units"]))
        self.assertTrue(all(doc["units"][u]["lad"].get("role") == "claim" for u in c["Long"]["units"]))   # (the model's, every one)
        self.assertEqual([s for s, _ in model.lines], ["Long"])   # (one more call, for the long one alone)
        self.assertEqual(len(model.lines[0][1]), 90)
        self.assertEqual(model.lines[0][1][0], "Point Row 0 reads")   # (in reading order)
        self.assertEqual(plain(c["Long"]["lad"]["take"], doc["atoms"]), "The whole section")

    def test_a_short_section_is_asked_as_before(self):
        model = Model()
        doc, c = self.build(model)
        self.assertEqual([len(u) for s, u in model.asked if s == "Short"], [2])
        self.assertEqual(plain(c["Short"]["lad"]["take"], doc["atoms"]), "A part of 2 units")   # (its line with its units)

    def test_a_part_that_failed_falls_back_and_the_line_is_written_from_the_rest(self):
        model = Model(fail="Row 45 ")
        doc, c = self.build(model)
        own = [u for u in c["Long"]["units"] if doc["units"][u]["lad"].get("role") == "claim"]
        self.assertEqual(len(own), 60)   # (the failed part's 30: their own levels, as for a failed call)
        self.assertEqual(len(model.lines[0][1]), 60)
        self.assertEqual(plain(c["Long"]["lad"]["take"], doc["atoms"]), "The whole section")


if __name__ == "__main__":
    unittest.main()
