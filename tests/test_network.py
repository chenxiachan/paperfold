"""A network that drops a connection now and then (issue #76): every download of TextFold's (fetch.urlread) is asked
again after 1, 2, 5 and 10 seconds when it fails on the way (a connection reset, a TLS stream cut short, a timeout) or
the server is busy (429, 5xx, its Retry-After kept to). An answer that will not change (404, a certificate refused) is
raised at once. Five failed tries read as net-down:<host>, which the app says in words, with Continue. An arXiv paper
whose HTML came and whose metadata did not asks only for its metadata the next time.

Run from the repo root:
    python3 -m unittest discover tests
"""
import email.message
import http.client
import json
import re
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from textfold import fetch, webpage

WEB = Path(__file__).resolve().parent.parent / "textfold" / "web"


class Response:
    def __init__(self, body=b"<html>ok</html>", url="https://arxiv.org/html/2512.23916v2", ctype="text/html", cut=False):
        self.body, self.url, self.cut = body, url, cut
        self.headers = email.message.Message()
        self.headers["Content-Type"] = ctype

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, amt=None):
        if self.cut:
            raise http.client.IncompleteRead(self.body[:3])
        return self.body if amt is None else self.body[:amt]

    def geturl(self):
        return self.url


def busy(code, after=None):
    headers = email.message.Message()
    if after is not None:
        headers["Retry-After"] = after
    return urllib.error.HTTPError("https://arxiv.org/html/2512.23916", code, "busy", headers, None)


DROPPED = urllib.error.URLError(ssl.SSLEOFError(8, "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"))


class Tries(unittest.TestCase):
    def run_with(self, *answers, **kw):
        waits = []
        with mock.patch("urllib.request.urlopen", side_effect=list(answers)) as opened, \
                mock.patch("textfold.fetch.time.sleep", waits.append):
            try:
                return fetch.urlread("https://arxiv.org/html/2512.23916", **kw), waits, opened.call_count
            except Exception as e:
                return e, waits, opened.call_count

    def test_a_dropped_connection_is_asked_again(self):
        got, waits, n = self.run_with(DROPPED, ConnectionResetError(54, "reset"), Response())
        self.assertEqual((got[0], got[1], waits, n), (b"<html>ok</html>", "https://arxiv.org/html/2512.23916v2", [1, 2], 3))

    def test_a_body_cut_short_or_a_timeout_too(self):
        got, waits, _ = self.run_with(Response(cut=True), TimeoutError("timed out"), Response())
        self.assertEqual((got[0], waits), (b"<html>ok</html>", [1, 2]))

    def test_five_failed_tries_read_as_the_host_unreachable(self):
        got, waits, n = self.run_with(*[DROPPED] * 5)
        self.assertIsInstance(got, fetch.Unreachable)
        self.assertIsInstance(got, urllib.error.URLError)   # (what tries another address still does)
        self.assertEqual((str(got), waits, n), ("net-down:arxiv.org", [1, 2, 5, 10], 5))

    def test_an_answer_that_will_not_change_is_raised_at_once(self):
        got, waits, n = self.run_with(busy(404))
        self.assertEqual((got.code, waits, n), (404, [], 1))
        refused = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
        got, waits, n = self.run_with(refused)
        self.assertEqual((got, waits, n), (refused, [], 1))

    def test_a_busy_server_is_waited_for_as_it_asks(self):
        got, waits, _ = self.run_with(busy(429, "3"), busy(503), busy(429, "600"), Response())
        self.assertEqual((got[0], waits), (b"<html>ok</html>", [3, 2, 60]))   # (its own wait; a minute at most)
        got, waits, n = self.run_with(*[busy(502)] * 5)
        self.assertEqual((got.code, n), (502, 5))

    def test_what_the_caller_checks_is_raised_before_the_body(self):
        def check(r):
            raise ValueError("web-pdf")
        got, waits, n = self.run_with(Response(), check=check)
        self.assertEqual((str(got), waits, n), ("web-pdf", [], 1))


class Paper(unittest.TestCase):
    def test_the_html_that_came_is_not_asked_for_again(self):
        html = b'<html><img src="2512.23916v2/x1.png"></html>'
        abs_page = b'<meta name="citation_title" content="A paper"><meta name="citation_author" content="Chen, Xia">'
        asked = []

        def answer(req, timeout=None):
            asked.append(req.full_url)
            if "/html/" in req.full_url:
                return Response(html, "https://arxiv.org/html/2512.23916v2")
            if len(asked) < 7:   # the metadata: every try of the first fetch fails
                raise DROPPED
            return Response(abs_page, "https://arxiv.org/abs/2512.23916")

        with tempfile.TemporaryDirectory() as tmp, mock.patch("urllib.request.urlopen", side_effect=answer), \
                mock.patch("textfold.fetch.time.sleep"):
            with self.assertRaises(fetch.Unreachable):
                fetch.fetch("2512.23916", Path(tmp))
            d = Path(tmp) / "papers" / "2512.23916"
            self.assertEqual(((d / "source.html").read_bytes(), (d / "meta.json").exists()), (html, False))
            fetch.fetch("2512.23916", Path(tmp))
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual([u for u in asked if "/html/" in u], ["https://arxiv.org/html/2512.23916"])   # (once)
            self.assertEqual((meta["title"], meta["version"], meta["html_url"]),
                             ("A paper", "v2", "https://arxiv.org/html/2512.23916v2"))
            self.assertEqual([f.name for f in d.iterdir() if f.name.endswith(".part")], [])


class Page(unittest.TestCase):
    def test_a_wall_still_answers_at_once_and_a_bad_gateway_is_asked_again(self):
        waits = []
        with mock.patch("urllib.request.urlopen", side_effect=[busy(503)]), mock.patch("textfold.fetch.time.sleep", waits.append):
            with self.assertRaisesRegex(ValueError, "web-blocked"):
                webpage._get("https://example.org/post")
        with mock.patch("urllib.request.urlopen", side_effect=[busy(502), Response(b"<p>words</p>", "https://example.org/post")]), \
                mock.patch("textfold.fetch.time.sleep", waits.append):
            self.assertEqual(webpage._get("https://example.org/post")[:2], (b"<p>words</p>", "https://example.org/post"))
        self.assertEqual(waits, [1])


class Said(unittest.TestCase):
    def test_every_interface_language_says_it(self):
        js = (WEB / "i18n.js").read_text(encoding="utf-8")
        said = re.findall(r'net_down: "([^"]*)"', js)
        self.assertEqual(len(said), js.count("web_blocked:"))
        self.assertTrue(all("{host}" in s for s in said))
        self.assertIn("/^net-down:/.test(msg)", (WEB / "app.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
