"""adr/latexml_safe.py on its own: each hostile spelling is removed, each harmless look-alike is kept.

The page-level tests (test_parse_sanitize.py, test_parse_keeps_figures.py) go through parse(); these go straight at
make_safe() with one small fragment per case, including the spellings a browser reads as a script URL.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from bs4 import BeautifulSoup

from adr.latexml_safe import make_safe


def cleaned(fragment):
    root = BeautifulSoup(f"<html><body><div id='r'>{fragment}</div></body></html>", "lxml").find(id="r")
    make_safe(root)
    return str(root).lower()


class RemovedTest(unittest.TestCase):
    def check(self, fragment, *gone):
        out = cleaned(fragment)
        for g in gone:
            self.assertNotIn(g, out, f"{g!r} survived in {out}")

    def test_elements(self):
        for tag in ("script", "style", "iframe", "embed", "form", "object", "applet"):
            self.check(f"<{tag}>x</{tag}><p>keep</p>", f"<{tag}")
        for void in ("<base href='http://x'>", "<meta http-equiv='refresh' content='0;url=x'>", "<link rel='stylesheet' href='x'>"):
            self.check(void + "<p>keep</p>", "<base", "<meta", "<link")
        self.assertIn("<p>keep</p>", cleaned("<script>x</script><p>keep</p>"))

    def test_script_urls_in_any_spelling(self):
        for url in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "java\tscript:alert(1)",
                    "java\nscript:alert(1)", "&#106;avascript:alert(1)", "vbscript:x"):
            self.check(f'<a href="{url}">x</a>', "javascript", "vbscript")

    def test_script_urls_on_svg_and_mathml(self):
        self.check('<svg><a xlink:href="javascript:alert(1)"><text>x</text></a></svg>', "javascript")
        self.check('<svg><use href="javascript:alert(1)"/></svg>', "javascript")
        self.check('<math href="javascript:alert(1)"><mi>x</mi></math>', "javascript")

    def test_event_handlers(self):
        self.check('<svg onload="x()"><rect onclick="y()"/></svg>', "onload", "onclick")
        self.check('<img src="a.png" onerror="x()" ONMOUSEOVER="y()">', "onerror", "onmouseover")

    def test_smil_that_rewrites_an_href(self):
        self.check('<svg><a><animate attributeName="href" to="javascript:alert(1)"/></a></svg>', "<animate", "javascript")
        self.check('<svg><a><set attributeName="xlink:href" to="javascript:alert(1)"/></a></svg>', "<set", "javascript")

    def test_data_urls_that_are_not_images(self):
        self.check('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>', "data:text/html")
        self.check('<img src="data:text/html,<script>">', "data:text/html")

    def test_style_that_fetches_or_runs(self):
        for st in ("background:url(http://evil/x)", "background:url(//evil/x)", "width:expression(alert(1))",
                   "b\\61ckground:u\\72l(//evil/x)", "background:ur/**/l(//evil/x)", "behavior:url(x.htc)",
                   "-moz-binding:url(x)", "background:url(javascript:alert(1))"):
            out = cleaned(f'<td style="{st};color:red">x</td>')
            self.assertNotIn("evil", out, st)
            self.assertNotIn("expression", out, st)
            self.assertNotIn("behavior", out, st)
            self.assertNotIn("binding", out, st)
            self.assertIn("color:red", out, f"the harmless declaration beside {st!r} was lost")


class KeptTest(unittest.TestCase):
    def test_svg_and_what_is_inside_it(self):
        out = cleaned('<svg width="9" height="9"><g><foreignObject><img src="a.png" width="3" height="3"></foreignObject></g></svg>')
        for kept in ("<svg", "<foreignobject", 'src="a.png"', 'width="3"', 'height="3"'):
            self.assertIn(kept, out)

    def test_harmless_urls_and_styles(self):
        out = cleaned('<a href="https://x.org/a">h</a><a href="#s">s</a><a href="mailto:a@b.c">m</a>'
                      '<img src="data:image/png;base64,AAAA"><td style="padding:0 4pt;width:30%">c</td>'
                      '<g style="fill:url(#p)"></g>')
        for kept in ('href="https://x.org/a"', 'href="#s"', 'href="mailto:a@b.c"', "data:image/png;base64,aaaa",
                     "padding:0 4pt;width:30%", "fill:url(#p)"):
            self.assertIn(kept, out)

    def test_smil_on_something_else_is_kept(self):
        self.assertIn("<animate", cleaned('<svg><rect><animate attributeName="width" to="5"/></rect></svg>'))

    def test_the_text_of_a_removed_script_does_not_leak_into_a_neighbour(self):
        self.assertEqual(cleaned("<p>a</p><script>alert(1)</script><p>b</p>").count("alert"), 0)


if __name__ == "__main__":
    unittest.main()
