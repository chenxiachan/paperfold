"""A web page's notes written inside its sentences and shown on hover or in the margin (issue #77): an ARIA tooltip under
its mark (aria-describedby), DPUB-ARIA's doc-footnote, Distill's d-footnote, Tufte's sidenote and marginnote. Read as
written, a note's words ran into the sentence, and a long one split its paragraph: the Full level was not the page's
text. Each is a footnote now, under the page's own mark (1, [10]), its words shown on hover. A tooltip with no mark is
hover help, not the article's. A popup the page marks in no such way is read as the page writes it.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import store, webpage
from textfold.parse import parse

FILL = ("Interpretability asks what each part of a trained network does, and how the parts work together to give the "
        "behaviour we see when the model reads a sentence and writes the next word. ")

PAGE = f"""<html><head><title>Neurons, counted</title></head><body><article>
<h1>Neurons, counted</h1>
<p>{FILL}Earlier audits found little<span class="fn cite"><button type="button" class="fn-mark" aria-describedby="cite-1">[10]</button><span class="fn-pop" role="tooltip" id="cite-1"><span class="cite-title">Towards Monosemanticity</span><br>Bricken, T., et al., 2023. <a href="#ref-10">References ↓</a></span></span> to read.</p>
<p>{FILL}Only a few are not yet understood<span class="fn"><button type="button" class="fn-mark" aria-describedby="fn-1">1</button><span class="fn-pop" role="tooltip" id="fn-1">A note on this number: it depends on the threshold.<br><br>How far to go into weak activations is a big factor here.</span></span>. Dense models seem roughly similar.</p>
<figure><canvas aria-describedby="map-tip"></canvas><div class="map-tip" role="tooltip" id="map-tip">Hover a dot to see its expert</div><figcaption>Every expert, narrowest first.</figcaption></figure>
<p>{FILL}Distill writes its notes in place<d-footnote>Distill numbers these itself, in order.</d-footnote> and goes on.</p>
<p>{FILL}Tufte puts one in the margin<label for="sn-1" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-1" class="margin-toggle"/><span class="sidenote">A sidenote, numbered by the page's own counter.</span> and another<label for="mn-1" class="margin-toggle">&#8853;</label><input type="checkbox" id="mn-1" class="margin-toggle"/><span class="marginnote">A margin note, without a number.</span> beside it.</p>
<p>{FILL}A book's note is marked<a href="#dn-9" role="doc-noteref">9</a><span role="doc-footnote" id="dn-9">An EPUB-style footnote, inside the sentence.</span> as such.</p>
<p>{FILL}A popup marked in no such way <span class="popup">stays where the page wrote it</span> as before.</p>
<p>{FILL}</p>
</article></body></html>"""

NOTE = re.compile(r'<span class="ltx_note ltx_role_footnote"><sup class="ltx_note_mark">([^<]*)</sup><span class="ltx_note_outer">'
                  r'<span class="ltx_note_content"><sup class="ltx_note_mark">[^<]*</sup>(.*?)</span></span></span>')


class Notes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        url = "https://example.org/neurons"
        with mock.patch.object(store, "DATA", Path(tmp.name)), mock.patch.object(webpage, "_get", lambda u: (PAGE.encode(), url, "utf-8")):
            pid = webpage.register(url)
            webpage.fetch(pid)
            d = store.pdir(pid)
            cls.html = (d / "source.html").read_text(encoding="utf-8")
            cls.md = (d / "source.md").read_text(encoding="utf-8")
        cls.notes = {mark: re.sub(r"<[^>]+>", "", words).strip() for mark, words in NOTE.findall(cls.html)}
        cls.text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", NOTE.sub("", cls.html)))
        cls.doc = parse(cls.html, {"id": pid})

    def test_the_sentence_reads_as_the_page_shows_it(self):
        self.assertIn("Only a few are not yet understood. Dense models seem roughly similar.", self.text)
        self.assertIn("Earlier audits found little to read.", self.text)
        self.assertIn("Distill writes its notes in place and goes on.", self.text)
        self.assertIn("Tufte puts one in the margin and another beside it.", self.text)
        self.assertIn("A book's note is marked as such.", self.text)
        for words in ("A note on this number", "weak activations", "Bricken", "Distill numbers", "sidenote", "margin note", "EPUB"):
            self.assertNotIn(words, self.text)

    def test_each_note_is_a_footnote_under_the_page_s_own_mark(self):
        self.assertEqual(self.notes["[10]"], "Towards Monosemanticity Bricken, T., et al., 2023. References ↓")
        self.assertIn("A note on this number: it depends on the threshold. How far to go into weak activations", self.html)
        self.assertEqual(self.notes["⊕"], "A margin note, without a number.")
        self.assertEqual(self.notes["9"], "An EPUB-style footnote, inside the sentence.")
        marks = [m for m, _ in NOTE.findall(self.html)]
        self.assertEqual(marks, ["[10]", "1", "1", "1", "⊕", "9"])   # (a tooltip's, Distill's and Tufte's first: each 1)
        self.assertIn('<a href="https://example.org/neurons#ref-10">References ↓</a>', self.html)
        self.assertEqual(sum(1 for a in self.doc["atoms"].values() if a["kind"] == "note"), 6)

    def test_a_tooltip_without_a_mark_is_not_the_article_s(self):
        self.assertNotIn("Hover a dot", self.html + self.md)

    def test_a_popup_marked_in_no_such_way_is_read_as_written(self):
        self.assertIn("A popup marked in no such way stays where the page wrote it as before.", self.text)

    def test_the_markdown_kept_has_them_as_footnotes(self):
        self.assertNotRegex(self.md + self.html, r"TFNOTE\d+Q")
        self.assertRegex(self.md, r"not yet understood\[\^\d+\]\. Dense")
        self.assertRegex(self.md, r"\n\[\^\d+\]: A note on this number: it depends on the threshold\. How far")
        self.assertRegex(self.md, r"\n\[\^\d+\]: Towards Monosemanticity Bricken, T\., et al\., 2023\. References ↓")


if __name__ == "__main__":
    unittest.main()
