"""A page rendered by a browser and serialized as its reader sees it, by the extension's own script
(extension/snapshot.js): shadow roots spelled out, what the browser does not show marked, each frame's page put where
its iframe is (by its address, as extension/background.js puts it). For trying pages without the extension.

    python3 tools/web_snapshot.py <name> <url> <out>     (playwright installed)   ->  <out>/<name>/rendered.html
"""
import html as htmllib
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = (Path(__file__).resolve().parent.parent / "extension" / "snapshot.js").read_text(encoding="utf-8")


def with_frames(top, frames):
    left = list(frames)

    def one(m):
        src = htmllib.unescape(m.group(2))
        i = next((k for k, f in enumerate(left) if f["url"] == src), None)
        if i is None:
            return m.group(0)
        body = re.search(r"<body[^>]*>(.*)</body>", left.pop(i)["html"], re.S)
        return f'<div{m.group(1)} data-tf-frame-src="{m.group(2)}"{m.group(3)}>{body.group(1) if body else ""}</div>'
    return re.sub(r'<div([^>]*?) data-tf-frame-src="([^"]*)"([^>]*)><!--TF-FRAME-(\d+)--></div>', one, top["html"])


def take(url):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1280, "height": 900}, locale="en-US").new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            pg.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        h = 0
        for _ in range(40):   # scrolled to its end: what loads when seen loads
            pg.mouse.wheel(0, 1600)
            pg.wait_for_timeout(250)
            nh = pg.evaluate("document.documentElement.scrollHeight")
            if pg.evaluate("window.scrollY + innerHeight") >= nh - 5 and nh == h:
                break
            h = nh
        pg.wait_for_timeout(1500)
        top = pg.evaluate(JS)
        frames = []
        for f in pg.frames[1:]:
            try:
                frames.append(f.evaluate(JS))
            except Exception:
                pass
        b.close()
    return with_frames(top, frames)


if __name__ == "__main__":
    name, url, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    (out / name).mkdir(parents=True, exist_ok=True)
    page = take(url)
    (out / name / "rendered.html").write_text(page, encoding="utf-8")
    print(name, len(page), "hidden marked:", page.count("data-tf-css-hidden"), "shadow roots:", page.count("data-tf-shadow"))
