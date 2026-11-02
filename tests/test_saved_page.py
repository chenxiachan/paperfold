"""A saved web page dropped on the landing (#82): its longest <article> was its article, whatever it held, so a page
whose one <article> is an advert's box was read as that box (the article's words gone), or as nothing (bad-file). An
<article> or <main> is taken now only when it holds most of what trafilatura finds the page's article to be; else the
body is, without the site's header, footer, side columns and that box. A page whose <article> is its article reads as
before, in Chinese too. No network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from textfold import office

ARTICLE = ("<h1>Real article title</h1>"
           "<p>This is the first paragraph of the real article. It has plenty of words so that any extractor would treat "
           "it as the main content of the page.</p>"
           "<p>This is the second paragraph of the real article, again long enough to be considered body text by "
           "trafilatura and similar tools.</p>"
           "<p>A third paragraph, so the article clearly outweighs the promo widget below in visible text.</p>")


def page(body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Repro</title></head><body><header>Site header</header>'
            f"{body}<footer>Site footer</footer></body></html>")   # (as a browser saves a page: its charset said)


class SavedPage(unittest.TestCase):
    def read(self, html):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.html"
            f.write_text(html, encoding="utf-8")
            out = office.convert(f, Path(tmp) / "out")
            return json.dumps(json.loads((out / "structured_content.json").read_text(encoding="utf-8")), ensure_ascii=False)

    def test_an_advert_s_empty_box_is_not_the_article(self):
        got = self.read(page(f'<div class="content">{ARTICLE}</div><article class="promo"><style>.promo{{color:red}}</style>'
                             '<div class="promo"></div></article>'))   # (was: bad-file)
        self.assertIn("first paragraph of the real article", got)
        self.assertIn("A third paragraph", got)
        self.assertNotIn("Site footer", got)

    def test_an_advert_s_link_is_not_the_article(self):
        got = self.read(page(f'<div class="content">{ARTICLE}</div><article class="promo"><a href="#">Advertisement</a></article>'))
        self.assertIn("second paragraph of the real article", got)   # (was: "Advertisement" alone)
        self.assertNotIn("Advertisement", got)

    def test_an_article_that_is_the_article(self):
        got = self.read(page(f'<nav>Home World Sport</nav><article>{ARTICLE}</article><aside>Most read today</aside>'))
        self.assertIn("first paragraph of the real article", got)
        self.assertNotIn("Home World Sport", got)
        self.assertNotIn("Most read today", got)

    def test_a_blog_with_more_comments_than_article(self):
        # (its comments outside the <article>, longer than it: they are not part of the text it must hold)
        comments = "".join(f'<li class="comment"><div class="comment-content"><p>Comment {k}. I read this twice and I still '
                           "wonder whether the floods were measured the same way before the war, since the gauges were moved "
                           "and the records from those years look different from the ones that came after.</p></div></li>"
                           for k in range(1, 9))
        got = self.read(page(f'<article class="post">{ARTICLE}</article><div id="comments" class="comments-area">'
                             f'<h2 class="comments-title">8 comments</h2><ol class="comment-list">{comments}</ol></div>'))
        self.assertIn("first paragraph of the real article", got)
        self.assertNotIn("Comment 3.", got)

    def test_a_comment_in_a_heading(self):
        # (trafilatura stops on it: MDN's and Hugging Face's pages, saved, read before the change and must still)
        got = self.read(page(f"<main><h2>Overview<!-- toc --></h2>{ARTICLE.replace('<h1>', '<h2>').replace('</h1>', '<!-- x --></h2>')}</main>"))
        self.assertIn("first paragraph of the real article", got)

    def test_an_article_in_chinese(self):
        zh = ("<h1>河流的记录</h1>" + "".join(f"<p>第{k}段：河务局保存水位计已有一百年，记录显示春汛随山上的积雪起落，年复一年，"
                                              "这座小城至今仍按同样缓慢的节奏生活。</p>" for k in range(1, 5)))
        got = self.read(page(f'<nav>首页 国际 体育</nav><article>{zh}</article>'))
        self.assertIn("河务局保存水位计", got)
        self.assertNotIn("首页 国际 体育", got)
        # (an article in Chinese has few spaces: not taken for an advert's box when the body is read)
        got = self.read(page(f'<div class="content">{zh}</div><article><a href="#">广告</a></article><article>{zh[:60]}</article>'))
        self.assertIn("河务局保存水位计", got)
        self.assertNotIn("广告", got)


if __name__ == "__main__":
    unittest.main()
