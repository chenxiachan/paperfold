"""A title-page picture and its adjacent caption-only figure (arXiv 2503.11651, 2507.11539) stay together.
Synthetic HTML only; no paper, network, model or personal library is used.
"""
import unittest
from unittest import mock

from bs4 import BeautifulSoup

from textfold import parse as parser, store, translate
from textfold.tokens import plain

META = {'id': '2401.00001', 'title': 'Teasers', 'authors': [], 'date': '', 'abs_url': '', 'html_url': '', 'license': ''}
PIC = '<div class="ltx_para" id="p0"><img class="ltx_graphics" src="teaser.png" id="g1" width="685" height="250"></div>'
CAP = '<figure class="ltx_figure" id="F1"><figcaption><span class="ltx_tag">Figure 1:</span>A picture <math alttext="x"><mi>x</mi></math>.</figcaption></figure>'
SEC = '<section class="ltx_section" id="S1"><h2 class="ltx_title">Method</h2><p class="ltx_p">Existing paragraph <math alttext="y"><mi>y</mi></math>.</p></section>'


def source(front):
    return '<article class="ltx_document">' + front + SEC + '</article>'


def read(front):
    return parser.parse(source(front), dict(META))


class Teasers(unittest.TestCase):
    def test_adjacent_picture_and_caption_stay_before_the_first_heading(self):
        doc = read(PIC + CAP)
        fig = next(b for b in doc['blocks'] if b['k'] == 'fig')
        self.assertEqual(fig['id'], 'F1')
        self.assertEqual(fig['cap'], 'F1.cap')
        self.assertEqual(fig['chunk'], 'S1')
        self.assertLess(doc['blocks'].index(fig), next(i for i, b in enumerate(doc['blocks']) if b['k'] == 'h'))
        self.assertEqual(BeautifulSoup(fig['html'], 'lxml').img['id'], 'g1')
        self.assertFalse(any('teaser.png' in b.get('html', '') for b in doc['blocks'] if b is not fig))
        self.assertIn('F1.cap', doc['chunks'][0]['units'])

    def test_logical_block_exposes_a_translatable_caption(self):
        doc = read('<div class="ltx_logical-block">' + PIC + CAP + '</div>')
        self.assertEqual(doc['units']['F1.cap']['role'], 'caption')
        self.assertIn('F1.cap', translate.gaps(doc, 'zh'))
        self.assertEqual([b['id'] for b in doc['blocks'] if b['k'] == 'fig'], ['F1'])
        self.assertIn('teaser.png', next(b['html'] for b in doc['blocks'] if b['k'] == 'fig'))

    def test_existing_unit_and_atom_ids_survive_a_new_caption(self):
        front = '<div class="ltx_logical-block">' + PIC + CAP + '</div>'
        with mock.patch.object(parser, 'teasers', return_value=(set(), set())):
            before = read(front)
        after = read(front)
        for uid, unit in before['units'].items():
            self.assertEqual(after['units'][uid], unit)
        for aid, atom in before['atoms'].items():
            self.assertEqual(after['atoms'][aid], atom)
        self.assertEqual(set(after['units']) - set(before['units']), {'F1.cap'})

    def test_existing_caption_translation_is_reused(self):
        doc = read(PIC + CAP)
        tr = {'units': {'F1.cap': {'toks': [{'t': '图注译文'}]}}, 'chunks': {}}
        store.apply_tr(doc, 'zh', tr)
        self.assertEqual(plain(doc['units']['F1.cap']['tr']['zh']['toks'], doc['atoms']), '图注译文')
        self.assertNotIn('F1.cap', translate.gaps(doc, 'zh'))

    def test_after_the_abstract_the_caption_is_read_with_it(self):
        abstract = '<div class="ltx_abstract"><p class="ltx_p" id="ab">An abstract.</p></div>'
        doc = read(abstract + '<div class="ltx_logical-block">' + PIC + CAP + '</div>')
        fig = next(b for b in doc['blocks'] if b['k'] == 'fig')
        self.assertEqual(fig['chunk'], 'abstract')
        self.assertEqual(doc['chunks'][0]['units'], ['ab', 'F1.cap'])

    def test_intervening_content_is_not_skipped(self):
        for gap in ('<h2 class="ltx_title">A title</h2>', '<p class="ltx_p">Bang!</p>',
                    '<p class="ltx_p">A short line</p>', '<p class="ltx_p"></p>', 'intervening text'):
            with self.subTest(gap=gap):
                doc = read(PIC + gap + CAP)
                self.assertNotIn('teaser.png', next(b['html'] for b in doc['blocks'] if b['k'] == 'fig'))

    def test_ambiguous_pictures_and_inline_objects_stay_as_written(self):
        cases = [PIC + PIC + CAP, PIC.replace('</div>', 'text</div>') + CAP,
                 PIC.replace('ltx_graphics', 'ltx_graphics pf-inline') + CAP,
                 PIC.replace('</div>', '<math><mi>x</mi></math></div>') + CAP]
        for front in cases:
            with self.subTest(front=front):
                doc = read(front)
                self.assertNotIn('teaser.png', next(b['html'] for b in doc['blocks'] if b['k'] == 'fig'))

    def test_a_complete_figure_and_its_subfigures_are_unchanged(self):
        front = '<figure class="ltx_figure" id="F1">' + PIC + CAP.replace('id="F1"', 'id="panel"') + '</figure>'
        with mock.patch.object(parser, 'teasers', return_value=(set(), set())):
            before = read(front)
        self.assertEqual(before, read(front))

    def test_a_wrapper_with_other_content_is_not_unwrapped(self):
        for extra in ('<p class="ltx_p">Bang!</p>', '<p class="ltx_p"></p>', '<svg><text>A diagram</text></svg>'):
            with self.subTest(extra=extra):
                doc = read('<div class="ltx_logical-block">' + PIC + CAP + extra + '</div>')
                self.assertNotIn('F1.cap', doc['units'])
                self.assertTrue(any('ltx_logical-block' in b.get('html', '') for b in doc['blocks']))

    def test_whitespace_and_comments_between_the_pair_are_allowed(self):
        self.assertIn('teaser.png', next(b['html'] for b in read(PIC + '\n<!-- layout -->\n' + CAP)['blocks'] if b['k'] == 'fig'))

    def test_new_captions_keep_their_source_order_and_cross_references(self):
        pair = '<div class="ltx_logical-block">' + PIC + CAP + '</div>'
        front = pair + pair.replace('F1', 'F2').replace('teaser.png', 'second.png')
        html = source(front).replace('Existing paragraph', '<a href="#F1">Figure 1</a> Existing paragraph')
        doc = parser.parse(html, dict(META))
        self.assertEqual(doc['chunks'][0]['units'][:2], ['F1.cap', 'F2.cap'])
        self.assertEqual([b['id'] for b in doc['blocks'] if b['k'] == 'fig'], ['F1', 'F2'])
        self.assertTrue(any(e['t'] == 'F1.cap' and e['tk'] == 'unit' for e in doc['edges']))

    def test_anonymous_figures_keep_their_generated_ids_and_placement(self):
        front = PIC + CAP.replace(' id="F1"', '')
        with mock.patch.object(parser, 'teasers', return_value=(set(), set())):
            before = read(front)
        self.assertEqual(before, read(front))

    def test_an_existing_complete_title_page_figure_keeps_its_placement(self):
        front = '<figure class="ltx_figure" id="F1">' + PIC + '<figcaption>A complete figure.</figcaption></figure>'
        doc = read(front)
        self.assertEqual(doc['blocks'][0]['k'], 'h')
        self.assertEqual(doc['blocks'][1]['id'], 'F1')


if __name__ == '__main__':
    unittest.main()
