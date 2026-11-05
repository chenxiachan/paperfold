"""A long section is translated in parts, and a part is as long as what its reply writes (reported in #99: a section
of 99 short paragraphs asked in one part came back cut off at the 65th). A paragraph's entry in the reply holds its
sentences and its levels (takeaway, reason, topic), and where the paragraphs are short the levels are most of it: a
part counts both. A data folder of its own; no model, no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import local, store, translate
from textfold.tokens import plain


class Parts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = mock.patch.object(store, "DATA", Path(tmp.name) / "data")
        p.start()
        self.addCleanup(p.stop)

    def section(self, n, words):
        """A document of one section of n short paragraphs, each with levels as a model writes them (about 250
        characters), and that section."""
        text = "# Notes\n\n## Results\n\n" + "\n\n".join(f"Row {k} reads {words}." for k in range(n)) + "\n"
        doc = store.assemble(local.import_text(text))
        c = next(c for c in doc["chunks"] if c["title"] == "Results")
        for uid in c["units"]:
            take = [{"t": "The row shows the measure rising with the size of the model, as the others do", "s": 1}]
            reason = [{"t": "because every larger model was trained on more of the same text, so it saw more", "s": 1},
                      {"t": "examples of each kind than the one before it."}]
            doc["units"][uid]["lad"] = {**doc["units"][uid]["lad"], "brief": take + reason, "tn": 1,
                                        "topic": [{"t": "measure rising"}]}
        return doc, c

    def test_many_short_paragraphs_are_asked_in_parts_their_levels_counted(self):
        doc, c = self.section(99, "a short value")
        text = sum(len(plain(doc["units"][u]["toks"], doc["atoms"])) for u in c["units"])
        self.assertLess(text, translate.PART_CHARS)   # (by their words alone: one part, as #99 had it)
        runs = translate.parts(doc, c)
        self.assertGreater(len(runs), 1)
        self.assertEqual([u for r in runs for u in r], c["units"])   # (every paragraph, once, in order)
        for r in runs:
            self.assertLessEqual(sum(translate.size(doc, u) for u in r), translate.PART_CHARS * 1.2)

    def test_a_short_section_is_one_part(self):
        doc, c = self.section(8, "a short value")
        self.assertEqual(translate.parts(doc, c), [c["units"]])


if __name__ == "__main__":
    unittest.main()
