"""Regression test: parse.parse() must take out what can run script from an arXiv/LaTeXML page.

fetch.py writes the raw arxiv.org/html/<id> bytes to papers/<id>/source.html and store.parsed() feeds that to
parse(). parse() copies element HTML verbatim into the document (str(el), decode_contents()), and web/reader.js draws
it with innerHTML on the local server's own origin. adr/latexml_safe.py is what stands in between; this test holds the
line in that direction (the other direction, that figures and sizes survive, is test_parse_keeps_figures.py).

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import re
import unittest

from adr.parse import parse

# A minimal arXiv/LaTeXML-shaped page (article.ltx_document, ltx_section/ltx_title/ltx_p
# classes the parser depends on) carrying independent injection vectors, the last group inside an SVG:
#   1. a top-level <script> sibling of the sections (parse.py block()'s raw fallback)
#   2. a top-level <style> sibling (same path)
#   3. a <script> inside a section heading (decode_contents() in heading(), parse.py:192-193)
#   4. an onclick= handler on an inline <a> (atom() stores str(el) verbatim, parse.py:131-134)
#   5. a javascript: href on that same <a>
#   6. SVG: an xlink:href javascript: link, <animate> and <set> that rewrite an href, a data:text/html
#      image src with an onerror handler, a style with an external url()
MALICIOUS_HTML = """
<html><body>
<article class="ltx_document">
<script>alert('top')</script>
<style>body{background:url(evil)}</style>
<section class="ltx_section" id="s1">
<h2 class="ltx_title ltx_title_section">Intro<script>alert('head')</script></h2>
<div class="ltx_para"><p class="ltx_p">hello <a href="javascript:alert(1)" onclick="y()">link</a></p></div>
<figure class="ltx_figure" id="f1">
<svg class="ltx_picture" width="100" height="60">
<a xlink:href="javascript:alert(2)"><text>x</text></a>
<animate attributeName="href" to="javascript:alert(3)"/>
<set attributeName="xlink:href" to="javascript:alert(4)"/>
<foreignObject><img src="data:text/html;base64,PHNjcmlwdD4=" onerror="z()"></foreignObject>
<rect style="fill:url(http://evil.example/x);width:5px"/>
</svg>
<figcaption class="ltx_caption">A picture.</figcaption>
</figure>
</section>
</article>
</body></html>
"""

META = {"id": "2401.00001", "title": "T", "authors": [], "date": "", "abs_url": "",
        "html_url": "", "license": ""}

ON_ATTR = re.compile(r'\son[a-z]+\s*=', re.I)


class ParseSanitizeTest(unittest.TestCase):
    def setUp(self):
        self.doc = parse(MALICIOUS_HTML, dict(META))

    def _all_html_fragments(self):
        """Every piece of HTML parse.parse() hands to the reader: atom html, block/raw
        html, chunk heading html, bib html -- the exact strings reader.js assigns via
        .innerHTML (web/reader.js:124, 224-230, 1613-1645)."""
        frags = []
        for a in self.doc["atoms"].values():
            frags.append(a.get("html", ""))
        for b in self.doc["blocks"]:
            if "html" in b:
                frags.append(b["html"])
        for c in self.doc["chunks"]:
            frags.append(c.get("html", "") or "")
        frags.append(self.doc.get("bib", "") or "")
        return frags

    def test_no_script_or_style_elements_survive(self):
        frags = self._all_html_fragments()
        for frag in frags:
            self.assertNotIn("<script", frag.lower(), f"<script> survived in: {frag!r}")
            self.assertNotIn("<style", frag.lower(), f"<style> survived in: {frag!r}")

    def test_no_event_handler_attributes_survive(self):
        frags = self._all_html_fragments()
        for frag in frags:
            self.assertIsNone(ON_ATTR.search(frag), f"on*= handler survived in: {frag!r}")

    def test_no_javascript_href_survives(self):
        frags = self._all_html_fragments()
        for frag in frags:
            self.assertNotIn("javascript:", frag.lower(), f"javascript: href survived in: {frag!r}")

    def test_svg_vectors_are_removed_and_the_picture_stays(self):
        blob = json.dumps(self.doc).lower().replace('\\"', '"')
        for bad in ("<animate", "<set ", "data:text/html", "evil.example"):
            self.assertNotIn(bad, blob, f"{bad!r} survived")
        # ...while the picture around them is kept: the svg, its foreignObject and image, the harmless style
        for good in ("<svg", "<foreignobject", "<img", "width:5px"):
            self.assertIn(good, blob, f"{good!r} was removed")

    def test_whole_payload_is_clean(self):
        """Belt-and-braces: serialize the entire doc payload (what store.assemble()/build.page()
        eventually ship to the reader) and check none of the four markers leak anywhere."""
        blob = json.dumps(self.doc)
        self.assertNotIn("<script", blob.lower())
        self.assertNotIn("<style", blob.lower())
        self.assertIsNone(ON_ATTR.search(blob))
        self.assertNotIn("javascript:", blob.lower())


if __name__ == "__main__":
    unittest.main()
