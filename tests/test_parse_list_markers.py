import unittest

from textfold.parse import parse


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
