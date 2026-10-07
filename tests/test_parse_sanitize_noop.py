"""Regression test: the sanitize() call parse.parse() now makes (see test_parse_sanitize.py
for the vulnerability it closes) must be a no-op on a clean, well-formed arXiv/LaTeXML page.

sanitize() only drops/unwraps elements and strips attributes outside semantic.py's
DROP/KEEP/ATTRS/MATHML allowlists (see adr/semantic.py's _sanitize()); it never touches class
values or document structure. A benign LaTeXML page should therefore parse identically whether
or not the call is made: same unit/chunk counts, same figure/image/math/table/link content.

Run from /tmp/paperfold-review so the `adr` package resolves:
    python3 -m unittest discover tests
or directly:
    python3 tests/test_parse_sanitize_noop.py
"""
import unittest

import adr.parse as parse_mod
from adr.parse import parse

# A benign LaTeXML-shaped page: sections, an ltx_p paragraph, a math element with alttext, an
# SVG figure given as <object> (parse.py's own object->img rewrite handles this, before sanitize
# ever runs), a table with ltx classes, an https link and a same-page #-anchor link.
CLEAN_HTML = """
<html><body>
<article class="ltx_document">
<section class="ltx_section" id="s1">
<h2 class="ltx_title ltx_title_section">Introduction</h2>
<div class="ltx_para"><p class="ltx_p">
See <a href="https://example.com">this site</a> and <a href="#s1">this section</a>: the formula
<math alttext="E=mc^2"><mi>E</mi></math> holds.
</p></div>
<figure class="ltx_figure" id="fig1">
<object data="fig1.svg" type="image/svg+xml">a sketch</object>
<figcaption class="ltx_caption"><span class="ltx_tag">Figure 1:</span> A sketch.</figcaption>
</figure>
<table class="ltx_tabular" id="tab1">
<tr class="ltx_tr"><td class="ltx_td">a</td><td class="ltx_td">b</td></tr>
</table>
</section>
</article>
</body></html>
"""

META = {"id": "2401.00002", "title": "T", "authors": [], "date": "", "abs_url": "",
        "html_url": "", "license": ""}


class ParseSanitizeNoopTest(unittest.TestCase):
    def setUp(self):
        self.with_sanitize = parse(CLEAN_HTML, dict(META))
        # Reparse the same clean HTML with sanitize() disabled, to prove it changed nothing.
        real_sanitize = parse_mod.sanitize
        parse_mod.sanitize = lambda art: None
        try:
            self.without_sanitize = parse(CLEAN_HTML, dict(META))
        finally:
            parse_mod.sanitize = real_sanitize

    def test_unit_and_chunk_counts_unchanged(self):
        self.assertEqual(len(self.without_sanitize["units"]), len(self.with_sanitize["units"]))
        self.assertEqual(len(self.without_sanitize["chunks"]), len(self.with_sanitize["chunks"]))
        self.assertEqual(len(self.without_sanitize["blocks"]), len(self.with_sanitize["blocks"]))

    def test_figure_image_survives_with_src(self):
        figs = [b for b in self.with_sanitize["blocks"] if b.get("k") == "fig"]
        self.assertEqual(len(figs), 1)
        self.assertIn('<img src="fig1.svg"', figs[0]["html"])

    def test_math_alttext_present(self):
        math_atoms = [a for a in self.with_sanitize["atoms"].values() if a.get("kind") == "math"]
        self.assertEqual(len(math_atoms), 1)
        self.assertEqual(math_atoms[0]["alt"], "E=mc^2")

    def test_https_and_hash_hrefs_survive(self):
        ref_atoms = [a for a in self.with_sanitize["atoms"].values() if a.get("kind") == "ref"]
        hrefs = {a["text"]: a["html"] for a in ref_atoms}
        self.assertIn('href="https://example.com"', hrefs["this site"])
        self.assertIn('href="#s1"', hrefs["this section"])

    def test_ltx_classes_intact(self):
        # parse() consumes some LaTeXML wrapper classes into its own section/caption structure
        # (ltx_section, ltx_para, ltx_figure, ltx_caption, ltx_tag never appear verbatim in the
        # payload even without sanitize -- that is parse()'s own behavior, not something
        # sanitize() could remove). The table is copied verbatim via str(ch), so its classes are
        # the ones that would show sanitize() stripping a class value, if it ever did.
        blob = str(self.with_sanitize)
        for cls in ("ltx_tabular", "ltx_tr", "ltx_td"):
            self.assertIn(cls, blob, f"{cls} missing from parsed output")

    def test_table_cell_content_intact(self):
        self.assertEqual(self.with_sanitize, self.without_sanitize)


if __name__ == "__main__":
    unittest.main()
