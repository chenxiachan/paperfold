"""A Markdown file's formulas and tables as Typora shows them. Its display formulas are numbered, (1), (2), on the
right (Typora's Auto Numbering Math Equations): \\tag{A} gives its own, \\notag and a starred environment none, and
\\eqref{x} elsewhere is the number of the formula \\label{x} names, a link to it. A formula written in LaTeX is marked
pf-tex, for the reader to draw with KaTeX (TeX's type and spacing, as Typora's MathJax), and the page loads KaTeX
first; MathML from elsewhere (a paper's) keeps the browser's drawing, in Latin Modern Math. A table is ruled and
banded (pf-grid). An equation set apart can be selected, and a question about it says so.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import build, local, markdown, notes, semantic, store
from textfold.parse import parse

TEXT = r"""# Diffusion

## The heat equation

The rate depends on how curved the profile is:

$$
\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2}
\label{eq:heat}
$$

Its kernel, in $\eqref{eq:kernel}$, solves $\eqref{eq:heat}$, as equation $\ref{eq:heat}$ says, and $\eqref{nowhere}$ is no label.

$$
u(x, t) = \frac{1}{\sqrt{4 \pi \alpha t}} \int f(y)\, e^{-\frac{(x - y)^2}{4 \alpha t}} \, dy
\label{eq:kernel}
$$

$$
a = b \tag{A}
$$

$$
c = d \tag*{B}
$$

$$
e = f \notag
$$

$$
\begin{align*} g &= h \\ i &= j \end{align*}
$$

$$
\begin{align} k &= l \\ m &= n \end{align}
$$

