"""The notes page and its summaries (summary.py): every note of the library in one list, newest first; a summary of
the notes picked is a document of the library, in its folder of summaries, dated, its notes kept as they were when it
was made. A point unfolds to the notes it rests on (its evidence), a number the model named that was not sent is left
out, and a point that names none says so. Without a model the notes are listed alone. Each copy links to its place
(/p/<id>#n=), a link the document keeps where it drops other paths.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import library, llm, local, notes, semantic, store, summary
from textfold.tokens import plain

A = """# Pruning

## Method

We remove the weights whose magnitude is smallest after every epoch, and keep the rest as they were.

## Results

On the held-out set the pruned network loses less than one point of accuracy, but only on the smaller models.
"""

B = """# Distillation

## Method

A small student network learns to match the outputs of a large teacher network.
"""


class Summary(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(store, "DATA", Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.a, self.b = local.import_text(A, "pruning.md"), local.import_text(B, "distill.md")
        self.note(self.a, "n-1", "the weights whose magnitude is smallest", "Magnitude only, no retraining.", "2026-11-01T08:00:00Z")
        self.note(self.a, "n-2", "but only on the smaller models", "", "2026-11-03T08:00:00Z")
        self.note(self.b, "n-3", "match the outputs of a large teacher", "Compare with pruning.", "2026-11-02T08:00:00Z")

    def note(self, pid, nid, exact, text, created):
        doc = store.parsed(pid)
        uid = next(u for u in doc["units"] if exact in plain(doc["units"][u]["toks"], doc["atoms"]))
        full, _ = notes._spans(doc["units"][uid]["toks"], doc["atoms"])
        a = notes._at(doc, uid, full.index(exact), full.index(exact) + len(exact))
        notes.put(pid, {"id": nid, "kind": "highlight", "created": created, "anchor": {**a, "lang": "en", "level": 4},
                        "text": text, "thread": []})

    def papers(self):
        return library.stamp(store.papers())

    def test_every_note_newest_first(self):
        got = summary.everything(self.papers())
        self.assertEqual([n["id"] for n in got["notes"]], ["n-2", "n-3", "n-1"])
        self.assertEqual({n["paper"] for n in got["notes"]}, {self.a, self.b})
        self.assertEqual(got["papers"][self.a]["title"], "Pruning")

    def items(self):
        return [{"paper": self.a, "note": "n-2"}, {"paper": self.b, "note": "n-3"}, {"paper": self.a, "note": "n-1"}]

    def test_picked_in_the_order_made_a_text_together(self):
        got = summary._picked(self.items())
        self.assertEqual([n["id"] for _, _, n in got], ["n-1", "n-2", "n-3"])
        with self.assertRaises(ValueError):
            summary._picked([{"paper": self.a, "note": "n-404"}])

    def test_without_a_model_the_notes_alone(self):
        pid = summary.make(self.items(), None, "en", when="2026-11-05 09:00")
        meta = json.loads(store.read_text(store.pdir(pid) / "meta.json"))
        self.assertEqual(meta["summary"]["made"], "2026-11-05 09:00")
        self.assertEqual(len(meta["summary"]["notes"]), 3)
        md = store.read_text(store.pdir(pid) / "source.md")
        self.assertIn("Summary · 2026-11-05 · 2 texts · 3 notes", md)
        self.assertNotIn("## Summary", md)
        self.assertIn("I wrote: Magnitude only, no retraining.", md)
        html = store.read_text(store.pdir(pid) / "source.html")
        self.assertIn(f'href="/p/{self.a}?lang=en#n=n-1&amp;u=', html)   # (a link to the place, kept)
        fs = library.folders()
        self.assertEqual([f["name"] for f in fs["folders"]], ["Summaries"])
        self.assertEqual(fs["of"][pid], fs["folders"][0]["id"])
        store.assemble(pid)   # (it reads in the reader)
        listed = {p["id"]: p for p in store.papers()}
        self.assertEqual(listed[pid]["summary"], {"made": "2026-11-05 09:00", "notes": 3, "texts": 2})   # (the sidebar marks it)
        self.assertNotIn("summary", listed[self.a])

    def test_points_unfold_to_the_notes_they_rest_on(self):
        reply = {"overview": {"takeaway": "Two ways to make a network smaller.", "topic": "smaller"},
                 "points": [{"point": "Pruning keeps accuracy only on small models.", "reason": "The result has a but.",
                             "topic": "Pruning", "notes": [1, 2, 9]},
                            {"point": "Distillation is the other way.", "reason": "", "topic": "Distillation", "notes": []}]}
        with mock.patch.object(llm, "call", return_value=({"out": reply}, False)) as call, \
                mock.patch.object(llm, "label", return_value="test-model"):
            pid = summary.make(self.items(), {"id": "test-model"}, "en", when="2026-11-05 09:00")
        prompt = call.call_args[0][0]
        self.assertIn('[2] (T1, 2026-11-03) quote: "but only on the smaller models"', prompt)
        self.assertIn("Write in English.", prompt)
        doc = store.assemble(pid)
        chunk = next(c for c in doc["chunks"] if c.get("title") == "Summary")
        first, second = (doc["units"][u] for u in chunk["units"])
        lad = first["lad"]
        self.assertEqual(plain(lad["brief"][:lad["tn"]], doc["atoms"]).strip(), "Pruning keeps accuracy only on small models")
        cited = [plain(first["toks"][s:e], doc["atoms"]) for k, (s, e) in enumerate(first["sents"]) if k in lad["ev"]]
        self.assertTrue(cited[0].startswith("[1]"))
        self.assertTrue(any(s.startswith("[2]") for s in cited))
        self.assertNotIn("[9]", plain(first["toks"], doc["atoms"]))   # (a number not sent: left out)
        self.assertIn("The model named no note for this point.", plain(second["toks"], doc["atoms"]))
        self.assertEqual(doc["meta"]["lang"], "en")

    def test_a_copy_stays_as_it_was(self):
        pid = summary.make(self.items(), None, "en", when="2026-11-05 09:00")
        notes.delete(self.a, "n-1")
        self.assertIn("Magnitude only, no retraining.", store.read_text(store.pdir(pid) / "source.md"))

    def test_links_kept_to_documents_only(self):
        html = ('<p><a href="/p/md-a-1?lang=en#n=n-1&amp;u=p-2">there</a> <a href="/api/papers">api</a> '
                '<a href="javascript:alert(1)">x</a></p>')
        out = semantic.normalize(html)
        self.assertIn('href="/p/md-a-1?lang=en#n=n-1&amp;u=p-2"', out)
        self.assertNotIn("/api/papers", out)
        self.assertNotIn("javascript", out)


if __name__ == "__main__":
    unittest.main()
