"""A formula the fast conversion keeps as a picture is drawn as wide against the reader's column as against its own
column on the page (reported in #97: in a two-column paper the formulas came out small, sized by their share of the
whole page, where a column is half of it). No engine: the engine's structured content written here.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import unittest

from textfold import pdfdoc


def paper(column, formula):
    """One page: two paragraphs as wide as a column (a share of the page), and a formula as wide as given."""
    text = lambda t, x: {"type": "text", "content": t, "bbox": [x, 0.1, x + column, 0.2]}
    return {"metadata": {"file_suffix": "pdf"}, "pages": [{"page_idx": 0, "blocks": [
        {"type": "paragraph_title", "content": "1 Method", "level": 1, "bbox": [0.08, 0.05, 0.3, 0.07]},
        text("The model reads each sentence once and keeps what it needs.", 0.08),
        {"type": "equation", "content": "", "image_source": "images/eq1.jpg", "bbox": [0.1, 0.3, 0.1 + formula, 0.34]},
        text("The loss below sums the error over every sentence.", 0.08),
    ]}]}


def width(sc):
    return int(re.search(r'<img src="images/eq1.jpg" alt="formula" width="(\d+)"', pdfdoc.to_markdown(sc, "x.pdf")[2]).group(1))


class FormulaSize(unittest.TestCase):
    def test_half_its_column_is_half_the_readers(self):
        self.assertEqual(width(paper(0.4, 0.2)), 380)   # (a two-column paper: 152 px when sized by the page)
        self.assertEqual(width(paper(0.8, 0.4)), 380)   # (one column: the same share, the same width)

    def test_never_wider_than_the_column(self):
        self.assertEqual(width(paper(0.4, 0.5)), 760)


if __name__ == "__main__":
    unittest.main()
