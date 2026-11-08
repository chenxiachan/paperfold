"""An endpoint of no preset (Settings › Add provider › Custom) saved without a name is named after its host, as its
base URL names it, so that each has a name and a key of its own: two such endpoints used to be both "Custom", the
second saved over the first (#115). No model, no network: the endpoints are only saved, never asked.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import shutil
import site
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from textfold import providers

ROOT = Path(__file__).resolve().parent.parent


class NameOf(unittest.TestCase):
    def test_the_host(self):
        for base, name in [("https://api.atlascloud.ai/v1", "atlascloud.ai"), ("https://gateway.example.org/v1/", "gateway.example.org"),
                           ("http://127.0.0.1:8000/v1", "127.0.0.1:8000"), ("www.Example.com/v1", "example.com"),
                           ("https://user:secret@api.example.com/v1", "example.com"), ("", "Custom")]:
            self.assertEqual(providers.name_of(base), name, base)


class Saved(unittest.TestCase):
    """On a server of its own, with this test's HOME and settings."""

    @classmethod
    def setUpClass(cls):
        cls.home = Path(tempfile.mkdtemp())
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        env = {**os.environ, "HOME": str(cls.home), "USERPROFILE": str(cls.home), "TEXTFOLD_DATA": str(cls.home / "data"),
               "TEXTFOLD_NO_MODELS": "1", "PYTHONUSERBASE": site.getuserbase()}
        cls.proc = subprocess.Popen([sys.executable, "-m", "textfold", "serve", "--port", str(cls.port)], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(150):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/papers", timeout=1)
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        shutil.rmtree(cls.home, True)

    def call(self, path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def saved(self):
        s = json.loads((self.home / ".textfold" / "settings.json").read_text(encoding="utf-8"))
        return sorted((p["key"], p["name"], p["base"]) for p in s["providers"])

    def test_two_endpoints_without_a_name(self):
        for base in ("https://api.atlascloud.ai/v1", "https://gateway.example.org/v1/"):
            code, d = self.call("/api/providers/save", {"preset": "custom", "name": "", "base": base, "api_key": "k", "models": ["m"]})
            self.assertEqual(code, 200, d)
        code, d = self.call("/api/providers/save", {"preset": "custom", "name": "My gateway", "base": "https://api.example.net/v1",
                                                    "api_key": "k", "models": ["m"]})
        self.assertEqual(code, 200, d)
        self.assertEqual(self.saved(), [("custom-atlascloud-ai", "atlascloud.ai", "https://api.atlascloud.ai/v1"),
                                        ("custom-gateway-example-org", "gateway.example.org", "https://gateway.example.org/v1"),
                                        ("custom-my-gateway", "My gateway", "https://api.example.net/v1")])
        settings = json.loads((self.home / ".textfold" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("m (atlascloud.ai)", {m["name"] for p in providers.ui_providers(settings) for m in p["models"]})
        for key in ("custom-atlascloud-ai", "custom-gateway-example-org", "custom-my-gateway"):
            self.call("/api/providers/remove", {"key": key})
        self.assertEqual(self.saved(), [])


if __name__ == "__main__":
    unittest.main()
