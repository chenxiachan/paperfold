"""Regression test: adr.parse.parse() must sanitize arXiv/LaTeXML HTML the same way
adr.semantic.normalize()/_sanitize() sanitizes every other ingestion path (Markdown via
local.py, JATS via jats.py, bioRxiv, Wikipedia).

Root cause under test: fetch.py writes the raw arxiv.org/html/<id> bytes straight to
papers/<id>/source.html, and store.parsed() feeds that file straight into parse.parse()
with no sanitization step anywhere on the way. parse() then copies element/attribute
content verbatim into the document payload (str(el), decode_contents(), etc.), so a
<script>, <style>, an on*= handler, or a javascript: href anywhere in the arXiv page
survives into atoms/blocks/chunks and is later written to the DOM via .innerHTML in
web/reader.js (e.g. line 124, 224-230, 1613-1645).

This test is expected to FAIL (RED) against current code: parse() has no sanitize call.
Run from /tmp/paperfold-review so the `adr` package resolves:
    python3 -m unittest discover tests
or directly:
    python3 tests/test_parse_sanitize.py
"""
import json
import re
import unittest

from adr.parse import parse

# A minimal arXiv/LaTeXML-shaped page (article.ltx_document, ltx_section/ltx_title/ltx_p
# classes the parser depends on) carrying five independent injection vectors:
#   1. a top-level <script> sibling of the sections (parse.py block()'s raw fallback)
#   2. a top-level <style> sibling (same path)
#   3. a <script> inside a section heading (decode_contents() in heading(), parse.py:192-193)
#   4. an onclick= handler on an inline <a> (atom() stores str(el) verbatim, parse.py:131-134)
#   5. a javascript: href on that same <a>
MALICIOUS_HTML = """
<html><body>
<article class="ltx_document">
<script>alert('top')</script>
<style>body{background:url(evil)}</style>
<section class="ltx_section" id="s1">
<h2 class="ltx_title ltx_title_section">Intro<script>alert('head')</script></h2>
<div class="ltx_para"><p class="ltx_p">hello <a href="javascript:alert(1)" onclick="y()">link</a></p></div>
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
