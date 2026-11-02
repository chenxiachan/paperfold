"""A question about a selection is answered from the paper in full, when it is short enough (notes.FULL_TOKENS): before,
the model had the selection's paragraph, a line per nearby paragraph, and five passages that shared the question's
words, so what the question needed from elsewhere, in other words, it did not have. The paper comes first in the
prompt, the same for every question about it, so that a service that keeps a prompt's beginning reads it once. A
paper too long, or too long for the model (its error says so), is asked about as before.

Run from the repo root:
    python3 -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import kinds, local, notes, store

TEXT = """# Pruning

## Method

We remove the weights whose magnitude is smallest after every epoch, and keep the rest as they were.

The schedule removes ten percent each time, until half of the network is gone.

## Results

On the held-out set the pruned network loses less than one point of accuracy.

## Limits

Our hardware ran out of memory on the largest model, so it was never tested.
"""


class Full(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(store, "DATA", Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.pid = local.import_text(TEXT, "pruning.md")
        self.doc = store.assemble(self.pid)
        self.head = kinds.adapt(notes.FULL_HEAD, self.doc["meta"])   # (a text, not a paper: "The text in full")
        self.first = next(u for u in self.doc["units"] if "smallest" in notes.plain(self.doc["units"][u]["toks"], self.doc["atoms"]))

    def note(self, nid="n-1"):
        n = {"id": nid, "kind": "ask", "thread": [], "anchor": {"unit": self.first, "level": 4, "tokens": None, "sents": None,
                                                                "quote": {"exact": "the weights whose magnitude is smallest"}}}
        notes.put(self.pid, n)
        return n

    def test_a_paragraph_far_off_and_in_other_words_is_there(self):
        text, nums = notes.prompt(self.doc, self.note(), "Was it tried on big models?", "en")
        self.assertTrue(text.startswith(f"Text: {self.doc['meta']['title']}\n\n{self.head}"), text[:200])
        self.assertIn("Our hardware ran out of memory on the largest model, so it was never tested.", text)
        self.assertNotIn("Passages from elsewhere", text)
        self.assertIn("Any paragraph number in the text above.", text)
        order = [u for u in self.doc["units"]]
        self.assertEqual([nums[str(k + 1)] for k in range(len(order))], order)   # (numbered as they come)

    def test_every_question_about_it_begins_the_same(self):
        a, _ = notes.prompt(self.doc, self.note(), "Why ten percent?", "en")
        whole = {"id": "n-2", "kind": "ask", "thread": [], "anchor": {"on": "paper", "level": 1}}
        b, _ = notes.prompt(self.doc, whole, "What is it about?", "en")
        at = a.index("A reader of this text")
        self.assertEqual(a[:at], b[:b.index("A reader of this text")])
        self.assertIn("given in full above", b)

    def test_a_paper_too_long_is_asked_about_as_before(self):
        with mock.patch.object(notes, "FULL_TOKENS", 10):
            text, _ = notes.prompt(self.doc, self.note(), "Was it tried on big models?", "en")
        self.assertNotIn(self.head, text)
        self.assertIn("Passages from elsewhere in the text that share words with the question", text)
        self.assertIn("Opening:", text)

    def test_too_long_for_the_model_it_is_asked_again_as_before(self):
        self.note()
        seen = []

        def reply(text, *a, **k):
            seen.append(text)
            if len(seen) == 1:
                raise RuntimeError("DeepSeek: HTTP 400 This model's maximum context length is 65536 tokens.")
            return {"out": {"answer": "It was not [[1]].", "takeaway": "Not tested.", "next": []}}, False
        with mock.patch("textfold.llm.call", reply):
            n = notes.ask(self.pid, "n-1", "Was it tried on big models?", {"kind": "agent", "id": "x/codex/m"})
        self.assertIn(self.head, seen[0])
        self.assertNotIn(self.head, seen[1])
        self.assertEqual(n["thread"][-1]["cites"], [self.first])   # ([1]: the numbers of the prompt that answered)

    def test_another_error_is_said_as_it_was(self):
        self.note()
        calls = []

        def refuse(text, *a, **k):
            calls.append(text)
            raise RuntimeError("DeepSeek: HTTP 401 the key was rejected")
        with mock.patch("textfold.llm.call", refuse), self.assertRaisesRegex(RuntimeError, "401"):
            notes.ask(self.pid, "n-1", "Why?", {"kind": "agent", "id": "x/codex/m"})
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
