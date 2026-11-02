"""Any document's text can be edited, one that came as a page too (an arXiv paper, a web page from the browser): its
text is the Markdown of what the reader reads (editable.py), which read back unchanged is the same document, word for
word and id for id; edited, only the paragraphs changed are new, its notes stay, and its pictures are the ones kept
beside it; every edit undone, it is the page it came as. In a data folder of its own; nothing is fetched.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_replace   # noqa: E402
from test_replace import Base, fake_model   # noqa: E402

from textfold import editable, ids, llm, local, markdown, pipeline, semantic, store   # noqa: E402

MATH = ('<math alttext="{t}" class="ltx_Math" display="inline"><semantics><mi>x</mi>'
        '<annotation encoding="application/x-tex">{t}</annotation></semantics></math>')
# an arXiv paper as LaTeXML writes it: an abstract, a numbered section, a citation, references to a figure and a
# formula, emphasis, a footnote, a numbered formula, a figure and a table with captions, a list, the references
ARXIV = f"""<!DOCTYPE html><html><body><div class="ltx_page_main"><article class="ltx_document">
<h1 class="ltx_title ltx_title_document">Folding paper</h1>
<div class="ltx_abstract"><h6 class="ltx_title ltx_title_abstract">Abstract</h6>
<p class="ltx_p" id="abstract1.1">We fold a square of paper and count its creases, {MATH.format(t="n^{2}")} of them.</p></div>
<section class="ltx_section" id="S1"><h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">1 </span>Introduction</h2>
<div class="ltx_para" id="S1.p1"><p class="ltx_p" id="S1.p1.1">Folding is old <cite class="ltx_cite ltx_citemacro_cite">[<a class="ltx_ref" href="#bib.bib1" title="">1</a>]</cite>. See <a class="ltx_ref" href="#S1.F1" title=""><span class="ltx_text ltx_ref_tag">Figure 1</span></a> and Eq. <a class="ltx_ref" href="#S1.E1"><span class="ltx_text ltx_ref_tag">1</span></a>. It is <span class="ltx_text ltx_font_italic">very</span> old, and <span class="ltx_text ltx_font_bold">still</span> done.<span class="ltx_note ltx_role_footnote" id="footnote1"><sup class="ltx_note_mark">1</sup><span class="ltx_note_outer"><span class="ltx_note_content"><sup class="ltx_note_mark">1</sup>Since 1797 at least.</span></span></span></p></div>
<table class="ltx_equation ltx_eqn_table" id="S1.E1"><tbody><tr class="ltx_equation ltx_eqn_row ltx_align_baseline"><td class="ltx_eqn_cell ltx_eqn_center_padleft"></td><td class="ltx_eqn_cell ltx_align_center"><math alttext="c=n^{{2}}" class="ltx_Math" display="block"><semantics><mi>c</mi><annotation encoding="application/x-tex">c=n^{{2}}</annotation></semantics></math></td><td class="ltx_eqn_cell ltx_eqn_center_padright"></td><td class="ltx_eqn_cell ltx_eqn_eqno ltx_align_middle ltx_align_right" rowspan="1"><span class="ltx_tag ltx_tag_equation ltx_align_right">(1)</span></td></tr></tbody></table>
<div class="ltx_para" id="S1.p2"><p class="ltx_p" id="S1.p2.1">The crane needs three folds:</p>
<ul class="ltx_itemize" id="S1.I1">
<li class="ltx_item" id="S1.I1.i1"><span class="ltx_tag ltx_tag_item">•</span><div class="ltx_para" id="S1.I1.i1.p1"><p class="ltx_p" id="S1.I1.i1.p1.1">a valley fold,</p></div></li>
<li class="ltx_item" id="S1.I1.i2"><span class="ltx_tag ltx_tag_item">•</span><div class="ltx_para" id="S1.I1.i2.p1"><p class="ltx_p" id="S1.I1.i2.p1.1">a mountain fold, and</p></div></li>
<li class="ltx_item" id="S1.I1.i3"><span class="ltx_tag ltx_tag_item">•</span><div class="ltx_para" id="S1.I1.i3.p1"><p class="ltx_p" id="S1.I1.i3.p1.1">a squash fold.</p></div></li>
</ul></div>
<figure class="ltx_figure" id="S1.F1"><img alt="Refer to caption" class="ltx_graphics ltx_centering" height="200" id="S1.F1.g1" src="2512.23916v1/crane.png" width="300"/>
<figcaption class="ltx_caption ltx_centering"><span class="ltx_tag ltx_tag_figure">Figure 1: </span>A crane, folded from {MATH.format(t="1")} square.</figcaption></figure>
<figure class="ltx_table" id="S1.T1"><figcaption class="ltx_caption ltx_centering"><span class="ltx_tag ltx_tag_table">Table 1: </span>Folds of each model.</figcaption>
<table class="ltx_tabular ltx_centering ltx_align_middle" id="S1.T1.1"><tr class="ltx_tr"><td class="ltx_td ltx_align_left ltx_border_tt">Crane</td><td class="ltx_td ltx_align_center ltx_border_tt">22</td></tr></table></figure>
</section>
<section class="ltx_bibliography" id="bib"><h2 class="ltx_title ltx_title_bibliography">References</h2>
<ul class="ltx_biblist"><li class="ltx_bibitem" id="bib.bib1"><span class="ltx_tag ltx_role_refnum ltx_tag_bibitem">[1]</span><span class="ltx_bibblock">A. Folder. On paper. 1954.</span></li></ul></section>
</article></div></body></html>"""
PID = "2512.23916"
META = {"id": PID, "title": "Folding paper", "authors": ["Folder, A."], "abs_url": f"https://arxiv.org/abs/{PID}",
        "html_url": f"https://arxiv.org/html/{PID}", "license": ""}
# a page from the browser, read by a reading view: no Markdown of its own; its picture kept beside it
WEB = """<article class="ltx_document"><section class="ltx_section" id="abstract"><p class="ltx_p">A note on paper cranes.</p></section>
<section class="ltx_section" id="sec-history"><h2 class="ltx_title">History</h2><p class="ltx_p">The first book on them appeared in <a href="https://example.org/1797">1797</a>, with <em>many</em> models.</p>
<figure class="ltx_figure"><img src="img/01-crane.png"/><figcaption class="ltx_caption">A thousand cranes on a string.</figcaption></figure>
<p class="ltx_p">Folders still make them.</p></section></article>"""
WEB_PID = "web-example-org-0123456789ab"


def tokens(doc, uid):
    """A unit's words as the model is shown them: its tokens, atoms by what they are, no space after the last."""
    toks = [({**t, "a": (doc["atoms"][t["a"]]["kind"], doc["atoms"][t["a"]].get("alt") or doc["atoms"][t["a"]]["text"])}
             if "a" in t else dict(t)) for t in doc["units"][uid]["toks"]]
    if toks:
        toks[-1].pop("s", None)
    return toks, doc["units"][uid]["sents"]


