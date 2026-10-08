"""What an arXiv page may carry into the reader.

arXiv's LaTeXML pages are the one source parse.py reads without reshaping them first, and the reader draws their
HTML with innerHTML on the same origin as the local API, so a script in a page could drive that server. They are also
already the shape the reader wants: TikZ pictures are <svg> with <foreignObject> images, figures keep the sizes
LaTeXML gave them, and tables are styled inline. semantic.py's allowlist is made for sources that are rebuilt anyway
(Markdown, JATS, Wikipedia) and would remove all of that, so this is a short list of what is dangerous instead.

Removed:
  elements   script, style, iframe, object (parse.py has already turned the picture ones into <img>), embed, form,
             base, meta, link, and frame, frameset and applet, which load a document the same way iframe does
  svg        <animate> and <set> that target an href or src, which could swap in a javascript: URL after the page loads
  attributes on* handlers; any attribute whose value is a javascript: or vbscript: URL; a data: URL in href,
             xlink:href or src unless it is an image
  style      the declarations that carry url(...) to anywhere but the same page, expression(...), @import, behavior
             or -moz-binding. url(#id) stays: it points at another element of the same SVG, such as the pattern a
             TikZ drawing fills with

Kept as written: svg and everything in it (foreignObject and its images included), width, height, style, classes.
"""
import re

REMOVE = ("script", "style", "iframe", "object", "embed", "form", "base", "meta", "link", "frame", "frameset", "applet")
URL_ATTRS = ("href", "xlink:href", "src")
SMIL = ("animate", "set")   # SVG elements that can set another attribute, an href included, from their own attributes

# a browser drops tabs, newlines and other control characters inside a URL's scheme, so "java\tscript:" is javascript:
_CTRL = re.compile(r"[\x00-\x20\x7f]")
_SCRIPT_URL = re.compile(r"^(?:javascript|vbscript):")
_IMAGE_DATA = re.compile(r"^data:image/")
# CSS lets a function name be spelled with escapes (u\72l) and broken up by comments
_CSS_ESCAPE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})\s?|(.))", re.S)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_RISKY = re.compile(r"expression\(|@import|behavior\s*:|-moz-binding|javascript:|vbscript:")
_CSS_URL = re.compile(r"url\(")


def _flat(value):
    return _CTRL.sub("", value).lower()


def _links_out(flat):
    """Whether a flattened declaration has a url(...) that is not a reference to an id on the same page."""
    for m in _CSS_URL.finditer(flat):
        if not flat[m.end():].lstrip().lstrip("\"'").startswith("#"):
            return True
    return False


def _unescape_css(text):
    def one(m):
        if m.group(1):
            n = int(m.group(1), 16)
            return chr(n) if 0 < n <= 0x10FFFF else ""
        return m.group(2)
    return _CSS_ESCAPE.sub(one, text)


def _clean_style(style):
    """The style attribute without the declarations that can fetch or run something. Returns the attribute as it was
    when nothing is dropped, so a clean page comes through byte for byte; None when every declaration goes."""
    kept, dropped = [], False
    for decl in re.split(r";(?![^(]*\))", style):
        if not decl.strip():
            continue
        probe = _unescape_css(_CSS_COMMENT.sub("", decl))
        flat = _flat(probe)
        if _CSS_RISKY.search(flat) or _links_out(flat):
            dropped = True
        else:
            kept.append(decl.strip())
    if not dropped:
        return style
    return "; ".join(kept) if kept else None


def make_safe(root):
    """Strip root (a BeautifulSoup tag) of what is listed in this module's docstring, in place."""
    for el in list(root.find_all(True)):
        if getattr(el, "decomposed", False):
            continue
        name = (el.name or "").lower()
        if name in REMOVE:
            el.decompose()
            continue
        if name in SMIL and _flat(str(el.get("attributename", ""))).split(":")[-1] in ("href", "src"):
            el.decompose()
            continue
        for key in list(el.attrs):
            low = key.lower()
            value = el.attrs[key]
            text = " ".join(value) if isinstance(value, list) else str(value)
            if low.startswith("on"):
                del el.attrs[key]
            elif low == "style":
                cleaned = _clean_style(text)
                if cleaned is None:
                    del el.attrs[key]
                elif cleaned != text:
                    el.attrs[key] = cleaned
            elif _SCRIPT_URL.match(_flat(text)):
                del el.attrs[key]
            elif low in URL_ATTRS and _flat(text).startswith("data:") and not _IMAGE_DATA.match(_flat(text)):
                del el.attrs[key]
