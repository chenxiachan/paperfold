"""The notes page and its reading records (record.py): every note of the library in one list, newest first; the
record of the notes picked answers four questions (what I read, what I was curious about, what I got, what I attended
to) from the notes and the texts alone, no model, each entry with its text and section; as a document of the library,
in its folder of records, dated, its entries folding to their own lines; or as Markdown for Obsidian, each text a
[[link]] to the note the reader saves for it and each entry a link to its block there. Each entry links to its place
(/p/<id>#n=), a link the document keeps where it drops other paths.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import library, llm, local, notes, record, semantic, store
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


class Record(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(store, "DATA", Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.a, self.b = local.import_text(A, "pruning.md"), local.import_text(B, "distill.md")
        self.note(self.a, "n-1", "the weights whose magnitude is smallest", "Magnitude only, no retraining.", "2026-11-01T08:00:00Z")
        self.note(self.a, "n-2", "but only on the smaller models", "", "2026-11-03T08:00:00Z")
        self.note(self.b, "n-3", "match the outputs of a large teacher", "", "2026-11-02T08:00:00Z",
                  [{"q": "Why a teacher?", "a": "It carries what the big network learned.", "takeaway": "The teacher's outputs carry its knowledge."}])

    def note(self, pid, nid, exact, text, created, thread=()):
        doc = store.parsed(pid)
        uid = next(u for u in doc["units"] if exact in plain(doc["units"][u]["toks"], doc["atoms"]))
        full, _ = notes._spans(doc["units"][uid]["toks"], doc["atoms"])
        a = notes._at(doc, uid, full.index(exact), full.index(exact) + len(exact))
        notes.put(pid, {"id": nid, "kind": "ask" if thread else "highlight", "created": created,
                        "anchor": {**a, "lang": "en", "level": 4}, "text": text, "thread": list(thread)})

    def items(self):
        return [{"paper": self.a, "note": "n-2"}, {"paper": self.b, "note": "n-3"}, {"paper": self.a, "note": "n-1"}]

    def test_every_note_newest_first(self):
        got = record.everything(library.stamp(store.papers()))
        self.assertEqual([n["id"] for n in got["notes"]], ["n-2", "n-3", "n-1"])
        self.assertEqual({n["paper"] for n in got["notes"]}, {self.a, self.b})
        self.assertEqual(got["papers"][self.a]["title"], "Pruning")

    def test_picked_in_the_order_made_a_text_together(self):
        got = record._picked(self.items())
        self.assertEqual([n["id"] for _, _, n in got], ["n-1", "n-2", "n-3"])
        with self.assertRaises(ValueError):
            record._picked([{"paper": self.a, "note": "n-404"}])

    def test_four_questions_from_the_notes_alone(self):
        with mock.patch.object(llm, "call", side_effect=AssertionError("no model")):
            title, md, lines, picked = record.record_md(self.items(), record.WORDS["en"], "2026-11-05 09:00")
        self.assertEqual(title, "Reading record · 2026-11-01 to 2026-11-03")
        for h in ("## What I read", "## What I was curious about", "## What I got", "## What I attended to"):
            self.assertIn(h, md)
        self.assertIn("Why a teacher? Answer: The teacher's outputs carry its knowledge.", md)
        self.assertIn("Magnitude only, no retraining. (Pruning · Method, 2026-11-01,", md)
        self.assertIn("“but only on the smaller models”", md)
        self.assertEqual(lines[:2], ["Pruning", "Distillation"])   # (what I read: the texts, in the order first noted)
        self.assertIn("Results", lines)                             # (what I attended to: under its section)

    def test_a_record_is_a_document_folded_to_its_lines(self):
        pid = record.record(self.items(), "en", when="2026-11-05 09:00")
        meta = json.loads(store.read_text(store.pdir(pid) / "meta.json"))
        self.assertEqual(meta["summary"]["kind"], "record")
        self.assertEqual(len(meta["summary"]["notes"]), 3)
        html = store.read_text(store.pdir(pid) / "source.html")
        self.assertIn(f'href="/p/{self.a}?lang=en#n=n-1&amp;u=', html)   # (a link to the place, kept)
        doc = store.assemble(pid)
        takes = [plain(u["lad"]["brief"][:u["lad"]["tn"]], doc["atoms"]).strip() for c in doc["chunks"] for u in (doc["units"][x] for x in c["units"])]
        self.assertIn("Why a teacher", takes)   # (a line at Takeaway ends without its stop)
        self.assertIn("Magnitude only, no retraining", takes)
        fs = library.folders()
        self.assertEqual([f["name"] for f in fs["folders"]], ["Reading records"])
        listed = {p["id"]: p for p in store.papers()}
        self.assertEqual(listed[pid]["summary"], {"made": "2026-11-05 09:00", "notes": 3, "texts": 2})   # (the sidebar marks it)
        got = record.everything(library.stamp(store.papers()))
        self.assertEqual(got["used"][f"{self.a}|n-1"], [pid])

    def test_obsidian_links_to_the_readers_own_notes(self):
        name, md = record.obsidian(self.items(), "en", when="2026-11-05 09:00")
        self.assertEqual(name, "Reading record · 2026-11-01 to 2026-11-03.md")
        self.assertTrue(md.startswith("---\ntitle: "))
        self.assertIn(f"[[{self.a} Pruning|Pruning]]", md)
        self.assertIn(f"[[{self.a} Pruning#^n-1|Pruning · Method]]", md)
        self.assertIn(f"textfold://open?paper={self.a}&n=n-1&lang=en", md)
        self.assertIn("> [!question] Why a teacher?", md)

    def test_what_the_page_makes_is_a_document_with_its_obsidian_beside_it(self):
        reply = {"opening": "Two texts. Mostly smaller networks [1].", "texts": [{"t": 1, "line": "Prune with care.", "about": "It prunes [T1.1].",
                 "noticed": "You marked a but [2].", "meaning": "A condition [2].", "extend": ""}], "closing": {"line": "Smaller networks.", "body": "[1][3]"}}
        with mock.patch.object(llm, "call", return_value=({"out": reply}, False)), mock.patch.object(llm, "label", return_value="test-model"):
            pid, title = record.make(self.items(), "en", "digest", "", {"id": "test-model"}, when="2026-11-05 09:00")
        self.assertEqual(title, "Reading record · 2026-11-01 to 2026-11-03")
        name, text = record.obsidian_of(pid)
        self.assertEqual(name, "Reading record · 2026-11-01 to 2026-11-03.md")
        self.assertIn("## Overview", text)
        self.assertIn("Prune with care.", store.read_text(store.pdir(pid) / "source.md"))
        with self.assertRaises(record.NoModel):
            record.make(self.items(), "en", "ask", "Why?", None)
        pid2, _ = record.make(self.items(), "en", "digest", "", None, when="2026-11-05 10:00")   # (no model: the notes alone)
        self.assertNotIn("## Overview", store.read_text(store.pdir(pid2) / "source.md"))
        answer = {"answer": "By pruning [1] or by a teacher [3].", "takeaway": "Two ways."}
        with mock.patch.object(llm, "call", return_value=({"out": answer}, False)), mock.patch.object(llm, "label", return_value="test-model"):
            pid3, title3 = record.make(self.items(), "en", "ask", "How do they shrink a network?", {"id": "test-model"}, when="2026-11-05 11:00")
        self.assertEqual(title3, "How do they shrink a network? · 2026-11-01 to 2026-11-03")
        self.assertIn("## What I asked", store.read_text(store.pdir(pid3) / "source.md"))

    def test_a_question_asked_of_the_notes(self):
        reply = {"answer": "Pruning keeps the large weights [1], and loses little only on small models [2]. Distillation "
                           "copies a teacher [3]. Nothing says which is faster [9].", "takeaway": "Two ways to shrink a network."}
        with mock.patch.object(llm, "call", return_value=({"out": reply}, False)) as call, mock.patch.object(llm, "label", return_value="test-model"):
            got = record.ask(self.items(), "How do they make a network smaller?", {"id": "test-model"}, "en")
        prompt = call.call_args[0][0]
        self.assertIn("Question: How do they make a network smaller?", prompt)
        self.assertIn('[2] (T1, in T1.2 Results, 2026-11-03) passage: "but only on the smaller models" paragraph: "On the held-out set', prompt)
        self.assertIn("Write in English", prompt)
        self.assertNotIn("[9]", got["answer"])   # (a number that names no note: left out)
        self.assertEqual([x["n"] for x in got["notes"]], [1, 2, 3])
        self.assertEqual(got["notes"][0]["line"], "Magnitude only, no retraining.")
        qa = [{"q": got["question"], "answer": got["answer"], "model": got["model"]}]
        title, md, lines, _ = record.record_md(self.items(), record.WORDS["en"], "2026-11-05 09:00", record._questions(qa))
        self.assertIn("## What I asked", md)
        self.assertIn(f"[1](/p/{self.a}?lang=en#n=n-1", md)
        self.assertEqual(lines[0], "How do they make a network smaller?")
        name, ob = record.obsidian(self.items(), "en", when="2026-11-05 09:00", qa=qa)
        self.assertIn("> [!question] How do they make a network smaller?", ob)
        self.assertIn(f"[[{self.a} Pruning#^n-1|1]]", ob)
        pid = record.record(self.items(), "en", when="2026-11-05 09:00", qa=qa)
        self.assertIn("How do they make a network smaller", store.read_text(store.pdir(pid) / "source.md"))

    def test_an_overview_a_part_a_text_every_claim_cited(self):
        reply = {"opening": "You read two texts over three days. Mostly about making networks smaller [1].",
                 "texts": [{"t": 2, "line": "A teacher passes on what it learned [3].", "about": "A student matches a teacher [T2.1].",
                            "noticed": "You asked why a teacher is needed [3].", "meaning": "Knowledge moves by outputs [3][7].", "extend": ""},
                           {"t": 1, "line": "Prune, but mind the model's size.", "about": "It removes small weights [T1.1] and reports a loss [T1.2][T1.9].",
                            "noticed": "You wrote it needs no retraining [1] and marked a but [2].", "meaning": "The result has a condition [2].",
                            "extend": "Lottery-ticket work asks the same question."}],
                 "closing": {"line": "Lately: smaller networks, and what they keep.", "body": "Both texts shrink a network [1][3]."}}
        with mock.patch.object(llm, "call", return_value=({"out": reply}, False)) as call, mock.patch.object(llm, "label", return_value="test-model"):
            got = record.digest(self.items(), {"id": "test-model"}, "en")
        prompt = call.call_args[0][0]
        self.assertIn("  [T1.1] Method", prompt)
        self.assertIn("[1] (T1, in T1.1 Method, 2026-11-01)", prompt)
        self.assertEqual([x["t"] for x in got["texts"]], [1, 2])   # (in the order of the texts)
        self.assertNotIn("[T1.9]", got["texts"][0]["about"])     # (a section that is not there: left out)
        self.assertNotIn("[7]", got["texts"][1]["meaning"])
        self.assertEqual({x["code"] for x in got["sections"]}, {"T1.1", "T1.2", "T2.1"})
        title, md, lines, _ = record.record_md(self.items(), record.WORDS["en"], "2026-11-05 09:00", (), record._digest_in(got))
        self.assertTrue(md.index("## Overview") < md.index("## What I read"))
        self.assertIn("### Pruning", md)
        self.assertIn(f"[§1](/p/{self.a}?lang=en#s=", md)
        self.assertIn("Further: Lottery-ticket work asks the same question.", md)
        self.assertEqual(lines[:2], ["You read two texts over three days.", "Prune, but mind the model's size."])
        name, ob = record.obsidian(self.items(), "en", when="2026-11-05 09:00", digest=got)
        self.assertIn(f"### [[{self.a} Pruning|Pruning]]", ob)
        self.assertIn(f"textfold://open?paper={self.a}&s=", ob)
        pid = record.record(self.items(), "en", when="2026-11-05 09:00", digest=got)
        self.assertIn("Lately: smaller networks", store.read_text(store.pdir(pid) / "source.md"))

    def test_a_copy_stays_as_it_was(self):
        pid = record.record(self.items(), "en", when="2026-11-05 09:00")
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
