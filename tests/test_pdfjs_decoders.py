"""PDF.js has its decoders wherever TextFold shows a PDF (#108). The pictures of a scanned page (CCITT, as fax scans
are, and JBIG2), JPEG 2000 pictures and colour profiles are decoded by WebAssembly files PDF.js asks for by name; without
them it leaves the pictures out, and a scanned page shows blank. They are kept beside PDF.js, served by the app, and
written into a saved page that carries its PDF.

Run from the repo root:
    python3 -m unittest discover tests
"""
import base64
import http.client
import json
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from textfold import build, local, pdf, server, store

DECODERS = ("jbig2.wasm", "openjpeg.wasm", "qcms_bg.wasm")
PDFJS = build.VENDOR / "pdfjs"


class Kept(unittest.TestCase):
    def test_each_one_the_worker_asks_for_is_there(self):
        worker = (PDFJS / "pdf.worker.min.mjs").read_text(encoding="utf-8")
        for name in DECODERS:
            with self.subTest(name=name):
                self.assertIn(name, worker)   # (a newer PDF.js that renames one fails here)
                self.assertEqual((PDFJS / "wasm" / name).read_bytes()[:4], b"\0asm")

    def test_served_by_the_app(self):
        f = server.vendor_file("pdfjs/wasm/jbig2.wasm")
        self.assertEqual(f, (PDFJS / "wasm" / "jbig2.wasm").resolve())
        self.assertEqual(server.VENDOR_TYPES[f.suffix], "application/wasm")


class Jobs:
    def list(self):
        return []


class Saved(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        web = root / "web"
        web.mkdir()
        for name in (*server.STATIC, "app.html", "template.html"):
            shutil.copy2(build.WEB / name, web / name)
        (root / "scan.pdf").write_bytes(b"%PDF-1.5\n%%EOF\n")
        patches = [mock.patch.object(build, "WEB", web), mock.patch.object(store, "DATA", root / "data"),
                   mock.patch.object(pdf, "has_source", return_value=True), mock.patch.object(pdf, "path", return_value=root / "scan.pdf")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        server.PAGES.clear()
        self.addCleanup(server.PAGES.clear)
        self.pid = local.import_text("# A scan\n\nA paragraph read from a scanned page.\n")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(Jobs()))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def test_a_saved_page_with_its_pdf_carries_them(self):
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=20)
        c.request("POST", "/api/export", json.dumps({"paper": self.pid, "pdf": True}),
                  headers={"Host": "localhost", "Content-Type": "application/json"})
        r = c.getresponse()
        html = r.read().decode("utf-8")
        c.close()
        self.assertEqual(r.status, 200)
        for name in DECODERS:
            with self.subTest(name=name):
                self.assertIn(json.dumps(name), html)
                self.assertIn(base64.b64encode((PDFJS / "wasm" / name).read_bytes()).decode()[:200], html)


if __name__ == "__main__":
    unittest.main()
