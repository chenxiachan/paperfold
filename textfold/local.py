"""Documents from this computer, kept as arXiv papers are: papers/<id>/ holds source.html (the normalized HTML that
parse.py reads), the file as it came (source.md), meta.json, and img/ with the images it shows.

A document's id is its title and a hash of its text: the same file opened twice is one paper, and an edited file is a
new one, since the stored layers belong to the text they were made from. A document already stored is not written
again: its source stays the one its layers were made from. Unless it is replaced by name (replace_text: a note edited
where it lives, folded again; or a converted PDF's text, its OCR put right by the reader): then it keeps its id, its
notes and its folder, and its levels are made again.

Its paragraphs are named by their words ("unit_ids": "text", parse.py), so an edit leaves every other paragraph's id,
and the notes and links on it, as they were. (Documents stored before keep the ids they were read with, u<n>, until
their text is replaced.)
"""
import base64
import hashlib
import json
import re
import shutil
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from . import ids, markdown, notes, picture, semantic, store
from .fetch import UA, urlread
from .parse import parse

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_IMG = 15_000_000
KINDS = {".md": "markdown", ".markdown": "markdown", ".mdown": "markdown", ".txt": "markdown"}


def make_id(title, text):
    words = re.findall(r"[a-z0-9]+", title.lower())
    stem, n = [], 0
    for w in words:
        if n + len(w) > 40:
            break
        stem.append(w)
        n += len(w) + 1
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return "md-" + "-".join(stem + [h])