| Operator | Cost |
|:---------|-----:|
| Heat kernel | $O(n \log n)$ |
| Attention | $O(n^2 d)$ |
"""


def numbers(html):
    return re.findall(r'ltx_tag_equation">([^<]*)<', html)


class Numbered(unittest.TestCase):
    def setUp(self):
        html, _ = markdown.to_html(TEXT)
        self.html = semantic.normalize(html, sizes=True)

    def test_each_display_formula_in_turn(self):
        self.assertEqual(numbers(self.html), ["(1)", "(2)", "(A)", "B", "(3)"])   # (\notag, align*: none)

    def test_a_numbering_environment_is_drawn_as_its_aligned_kind(self):
        self.assertIn(r'alttext="\begin{aligned} k &amp;= l \\ m &amp;= n \end{aligned}"', self.html)
        self.assertIn(r'alttext="\begin{aligned} g &amp;= h \\ i &amp;= j \end{aligned}"', self.html)
        self.assertNotIn(r"\label", self.html)
        self.assertNotIn(r"\tag", self.html)

    def test_a_reference_is_the_number_and_a_link(self):
        self.assertIn('<table class="ltx_equation ltx_eqn_table" id="eq-heat">', self.html)
        self.assertIn('<a class="ltx_ref" href="#eq-kernel">(2)</a>', self.html)   # (named after it: still found)
        self.assertIn('<a class="ltx_ref" href="#eq-heat">(1)</a>', self.html)
        self.assertIn('<a class="ltx_ref" href="#eq-heat">1</a>', self.html)       # (\ref: without the brackets)
        self.assertIn('<a class="ltx_ref">(?)</a>', self.html)

    def test_the_reference_is_a_link_of_the_reader(self):
        doc = parse(self.html, {"id": "md-test"})
        self.assertIn({"tk": "eq", "t": "eq-kernel"}, [{"tk": e["tk"], "t": e["t"]} for e in doc["edges"]])

    def test_a_web_page_formula_is_numbered_only_by_its_tag(self):
        html = semantic.normalize('<p>One.</p><span class="math display">\\[x = 1\\]</span><p>Two.</p>'
                                  '<span class="math display">\\[y = 2 \\tag{3.1}\\]</span>')
        self.assertEqual(numbers(html), ["(3.1)"])


class Drawn(unittest.TestCase):
    def test_latex_is_marked_for_katex(self):
        html, _ = markdown.to_html("A formula $x^2$ here.\n\n$$\n\\operatorname{softmax}(x)\n$$\n")
        out = semantic.normalize(html, sizes=True)
        self.assertEqual(out.count('class="pf-tex"'), 2)

    def test_mathml_from_elsewhere_is_not(self):
        out = semantic.normalize('<p>So <math alttext="x"><semantics><mi>x</mi>'
                                 '<annotation encoding="application/x-tex">x</annotation></semantics></math>.</p>')
        self.assertNotIn("pf-tex", out)

    def test_a_formula_the_converter_cannot_read_is_its_source_for_katex(self):
        with mock.patch("latex2mathml.converter.convert", side_effect=ValueError):
            m = semantic.tex_math(r"\begin{multline} a + b \\ = c \end{multline}", True)
        self.assertEqual((m.name, m["class"], m.get("display")), ("math", ["pf-tex"], "block"))
        self.assertIn("multline", m["alttext"])

    def test_a_table_is_ruled_as_typora_rules_it(self):
        html, _ = markdown.to_html(TEXT)
        self.assertIn('<table class="ltx_tabular ltx_centering pf-grid">', semantic.normalize(html, sizes=True))


def eq_table(latex):
    return ('<table class="ltx_equation ltx_eqn_table"><tbody><tr class="ltx_equation ltx_eqn_row"><td class="ltx_eqn_cell '
            'ltx_eqn_center_padleft"></td><td class="ltx_eqn_cell ltx_align_center"><math alttext="' + latex + '" display="block">'
            '<mi>u</mi></math></td><td class="ltx_eqn_cell ltx_eqn_center_padright"></td></tr></tbody></table>')


# a Markdown document as 0.10.33 stored it: no numbers, no marks, \label in its formula, $\eqref{}$ a formula
STORED = ('<article class="ltx_document"><section class="ltx_section" id="sec-a"><h2 class="ltx_title">A</h2>'
          '<p class="ltx_p">The rate is <math alttext="\\alpha"><mi>α</mi></math>, and see <math alttext="\\eqref{eq:heat}">'
          '<mi>x</mi></math>.</p>' + eq_table("u_t = \\alpha u_{xx} \\label{eq:heat}") + '<p class="ltx_p">Then two more.</p>'
          + eq_table("a = b \\notag") + eq_table("\\begin{align} c &amp;= d \\end{align}")
          + '<figure class="ltx_table"><table class="ltx_tabular ltx_centering"><tr><td class="ltx_td">x</td></tr></table></figure>'
          '</section></article>')


class Stored(unittest.TestCase):
    """A Markdown document stored before 0.10.34 reads as one stored now (semantic.upgrade, from parse), with no new
    import: its paragraphs as they were, so its levels and notes stay where they are."""
    def test_its_formulas_are_numbered_and_drawn_and_its_tables_ruled(self):
        doc = parse(STORED, {"id": "md-old"})
        eqs = [b for b in doc["blocks"] if b["k"] == "eq"]
        self.assertEqual([numbers(b["html"]) for b in eqs], [["(1)"], [], ["(2)"]])
        self.assertEqual(eqs[0]["id"], "eq-heat")
        self.assertIn(r'alttext="\begin{aligned} c &amp;= d \end{aligned}"', eqs[2]["html"])
        self.assertNotIn(r"\label", eqs[0]["html"])
        self.assertTrue(all('class="pf-tex"' in b["html"] for b in eqs))
        atoms = list(doc["atoms"].values())
        self.assertIn('class="pf-tex"', atoms[0]["html"])
        self.assertEqual((atoms[1]["kind"], atoms[1]["html"]), ("ref", '<a class="ltx_ref" href="#eq-heat">(1)</a>'))
        self.assertIn("pf-grid", next(b for b in doc["blocks"] if b["k"] == "fig")["html"])

    def test_its_paragraphs_stay_as_they_were(self):
        with mock.patch("textfold.parse.upgrade", lambda *a: None):
            before = parse(STORED, {"id": "md-old"})
        after = parse(STORED, {"id": "md-old"})
        self.assertEqual({k: u["toks"] for k, u in before["units"].items()}, {k: u["toks"] for k, u in after["units"].items()})
        self.assertEqual(list(before["atoms"]), list(after["atoms"]))

    def test_only_a_markdown_document_stored_before(self):
        self.assertEqual([numbers(b["html"]) for b in parse(STORED, {"id": "2512.23916"})["blocks"] if b["k"] == "eq"], [[], [], []])
        html, _ = markdown.to_html(TEXT)
        new = semantic.normalize(html, sizes=True)
        with mock.patch("textfold.parse.upgrade", side_effect=AssertionError("read twice")):
            parse(new, {"id": "md-new"})   # (stored by 0.10.34: already so)


class Page(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(store, "DATA", Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)

    def test_katex_comes_before_the_reader(self):
        doc = store.assemble(local.import_text(TEXT, "heat.md"))
        app = build.page(doc, app=True)
        self.assertLess(app.index('src="/static/vendor/katex/katex.min.js"'), app.index("/static/reader.js"))
        self.assertIn("katex.min.js", build.page(store.assemble(doc["meta"]["id"]), assets="assets/"))
        self.assertIn('id="katex-css"', build.page(store.assemble(doc["meta"]["id"])))

    def test_a_text_without_formulas_loads_none(self):
        doc = store.assemble(local.import_text("# Plain\n\nWords alone, and nothing else.\n", "plain.md"))
        self.assertNotIn("katex.min.js", build.page(doc, app=True))
        page = build.page(store.assemble(doc["meta"]["id"]))
        self.assertNotIn('id="katex-css"', page)
        self.assertNotIn("Latin Modern Math';", page.split("<style>")[1] if "<style>" in page else "")

    def test_a_page_of_mathml_carries_the_math_font(self):
        doc = store.assemble(local.import_text("# Plain\n\nWords.\n", "plain.md"))
        doc["atoms"]["a0"] = {"kind": "math", "html": '<math alttext="x"><mi>x</mi></math>', "alt": "x", "text": ""}
        self.assertIn("font-family: 'Latin Modern Math'", build.page(doc))


class Asked(unittest.TestCase):
    def test_a_question_about_an_equation_says_so(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(store, "DATA", Path(tmp)):
            pid = local.import_text(TEXT, "heat.md")
            doc = store.assemble(pid)
            uid = next(b["u"] for b in doc["blocks"] if b["k"] == "u")
            notes.put(pid, {"id": "n-1", "kind": "ask", "thread": [], "anchor": {
                "unit": uid, "level": 4, "tokens": None, "sents": None, "eq": "eq-heat",
                "quote": {"exact": r"$\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2}$"}}})
            seen = []
            reply = lambda text, *a, **k: seen.append(text) or ({"out": {"answer": "It is diffusion.", "takeaway": "t", "next": []}}, False)
            with mock.patch("textfold.llm.call", reply):
                notes.ask(pid, "n-1", "What does it say?", {"kind": "agent", "id": "x/codex/m"})
        self.assertIn("selected an equation set apart from the text", seen[0])
        self.assertIn(r"\frac{\partial u}{\partial t}", seen[0])


if __name__ == "__main__":
    unittest.main()
