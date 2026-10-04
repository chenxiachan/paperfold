"""Reader pages. The same reader in two modes:
  app     served by the local server, with the sidebar, the language menu that can generate, settings
  static  one self-contained file (python -m adr export): CSS, JS, data and images all inside
"""
import base64
import io
import json
import urllib.parse
from html import escape

from PIL import Image

from . import store
from .fetch import fetch_images

WEB = store.ROOT / "web"
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400..700&'
         'family=Source+Serif+4:ital,opsz,wght@0,8..60,400..700;1,8..60,400..700&display=swap">')


def data_uri(f, max_side=1600):
    if f.suffix.lower() == ".svg":  # vector stays vector: crisp at every zoom, and small for line plots
        svg = f.read_text(errors="replace")
        # "&" escaped too: in the page's src="…" an entity of the SVG's own (&quot;) would be decoded first and break it
        return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg, safe=" /:=;,'()-._~!*+@?$")
    im = Image.open(f)
    im.thumbnail((max_side, max_side))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def inline_images(doc):
    """Figures go inside the page: one file that still works when forwarded, previewed, or opened on a phone."""
    meta = doc["meta"]
    cache = store.pdir(meta["id"]) / "img"
    local = fetch_images(doc["images"], meta["html_url"], cache)
    uris = {src: data_uri(cache / path.split("/", 1)[1]) for src, path in local.items()}
    for b in doc["blocks"]:
        if "html" in b:
            for src, uri in uris.items():
                b["html"] = b["html"].replace(f'src="{src}"', f'src="{uri}"')


def payload(doc, app):
    data = {k: doc[k] for k in ("meta", "atoms", "units", "chunks", "blocks", "bib", "edges", "alias")}
    data["app"] = app
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def page(doc, app=False):
    inline_images(doc)
    t = (WEB / "template.html").read_text()
    if app:
        head = FONTS + '<link rel="stylesheet" href="/static/reader.css"><link rel="stylesheet" href="/static/app.css">'
        scripts = '<script src="/static/i18n.js"></script><script src="/static/reader.js"></script><script src="/static/app.js"></script>'
        side, cls = '<aside id="sidebar" class="collapsed"></aside>', "app"
    else:
        head = FONTS + f"<style>{(WEB / 'reader.css').read_text()}</style>"
        scripts = f"<script>{(WEB / 'i18n.js').read_text()}</script><script>{(WEB / 'reader.js').read_text()}</script>"
        side, cls = "", "static"
    return (t.replace("{{TITLE}}", escape(doc["meta"]["title"])).replace("{{HEAD}}", head).replace("{{CLASS}}", cls)
             .replace("{{SIDEBAR}}", side).replace("{{SCRIPTS}}", scripts).replace("{{DATA}}", payload(doc, app)))


def export(pid):
    doc = store.assemble(pid)
    out = store.DATA / "out" / pid
    out.mkdir(parents=True, exist_ok=True)
    f = out / "index.html"
    f.write_text(page(doc, app=False))
    return f
