"""A web page read with a recipe for its site (adapt.py, docs/web-adapt.md): selectors only, the words taken from the
page by TextFold's code and checked against it. And a browser's snapshot (what the app or an extension takes): what
the browser did not show is marked, a note on a mark becomes a footnote, the rest stays out.

Run from the repo root:
    python3 -m unittest discover tests
"""
import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from textfold import adapt, store, webpage

URL = "https://news.example.org/2026/10/rivers"
FILL = ("Rivers carry water, silt and the history of the land they drain, and the people who live beside them read "
        "that history in the colour and the height of the water each spring. ")

PAGE = f"""<html><head><title>Rivers of the plain - Example News</title>
<script type="application/ld+json">{{"@type": "NewsArticle", "isAccessibleForFree": "False",
  "hasPart": {{"@type": "WebPageElement", "isAccessibleForFree": "False", "cssSelector": ".members-only"}}}}</script></head>
<body><nav class="site-nav"><a href="/">Home</a> <a href="/world">World</a></nav>
<main><article class="story" data-testid="Story">
<h1>Rivers of the plain</h1>
<p>{FILL}The flood of 1931 is still the measure<sup class="ref">4</sup><span class="ref-body">Records of the river office, 1931, kept in the county archive.</span> of every spring since.</p>
<aside class="newsletter">Sign up for our newsletter and get the news every morning.</aside>
<table><tr><th>Year</th><th>Height</th></tr><tr><td>1931</td><td><button class="cell">9.4 m</button></td></tr>
<tr><td>2024</td><td><button class="cell">6.1 m</button></td></tr></table>
<figure class="chart"><svg viewBox="0 0 10 10"><text>metres</text><text>1900</text><text>2000</text></svg>
<figcaption>River height each spring, 1900 to 2024.</figcaption></figure>
<p>{FILL}Engineers now read the gauges every hour<span class="tip-mark">*</span><span data-tf-css-hidden="1">Hourly since the new telemetry of 2019.</span>, and the town listens.</p>
<div data-tf-css-hidden="1">Advertisement: buy boots now.</div>
<p>{FILL}</p>
</article></main><footer>Example News, all rights reserved.</footer></body></html>"""

RECIPE = {"format": "textfold/web-recipe", "version": 1, "site": "news.example.org", "article": "article[data-testid='Story']",
          "drop": ["aside.newsletter"], "notes": [{"mark": "sup.ref", "note": "span.ref-body"}],
          "content": ["td button"], "figures": ["article figure:has(svg):not(:has(img))"], "why": "test"}


class Recipe(unittest.TestCase):
    def test_its_shape_is_checked(self):
        self.assertEqual(adapt.recipe_of(json.dumps(RECIPE))["article"], RECIPE["article"])
        for bad, said in ((dict(RECIPE, drop="aside"), "drop"), (dict(RECIPE, notes=[{"mark": "sup"}]), "notes"),
                          (dict(RECIPE, figures=["figure::before"]), "how it looks"), (dict(RECIPE, drop=["a:hover"]), "how it looks"),
                          (dict(RECIPE, format="other"), "web-recipe")):
            with self.assertRaisesRegex(ValueError, said):
                adapt.recipe_of(bad)

    def test_a_selector_it_cannot_read_is_said(self):
        with self.assertRaisesRegex(ValueError, "div\\["):
            adapt.apply(PAGE, URL, adapt.recipe_of(dict(RECIPE, drop=["div["])))


