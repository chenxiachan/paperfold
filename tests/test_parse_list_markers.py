"""A label (a list's marker, a section's number, a figure's label) and a link's text are read as the page shows them:
a formula's annotations, its LaTeX or content MathML, are not drawn (RetrieveVGGT's markers read "∙\\bullet", #128).

Run from the repo root:
    python3 -m unittest tests.test_parse_list_markers
"""
import unittest

from textfold.parse import parse

DOT = r'<math><semantics><mo>∙</mo><annotation encoding="application/x-tex">\bullet</annotation></semantics></math>'


class ParseListMarkersTest(unittest.TestCase):
    def test_only_the_visible_math_is_read_as_a_list_marker(self):
        cases = (
            ("ul", r'<math><semantics><mo>∙</mo><annotation encoding="application/x-tex">\bullet</annotation>'
                   r'</semantics></math>', "∙"),
            ("ul", r'<math><semantics><mo>†</mo><annotation encoding="application/x-tex">\dagger</annotation>'
                   r'</semantics></math>', "†"),
            ("ul", r'<math><semantics><mo>⋆</mo><annotation encoding="application/x-tex">\star</annotation>'
                   r'</semantics></math>', "⋆"),
            ("ol", '(<math><semantics><mn>2</mn><annotation-xml encoding="MathML-Content"><cn>2</cn>'
                   '</annotation-xml></semantics></math>)', "(2)"),
            ("ol", '<strong>(a)</strong>', "(a)"),
            ("ul", '<math><mo>∗</mo></math>', "∗"),
            ("ul", None, "•"),
        )
        for list_tag, marker, expected in cases:
            with self.subTest(marker=marker):
                label = f'<span class="ltx_tag ltx_tag_item">{marker}</span>' if marker is not None else ""
                doc = parse(rf'''
                    <article class="ltx_document">
                    <{list_tag}><li>{label}<p class="ltx_p">An item with
                      <math><semantics><mo>∙</mo><annotation encoding="application/x-tex">\bullet</annotation>
                      </semantics></math> in its text.</p></li></{list_tag}>
                    </article>
                ''', {"id": "2601.00001", "title": "Lists"})
                unit, = doc["units"].values()
                atom, = doc["atoms"].values()
                self.assertEqual(unit["marker"], expected)
                self.assertEqual(atom["alt"], r"\bullet")

    def test_a_number_a_label_and_a_link_as_shown(self):
        doc = parse(rf'''
            <article class="ltx_document">
            <section class="ltx_section" id="S1"><h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">{DOT}1 </span>Results</h2>
            <div class="ltx_para"><p class="ltx_p">As in <a class="ltx_ref" href="#S1"><span class="ltx_text ltx_ref_title">{DOT} Results</span></a>,
              see <cite class="ltx_cite">Smith {DOT} Lee</cite>.</p></div>
            <figure class="ltx_figure" id="F1"><img src="x.png"/>
              <figcaption class="ltx_caption"><span class="ltx_tag ltx_tag_figure">Figure 1{DOT}: </span>A figure.</figcaption></figure>
            </section>
            </article>
        ''', {"id": "2601.00001", "title": "Labels"})
        self.assertEqual(doc["chunks"][0]["num"], "∙1")
        texts = sorted((a["kind"], a["text"]) for a in doc["atoms"].values() if a["kind"] in ("ref", "cite"))
        self.assertEqual(texts, [("cite", "Smith ∙ Lee"), ("ref", "∙ Results")])
        fig, = (b for b in doc["blocks"] if b["k"] == "fig")
        self.assertEqual(fig["label"], "Figure 1∙")
