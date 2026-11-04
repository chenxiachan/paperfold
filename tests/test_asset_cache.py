"""Shared assets can be reused between documents, but never under a stale content version."""
import hashlib
import http.client
import re
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from textfold import build, local, server, store


class Jobs:
    def list(self):
        return []


class AssetCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        web = root / "web"
        web.mkdir()
        for name in (*server.STATIC, "app.html", "template.html"):
            shutil.copy2(build.WEB / name, web / name)
        for obj, key, value in ((build, "WEB", web), (store, "DATA", root / "data")):
            patch = mock.patch.object(obj, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        for obj, key, value in ((server.agents, "wait_scanned", None),
                                (server, "models_payload", {"selectedName": "", "askName": "", "bridge": None}),
                                (server, "listed", [])):
            patch = mock.patch.object(obj, key, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)
        server.PAGES.clear()
        self.addCleanup(server.PAGES.clear)
        self.pid = local.import_text("# Cache fixture\n\nA paragraph that needs no model.\n")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(Jobs()))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def get(self, path, host="localhost"):
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=10)
        c.request("GET", path, headers={"Host": host})
        r = c.getresponse()
        out = r.status, dict(r.getheaders()), r.read()
        c.close()
        return out

    def url(self, name):
        key = hashlib.sha256((build.WEB / name).read_bytes()).hexdigest()
        return f"/static/{name}?v={key}"

    def test_versions_match_served_bytes_and_allow_private_caching(self):
        for name, kind in server.STATIC.items():
            with self.subTest(name=name):
                status, headers, data = self.get(self.url(name))
                self.assertEqual(status, 200)
                self.assertEqual(data, (build.WEB / name).read_bytes())
                self.assertEqual(headers["Content-Type"], kind + "; charset=utf-8")
                self.assertEqual(headers["Cache-Control"], "private, max-age=31536000, immutable")

    def test_bare_incorrect_and_duplicate_versions_are_not_cached(self):
        valid = self.url("app.js")
        for url in ("/static/app.js", "/static/app.js?v=old", valid + "&v=old", "/static/app.js?v="):
            with self.subTest(url=url):
                status, headers, data = self.get(url)
                self.assertEqual(status, 200)
                self.assertEqual(data, (build.WEB / "app.js").read_bytes())
                self.assertEqual(headers["Cache-Control"], "no-store")

    def test_landing_and_reader_version_only_shared_assets(self):
        for path, expected in (("/", set(server.STATIC) - {"reader.js"}), (f"/p/{self.pid}", set(server.STATIC))):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                urls = re.findall(r'(?:src|href)="(/static/(?!vendor/)[^"]+)"', body.decode())
                self.assertEqual(set(urls), {self.url(name) for name in expected})
                self.assertIn(b'/static/vendor/fonts/fonts.css"', body)

    def test_changed_asset_updates_cached_reader_html_and_old_url_is_not_immutable(self):
        old = self.url("app.js")
        self.assertIn(old.encode(), self.get(f"/p/{self.pid}")[2])
        with (build.WEB / "app.js").open("ab") as f:
            f.write(b"\n// Updated asset fixture.\n")
        fresh = self.url("app.js")
        self.assertNotEqual(old, fresh)
        for path in ("/", f"/p/{self.pid}"):
            body = self.get(path)[2]
            self.assertIn(fresh.encode(), body)
            self.assertNotIn(old.encode(), body)
        status, headers, data = self.get(old)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(data, (build.WEB / "app.js").read_bytes())
        self.assertIn("immutable", self.get(fresh)[1]["Cache-Control"])

    def test_dynamic_responses_missing_files_and_other_hosts_are_not_cached(self):
        for path, expected in (("/api/papers", 200), ("/static/missing.js", 404)):
            status, headers, _ = self.get(path)
            self.assertEqual(status, expected)
            self.assertEqual(headers["Cache-Control"], "no-store")
        status, headers, _ = self.get(self.url("app.js"), host="attacker.example")
        self.assertEqual(status, 421)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_vendor_policy_and_standalone_export_are_unchanged(self):
        folder = build.WEB / "vendor" / "fonts"
        folder.mkdir(parents=True)
        (folder / "fixture.woff2").write_bytes(b"font fixture")
        self.assertEqual(self.get("/static/vendor/fonts/fixture.woff2")[1]["Cache-Control"], "max-age=86400")
        doc = store.assemble(self.pid)
        with mock.patch.object(build, "fonts_head", return_value=""), mock.patch.object(build, "app_assets", side_effect=AssertionError):
            exported = build.page(doc, app=False)
        self.assertIn((build.WEB / "reader.js").read_text(encoding="utf-8"), exported)
        self.assertNotIn('/static/reader.js?v=', exported)


if __name__ == "__main__":
    unittest.main()