class EditAny(Base):
    def setUp(self):
        super().setUp()
        from PIL import Image
        for pid, page, meta in ((PID, ARXIV, META), (WEB_PID, WEB, {"id": WEB_PID, "title": "Paper cranes"})):
            d = store.pdir(pid)
            (d / "img").mkdir(parents=True)
            (d / "source.html").write_text(page, encoding="utf-8")
            (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        Image.new("RGB", (30, 20), "red").save(store.pdir(PID) / "img" / "crane.png")   # (as the reader kept it: build.py)
        Image.new("RGB", (30, 20), "blue").save(store.pdir(WEB_PID) / "img" / "01-crane.png")
        nothing = mock.patch.object(local, "urlread", side_effect=AssertionError("nothing is fetched"))
        nothing.start()
        self.addCleanup(nothing.stop)

    def test_the_text_of_a_page_is_its_markdown(self):
        text = local.text_of(PID)
        for part in ("## 1 Introduction", "Folding is old <cite class=\"ltx_cite ltx_citemacro_cite\">[<a class=\"ltx_ref\" href=\"#bib.bib1\">1</a>]</cite>.", "[Figure 1](#S1.F1)", "[1](#eq-S1-E1)", "*very* old",
                     "**still** done", "[^1]", "[^1]: Since 1797 at least.", "$n^{2}$", "$$\nc=n^{2} \\tag{1} \\label{S1.E1}\n$$",
                     "- a valley fold,", '<figure id="S1.F1">', '<img alt="Refer to caption" class="ltx_graphics ltx_centering" height="200" src="img/crane.png" width="300"/>',
                     '<span class="ltx_tag">Figure 1: </span>\n\nA crane, folded from $1$ square.', "## References", '<li class="ltx_bibitem" id="bib.bib1">'):
            self.assertIn(part, text)
        self.assertNotIn("style=", text)
        self.assertEqual(local.text_of(WEB_PID).splitlines()[0], "A note on paper cranes.")

    def test_read_back_unchanged_it_is_the_same_document(self):
        for pid in (PID, WEB_PID):
            doc = store.parsed(pid)
            meta = json.loads((store.pdir(pid) / "meta.json").read_text(encoding="utf-8"))
            html = markdown.to_html(editable.markdown(doc, store.pdir(pid) / "img"))[0]
            _, again = ids.freeze(semantic.normalize(html, resolve_img=lambda s: s, sizes=True), meta, doc, ids.load(pid))
            self.assertEqual(list(again["units"]), list(doc["units"]), pid)
            for uid in doc["units"]:
                self.assertEqual(tokens(again, uid), tokens(doc, uid), (pid, uid))
            self.assertEqual([c["num"] + c["title"] for c in again["chunks"]], [c["num"] + c["title"] for c in doc["chunks"]])
            self.assertEqual(sorted(a["kind"] for a in again["atoms"].values()), sorted(a["kind"] for a in doc["atoms"].values()))
            self.assertEqual(sorted(b["k"] for b in again["blocks"]), sorted(b["k"] for b in doc["blocks"]))
            self.assertEqual({(e["f"], e["tk"]) for e in again["edges"]}, {(e["f"], e["tk"]) for e in doc["edges"]})
            self.assertEqual(bool(again.get("bib")), bool(doc.get("bib")))

    def test_edited_only_what_changed_is_new_and_every_edit_undone_it_is_the_page_again(self):
        d = store.pdir(PID)
        page = (d / "source.html").read_bytes()
        was = store.parsed(PID)
        anchor = self.note(PID, "n-old", "S1.p1.1", "very old")
        text = local.text_of(PID)
        local.replace_text(PID, text.replace("a mountain fold", "a mountain fold (the back of a valley)"))
        now = store.parsed(PID)
        self.assertEqual(list(now["units"]), list(was["units"]))
        self.assertEqual([u for u in was["units"] if tokens(now, u) != tokens(was, u)], ["S1.I1.i2.p1.1"])
        self.assertEqual(self.words_at(PID, self.notes(PID)["n-old"]["anchor"]), "very old")
        self.assertEqual(anchor["unit"], self.notes(PID)["n-old"]["anchor"]["unit"])
        self.assertEqual(local.original(PID), text)                          # the text it had, in its history
        self.assertTrue((d / store.HISTORY / "source.html").exists())        # and the page it came as
        self.assertEqual([p.name for p in (d / "img").iterdir()], ["01-crane.png"])   # its figure, the one kept beside it
        self.assertNotIn("pf-missing", (d / "source.html").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((d / "meta.json").read_text(encoding="utf-8"))["title"], "Folding paper")
        self.assertIn("(the back of a valley)", local.text_of(PID))         # (its text now, saved)
        local.replace_text(PID, text)
        self.assertEqual((d / "source.html").read_bytes(), page)
        self.assertFalse((d / "source.md").exists())
        self.assertFalse((d / store.HISTORY).exists())
        self.assertEqual([p.name for p in (d / "img").iterdir()], ["crane.png"])
        self.assertEqual(self.words_at(PID, self.notes(PID)["n-old"]["anchor"]), "very old")

    def test_a_page_from_the_browser_too(self):
        text = local.text_of(WEB_PID)
        local.replace_text(WEB_PID, text.replace("Folders still make them.", "Folders still make them, by the thousand."))
        doc = store.parsed(WEB_PID)
        self.assertIn("by the thousand", " ".join(t.get("t", "") for u in doc["units"].values() for t in u["toks"]))
        self.assertEqual([p.name for p in (store.pdir(WEB_PID) / "img").iterdir()], ["01-crane.png"])
        self.assertEqual(sum(1 for u in doc["units"].values() if u["role"] == "caption"), 1)


    def test_generated_again_the_model_is_asked_only_for_the_section_that_changed(self):
        asked = []
        with mock.patch.object(llm, "_once", fake_model(asked)), mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)   # (the build runs the tests with it: the model here is a stand-in)
            pipeline.generate(PID, "en", test_replace.Refold.SPEC)
            self.assertEqual(len(asked), 3)   # the abstract, the introduction and the links
            local.replace_text(PID, local.text_of(PID).replace("a squash fold.", "a squash fold, last."))
            asked.clear()
            pipeline.generate(PID, "en", test_replace.Refold.SPEC, force=True)
            # the introduction and the links; and once, at the first edit, the abstract: read from Markdown, its
            # paragraph is a paragraph, no longer LaTeXML's abstract
            self.assertEqual([a.split("This section: ")[1].split("\n")[0] if "This section: " in a else "links" for a in asked],
                             ["Abstract", "1 Introduction", "links"])
            self.assertIn("a squash fold, last.", asked[1])
            local.replace_text(PID, local.text_of(PID).replace("a valley fold,", "a valley fold, first,"))
            asked.clear()
            pipeline.generate(PID, "en", test_replace.Refold.SPEC, force=True)
            self.assertEqual(len(asked), 2)   # the introduction and the links


class Captions(unittest.TestCase):
    def test_a_caption_written_in_paragraphs_is_their_words(self):
        html = semantic.normalize('<figure><img src="a.png"><figcaption>\n<p>A crane.</p>\n<p>Folded twice.</p>\n</figcaption></figure>',
                                  resolve_img=lambda s: s)
        self.assertIn('<figcaption class="ltx_caption">A crane. Folded twice.</figcaption>', html.replace("\n", ""))


if __name__ == "__main__":
    unittest.main()
