"""A Markdown file as semantic HTML, for semantic.normalize.

CommonMark, with GitHub's tables and strikethrough, footnotes, definition lists, YAML front matter, and math:
$...$ and $$...$$ by Pandoc's rules (so "$5 and $10" stays money), and \\(...\\) and \\[...\\] as chat models write
them. HTML written in the file (a GitHub README's centred logo, its badges, a <details>) is kept as far as
semantic.normalize's allowlist goes: no script, no handler, no javascript: link survives it.
"""
import re

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


def _md():
    return (MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
            .enable(["table", "strikethrough"])
            .use(front_matter_plugin).use(footnote_plugin).use(deflist_plugin)
            .use(anchors_plugin, min_level=1, max_level=6)   # GitHub's heading ids: a README's "#get-started" lands
            .use(dollarmath_plugin, allow_space=False, allow_digits=False, double_inline=True))


def math_delimiters(text):
    """\\(x\\) -> $x$, and \\[ ... \\] on lines of their own -> $$ ... $$, outside code (where markdown-it would read
    the backslashes as escapes and leave bare brackets)."""
    out, block, fence = [], [], None
    for line in text.splitlines(keepends=True):
        m = FENCE.match(line)
        if fence is None and m:
            out.append(_convert("".join(block)))
            block, fence = [], m.group(1)
            out.append(line)
        elif fence is not None:
            out.append(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
        else:
            block.append(line)
    out.append(_convert("".join(block)))
    return "".join(out)


def _convert(text):
    code = []

    def keep(m):
        code.append(m.group(0))
        return f"\x00{len(code) - 1}\x00"

    text = re.sub(r"(`+)(?:.|\n)*?\1", keep, text)
    text = re.sub(r"(?ms)^([ \t]*)\\\[(.+?)\\\][ \t]*$", lambda m: f"{m.group(1)}$$\n{m.group(2).strip()}\n{m.group(1)}$$", text)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: m.group(0) if "$" in m.group(1) else f"${m.group(1).strip()}$", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: code[int(m.group(1))], text)


def front_matter(src):
    """The few fields a document's YAML front matter is read for: title, author(s), date, license."""
    meta, key = {}, None
    for line in src.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [_unquote(x) for x in re.split(r",\s*(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)", val[1:-1]) if x.strip()]
            elif val:
                meta[key] = _unquote(val)
            else:
                meta[key] = []
        elif key and re.match(r"^\s*-\s+", line) and isinstance(meta.get(key), list):
            meta[key].append(_unquote(re.sub(r"^\s*-\s+", "", line)))
    authors = meta.get("authors") or meta.get("author") or []
    return {"title": meta.get("title") if isinstance(meta.get("title"), str) else "",
            "authors": [authors] if isinstance(authors, str) else [a for a in authors if isinstance(a, str)],
            "date": meta.get("date") if isinstance(meta.get("date"), str) else "",
            "license": meta.get("license") if isinstance(meta.get("license"), str) else ""}


def _unquote(s):
    s = s.strip()
    return s[1:-1] if len(s) > 1 and s[0] == s[-1] and s[0] in "\"'" else s


def to_html(text):
    """(html, front matter) for a Markdown text."""
    md = _md()
    text = math_delimiters(text.replace("\r\n", "\n"))
    tokens = md.parse(text)
    fm = next((t.content for t in tokens if t.type == "front_matter"), "")
    return md.renderer.render(tokens, md.options, {}), front_matter(fm)


def take_title(html, fm, name):
    """The document's title, and its HTML without the heading that gave it: the front matter's title, else a first
    heading that is the only top-level one, else the file's name."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    h1s = body.find_all("h1")
    first = h1s[0] if h1s else None
    # the first heading counts when nothing but pictures and links comes before it (a README's logo and badges)
    if first is not None and "".join(s for s in first.find_all_previous(string=True) if not s.find_parent("a")).strip():
        first = None
    title = fm.get("title") or ""
    if first is not None and (len(h1s) == 1 or (title and first.get_text(" ", strip=True) == title)):
        title = title or first.get_text(" ", strip=True)
        first.decompose()
    if not title:
        stem = re.sub(r"\.(md|markdown|txt)$", "", name.split("/")[-1], flags=re.I)
        title = re.sub(r"[_-]+", " ", stem).strip() or "Untitled"
    return title, body.decode_contents()