class Images:
    """Where each image of the document is kept (img/NN-name, or NN-name.webp, kept smaller: picture.py): copied from
    beside the file, downloaded, or decoded from a data URI. One that cannot be had is left out (the page shows its
    name), unless the text it is in replaces one whose pictures are kept (kept: that text's img/): then it is the
    picture kept under its name (a converted PDF's pictures were read from the engine's folder, which is gone)."""

    def __init__(self, folder, base, get=None, pre=None, kept=None):
        self.folder, self.base, self.seen, self.get = folder, base, {}, get   # get(url) -> (bytes, url): a source's own
        self.pre = pre or {}   # src -> (bytes, name), read beforehand (prefetch)
        self.kept = {f.name.split("-", 1)[-1]: f for f in sorted(Path(kept).iterdir())} if kept and Path(kept).is_dir() else {}

    def resolve(self, src):
        if src in self.seen:
            return self.seen[src]
        try:
            data, name = self._read(src)
        except Exception:
            data, name = None, ""
        where = None
        old = None if data else self._kept(src)
        if old is not None:   # as it was kept (made smaller then)
            fn = f"{len(self.seen) + 1:02d}-{old.name.split('-', 1)[-1]}"
            self.folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, self.folder / fn)
            where = f"img/{fn}"
        elif data and len(data) <= MAX_IMG:
            name = re.sub(r"[^\w.\-]", "_", name)[-60:] or "image"
            data, fn = picture.compact(data, f"{len(self.seen) + 1:02d}-{name}")   # (kept smaller: picture.py)
            self.folder.mkdir(parents=True, exist_ok=True)
            (self.folder / fn).write_bytes(data)
            where = f"img/{fn}"
        self.seen[src] = where
        return where

    def _kept(self, src):
        """The picture kept for the replaced text under the name resolve gave it then (NN-name, or NN-name.webp)."""
        if not self.kept or src.startswith("data:"):
            return None
        name = re.sub(r"[^\w.\-]", "_", urllib.parse.unquote(urllib.parse.urlparse(src).path).rsplit("/", 1)[-1])[-60:] or "image"
        return self.kept.get(name) or self.kept.get(name + ".webp")

    def _read(self, src):
        if src in self.pre:
            return self.pre[src]
        m = re.match(r"data:image/(png|jpe?g|gif|webp);base64,(.+)$", src, re.S)
        if m:
            return base64.b64decode(m.group(2)), f"image.{m.group(1)}"
        if re.match(r"https?://", src, re.I):
            path = urllib.parse.urlparse(src).path
            if self.get:
                data, _ = self.get(src)
                return (data if data[:4] != b"<!DO" and data[:5] != b"<html" else None), path.rsplit("/", 1)[-1] or "image"
            data, _, headers = urlread(urllib.request.Request(src, headers=UA), 20, MAX_IMG + 1, again=(1,))   # (a page
            # has many pictures, and one missed is tried again: one try more each)
            ctype = (headers.get("Content-Type") or "").split(";")[0].strip()
            if not ctype.startswith("image/"):
                return None, ""
            name = path.rsplit("/", 1)[-1] or "image"
            if Path(name).suffix.lower() not in IMG_EXT:   # a badge's address has none: the page needs it to draw it
                name += {"image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}.get(ctype, "")
            return data, name
        if self.base is None or re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
            return None, ""
        f = (self.base / urllib.parse.unquote(src.split("#")[0].split("?")[0])).resolve()
        if f.suffix.lower() not in IMG_EXT or not f.is_file() or f.stat().st_size > MAX_IMG:
            return None, ""
        return f.read_bytes(), f.name


def prefetch(srcs, workers=6):
    """Pictures on the web, read at the same time rather than one after the other (a README's GIFs take seconds
    each): src -> (bytes, name), for Images(pre=...). One that cannot be read is left to Images to try again."""
    from concurrent.futures import ThreadPoolExecutor

    web = sorted({s for s in srcs if re.match(r"https?://", s or "", re.I)})
    reader = Images(None, None)

    def one(src):
        try:
            return src, reader._read(src)
        except Exception:
            return src, None

    with ThreadPoolExecutor(workers) as ex:
        return {src: got for src, got in ex.map(one, web) if got and got[0]}


def _read_md(text, name):
    """A Markdown text as (its title, its semantic HTML, the meta it is stored with but its id)."""
    kind = KINDS.get(Path(name).suffix.lower())
    if kind is None:
        raise ValueError(f"not a Markdown file: {name}")
    html, fm = markdown.to_html(text)
    title, html = markdown.take_title(html, fm, name)
    meta = {"version": "", "title": title, "authors": fm["authors"], "date": fm["date"],
            "abs_url": "", "html_url": "", "license": fm["license"] if re.match(r"https?://", fm["license"]) else "",
            "source": {"kind": kind, "name": Path(name).name}, "label": Path(name).name, "unit_ids": "text"}
    return title, html, meta


def import_text(text, name="document.md", base=None):
    """Store a document given as text (base: the folder its relative image paths start from, if known). Returns its id."""
    title, html, meta = _read_md(text, name)
    pid = make_id(title, text)
    return store_doc(pid, html, {"id": pid, **meta}, "source.md", text, lambda folder: Images(folder, base).resolve, sizes=True)


# what a replaced text takes with it to previous/: the text, what was read from it, and the levels made from it
REPLACED = ("source.md", "source.html", "meta.json", "img", "layers")
_REPLACING = threading.Lock()   # one replace at a time (the server answers on several threads; a note saved twice)
EDITABLE = ("md-", "pdf-", "doc-")   # a Markdown file's text, and a converted file's (pdfdoc.py), kept as Markdown


def text_of(pid):
    """The Markdown a stored document was read from (source.md), to be edited and put in its place (replace_text); None
    for one that has none to edit (an arXiv paper, a web page, a document from Europe PMC)."""
    d = store.pdir(pid)
    if pid.startswith(EDITABLE) and store.valid_id(pid) and all((d / f).exists() for f in ("meta.json", "source.html", "source.md")):
        return store.read_text(d / "source.md")
    return None


def replace_text(pid, text, name=None, base=None):
    """A stored document's text replaced by an edited one, under the same id: a Markdown file's, or a converted file's
    (a PDF's Markdown, its OCR put right by the reader; its title, authors and source stay the file's, and the file
    stays beside it). Its notes, its folder and the model's replies (llm-cache) stay; its notes are found again in the
    new text (notes.reanchor), its pictures among the ones kept for the old (Images). Its levels belonged to the old
    text: they go to previous/ with it (the one replaced last, notes as they were included), and the next generation
    makes them again from the replies kept, so the model is asked only for the sections whose text changed
    (pipeline.py). Returns the new title. LookupError: no such document, or none with a text to edit (text_of)."""
    with _REPLACING:
        return _replace(pid, text, name, base)


def _replace(pid, text, name, base):
    d = store.pdir(pid)
    if text_of(pid) is None:
        raise LookupError(pid)
    was = json.loads(store.read_text(d / "meta.json"))
    if pid.startswith("md-"):
        title, html, meta = _read_md(text, name or (was.get("source") or {}).get("name") or "document.md")
    else:   # a converted file's: what was read from the file itself (its title, authors, Zotero's) stays
        html, title, meta = markdown.to_html(text)[0], was.get("title", ""), {}
    meta = {**was, **meta, "id": pid, "replaced": store.stamp()}
    old = store.parsed(pid)
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        page, new = ids.freeze(semantic.normalize(html, resolve_img=Images(tmp / "img", base, kept=d / "img").resolve, sizes=True),
                               meta, old, ids.load(pid))
        (tmp / "source.html").write_text(page, encoding="utf-8")
        (tmp / "source.md").write_text(text, encoding="utf-8")
        (tmp / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        prev = d / "previous"
        shutil.rmtree(prev, ignore_errors=True)
        prev.mkdir()
        if (d / "notes.json").exists():
            shutil.copy2(d / "notes.json", prev / "notes.json")
        for f in REPLACED:   # each moved by a rename: a page opened meanwhile reads a file old or new, never half of one
            if (d / f).exists():
                (d / f).rename(prev / f)
            if (tmp / f).exists():
                (tmp / f).rename(d / f)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ids.remember(pid, old, new)
    notes.reanchor(pid, old, new)
    return title


def store_doc(pid, html, meta, raw_name, raw, resolver, sizes=False, old=None):
    """A document's semantic HTML stored as a paper: normalized (with its images, through resolver(img folder)) into
    papers/<pid>/, written whole or not at all, with its paragraphs' ids (ids.freeze; old: the document it replaces,
    whose paragraphs still there keep theirs). A paper already stored stays as it is."""
    d = store.pdir(pid)
    if (d / "meta.json").exists() and (d / "source.html").exists():
        return pid
    gone = ids.load(pid) if old is not None else None
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        page, _ = ids.freeze(semantic.normalize(html, resolve_img=resolver(tmp / "img"), sizes=sizes), meta, old, gone)
        (tmp / "source.html").write_text(page, encoding="utf-8")
        (tmp / raw_name).write_text(raw, encoding="utf-8")
        (tmp / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(d, ignore_errors=True)
        tmp.rename(d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return pid


def _codepage():
    """The system's own encoding for a text file saved in its locale: a Chinese Windows's GBK, a German one's
    Windows-1252, UTF-8 on a Mac. Python 3.11's getencoding() is not swayed by UTF-8 mode, which the app runs in."""
    return store.codepage()


def _read(p):
    """A text file as text: UTF-8 first (the encoding of the web, and of this app's own files), then the system's own
    codepage (a Windows file saved in its locale), and as UTF-8 with stand-ins when neither holds. The BOM comes off
    with -sig. (Not GBK whatever the system: a German file read as GBK turns "für" into "f黵".)"""
    data = p.read_bytes()
    for enc in dict.fromkeys(("utf-8-sig", _codepage())):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def import_file(path):
    p = Path(path).expanduser().resolve()
    return import_text(_read(p), p.name, p.parent)