class Read(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.done, cls.matched = adapt.apply(PAGE, URL, adapt.recipe_of(RECIPE))

    def test_the_article_alone_its_furniture_out(self):
        for gone in ("Home", "all rights reserved", "Sign up for our newsletter", "Advertisement"):
            self.assertNotIn(gone, self.html)
        self.assertIn("Rivers of the plain", self.html)
        self.assertEqual(self.matched["aside.newsletter"], 1)

    def test_a_table_s_numbers_drawn_as_buttons_are_its_words(self):
        self.assertIn("<span", self.html.split("9.4 m")[0][-40:])
        self.assertNotIn("<button", self.html)
        self.assertEqual(self.done["content"], 2)

    def test_a_drawing_is_its_caption_with_a_link_to_it(self):
        self.assertNotIn("metres", self.html)
        self.assertIn(f'<a href="{URL}">River height each spring, 1900 to 2024.</a>', self.html)
        self.assertEqual(self.done["figures"], 1)

    def test_the_recipe_s_note_and_the_browser_s_hidden_one_are_footnotes(self):
        self.assertEqual(self.done["notes"], 2)
        self.assertIn('<sup class="ltx_note_mark">4</sup>', self.html)
        self.assertIn('<sup class="ltx_note_mark">*</sup>', self.html)
        self.assertIn("the measure<span class=\"ltx_note", self.html)
        self.assertIn("Records of the river office", self.html)
        self.assertIn("Hourly since the new telemetry", self.html)

    def test_checked_against_the_page_nothing_it_does_not_show(self):
        c = adapt.check(PAGE, URL, self.html, adapt.recipe_of(RECIPE))
        self.assertEqual((c["not on the page (count)"], c["missing (blocks)"], c["notes"]), (0, 0, 2))
        self.assertEqual(c["in figures shown as a link"], 1)

    def test_a_block_the_reading_lacks_is_said_and_where(self):
        thin = self.html.replace("Engineers now read the gauges every hour", "")
        c = adapt.check(PAGE, URL, thin, adapt.recipe_of(RECIPE))
        self.assertEqual(c["missing (blocks)"], 1)
        self.assertEqual(list(c["missing"]), ["p"])   # (where: the block itself, right in the article)


class Signals(unittest.TestCase):
    def test_what_a_recipe_may_have_to_say(self):
        sig = adapt.signals(PAGE, adapt.seen(PAGE, URL))
        self.assertIn("isAccessibleForFree false, hidden part .members-only", sig["paywall"])
        self.assertIn("a browser's snapshot", sig)
        gen = adapt.signals('<div class="BodyWrapper-cuqCAc css-1q2w3e post-content"><p>x</p></div>', adapt.seen("<p>x</p>", URL))
        self.assertEqual(adapt.GENERATED.match("BodyWrapper-cuqCAc") is not None, True)
        self.assertIsNone(adapt.GENERATED.match("post-content"))
        self.assertIsNone(adapt.GENERATED.match("byline"))
        self.assertTrue(gen)

    def test_the_outline_counts_like_siblings_once(self):
        page = "<html><body><main>" + "".join(f"<p>Paragraph {k} has a few words in it.</p>" for k in range(9)) + "</main></body></html>"
        text = adapt.outline(adapt.seen(page, URL))
        self.assertIn("p  ×9", text)
        self.assertNotIn("Paragraph 3", text)


class Generic(unittest.TestCase):
    def test_a_browser_s_snapshot_read_with_no_recipe(self):
        _, html, _ = webpage.read(PAGE, URL)
        self.assertIn("Hourly since the new telemetry", html)   # (a note now, on its mark)
        self.assertNotIn("Advertisement", html)
        self.assertIn('<sup class="ltx_note_mark">*</sup>', html)


class Command(unittest.TestCase):
    def test_try_and_keep(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(store, "DATA", Path(tmp)), \
                mock.patch("textfold.local.prefetch", lambda srcs: {}):
            snap, rec = Path(tmp) / "page.html", Path(tmp) / "recipe.json"
            snap.write_text(PAGE, encoding="utf-8")
            rec.write_text(json.dumps(RECIPE), encoding="utf-8")
            from textfold.__main__ import adapt_cmd
            a = argparse.Namespace(url=URL, snapshot=str(snap), rendered=True, recipe=str(rec), keep=True)
            with redirect_stdout(io.StringIO()) as said:
                self.assertEqual(adapt_cmd(a), 0)
            text = said.getvalue()
            self.assertIn("NOTE: the page marks a paywall", text)
            self.assertIn("words the page does not show: 0", text)
            pid = webpage.pid_of(URL)
            d = store.pdir(pid)
            self.assertEqual((d / "snapshot.html").read_text(encoding="utf-8"), PAGE)
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual((meta["recipe"]["article"], meta["snapshot_kind"]), (RECIPE["article"], "rendered"))
            with redirect_stdout(io.StringIO()) as said:
                self.assertEqual(adapt_cmd(a), 2)   # (in the library already: not over it)
            self.assertIn("in the library already", said.getvalue())


if __name__ == "__main__":
    unittest.main()
