"""Regression test: the safety pass in parse.parse() must leave an arXiv/LaTeXML page's figures alone.

The first version of the fix reused semantic.py's allowlist, which removed every <svg> (TikZ pictures and the images
LaTeXML places inside them through <foreignObject>), the width and height of <img>, and inline styles. Parsing real
arXiv pages with and without it showed 43 pictures lost in 6 papers, so this holds the line in the other direction:
a page with nothing dangerous in it comes out the same with the safety pass as without it, and the things below are
named so a failure says which one went.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import unittest

from bs4 import BeautifulSoup

import adr.parse as parse_mod
from adr.parse import parse

CLEAN_HTML = """
<html><body>
<article class="ltx_document">
<section class="ltx_section" id="s1">
<h2 class="ltx_title ltx_title_section">Introduction</h2>
<div class="ltx_para"><p class="ltx_p">
See <a href="https://example.com">this site</a>, <a href="#s1">this section</a> and
<a href="mailto:a@example.com">a mail link</a>: the formula <math alttext="E=mc^2"><mi>E</mi></math> holds.
</p></div>
<figure class="ltx_figure" id="fig1">
<svg class="ltx_picture" id="tikz1" width="120" height="80" viewBox="0 0 120 80">
<defs><pattern id="pgfupat1" width="4" height="4"><rect width="2" height="2"/></pattern></defs>
<g style="--ltx-fill-color:url(#pgfupat1);fill:red"><rect x="1" y="1" width="50" height="30"/></g>
<foreignObject x="10" y="10" width="60" height="40">
<img class="ltx_graphics" src="x1.png" width="60" height="40" alt="panel">
</foreignObject>
</svg>
<img class="ltx_graphics" src="fig2.png" width="300" height="200" style="width:300px" alt="two">
<object data="fig3.svg" type="image/svg+xml" width="200" height="100">a sketch</object>
<figcaption class="ltx_caption"><span class="ltx_tag">Figure 1:</span> A picture.</figcaption>
</figure>
<table class="ltx_tabular" id="tab1">
<tr class="ltx_tr"><td class="ltx_td" style="padding:0 4pt;border-top:1px solid #000">a</td><td class="ltx_td">b</td></tr>
</table>
</section>
</article>
</body></html>
"""
META = {"id": "2401.00002", "title": "T", "authors": [], "date": "", "abs_url": "",
        "html_url": "", "license": ""}


def _figure(doc):
    """The figure block's HTML, parsed again so a test can ask about elements and attributes, not their order."""
    html = next(b["html"] for b in doc["blocks"] if b.get("k") == "fig")
    return BeautifulSoup(html, "lxml")


def _blob(doc):
    return json.dumps(doc).lower().replace('\\"', '"')


class ParseKeepsFiguresTest(unittest.TestCase):
    def setUp(self):
        self.with_safety = parse(CLEAN_HTML, dict(META))
        real = parse_mod.make_safe
        parse_mod.make_safe = lambda root: None
        try:
            self.without_safety = parse(CLEAN_HTML, dict(META))
        finally:
            parse_mod.make_safe = real
        self.blob = _blob(self.with_safety)

    def test_a_clean_page_parses_exactly_as_without_the_safety_pass(self):
        self.assertEqual(self.without_safety, self.with_safety)

    def test_tikz_picture_keeps_its_svg_and_the_image_in_its_foreignobject(self):
        fig = _figure(self.with_safety)
        svg = fig.find("svg", id="tikz1")
        self.assertIsNotNone(svg, "the <svg> picture was removed")
        self.assertEqual((svg["width"], svg["height"]), ("120", "80"))
        inner = svg.find("foreignobject").find("img")
        self.assertIsNotNone(inner, "the image inside <foreignObject> was removed")
        self.assertEqual((inner["src"], inner["width"], inner["height"]), ("x1.png", "60", "40"))

    def test_img_keeps_width_height_and_style(self):
        img = _figure(self.with_safety).find("img", src="fig2.png")
        self.assertEqual((img["width"], img["height"], img["style"]), ("300", "200", "width:300px"))

    def test_the_svg_figure_given_as_an_object_still_becomes_an_image(self):
        self.assertIn('src="fig3.svg"', self.blob)
        self.assertNotIn("<object", self.blob)
        self.assertIn("fig3.svg", self.with_safety["images"])

    def test_inline_styles_survive_including_a_same_page_url(self):
        self.assertIn("padding:0 4pt;border-top:1px solid #000", self.blob)
        self.assertIn("--ltx-fill-color:url(#pgfupat1);fill:red", self.blob)

    def test_links_and_math_survive(self):
        for kept in ('href="https://example.com"', 'href="#s1"', 'href="mailto:a@example.com"', 'alttext="e=mc^2"'):
            self.assertIn(kept, self.blob)

    def test_unit_and_chunk_counts_unchanged(self):
        self.assertEqual(len(self.without_safety["units"]), len(self.with_safety["units"]))
        self.assertEqual(len(self.without_safety["chunks"]), len(self.with_safety["chunks"]))


if __name__ == "__main__":
    unittest.main()
