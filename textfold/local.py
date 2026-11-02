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
import difflib
import hashlib
import json
import os
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
    name), unless the text it is in replaces one whose pictures are kept (kept: that text's img/, and its history's,
    the later first): then it is the picture kept under its name (a converted PDF's pictures were read from the
    engine's folder, which is gone)."""

    def __init__(self, folder, base, get=None, pre=None, kept=()):
        self.folder, self.base, self.seen, self.get = folder, base, {}, get   # get(url) -> (bytes, url): a source's own
        self.pre = pre or {}   # src -> (bytes, name), read beforehand (prefetch)
        self.kept = {f.name.split("-", 1)[-1]: f for k in kept if Path(k).is_dir() for f in sorted(Path(k).iterdir())}

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


# what a replaced text takes with it: the text (the one last generated kept in its history: keep_text), what was read
# from it, its pictures (kept there too), and the levels made from it
REPLACED = ("source.md", "source.html", "meta.json", "img", "layers")
HISTORY = store.HISTORY
_REPLACING = threading.Lock()   # one replace at a time (the server answers on several threads; a note saved twice)
EDITABLE = ("md-", "pdf-", "doc-")   # a Markdown file's text, and a converted file's (pdfdoc.py), kept as Markdown


def text_of(pid):
    """The Markdown a stored document was read from (source.md), to be edited and put in its place (replace_text); None
    for one that has none to edit (an arXiv paper, a web page, a document from Europe PMC)."""
    d = store.pdir(pid)
    if pid.startswith(EDITABLE) and store.valid_id(pid) and all((d / f).exists() for f in ("meta.json", "source.html", "source.md")):
        return store.read_text(d / "source.md")
    return None


def original(pid):
    """The text a document had when it was last generated (or read in), before the edits since (keep_text), or None:
    the page's edit history shows what they changed in it, and puts any of it back (app.js, review)."""
    f = store.pdir(pid) / HISTORY / "source.md"
    return store.read_text(f) if store.valid_id(pid) and f.exists() else None


def keep_text(d):
    """The text a stored document (its folder, d) has now, kept as an edit takes its place (replace_text) if it is the
    first since the document was last generated, until it is generated again (settle): the page's edit history shows
    each change the edits made to it, and puts any of them back (app.js, review). As history/source.md, its
    pictures in history/img, where a text put back finds them (Images: a converted PDF's were read from the engine's
    folder, which is gone)."""
    hist = d / HISTORY
    if (hist / "source.md").exists():
        return
    hist.mkdir(exist_ok=True)
    if (d / "img").is_dir():
        shutil.copytree(d / "img", hist / "img", dirs_exist_ok=True)
    shutil.copy2(d / "source.md", hist / "source.md")   # (last: a history with its text has its pictures)


def settle(pid):
    """A document generated again in every language its levels were in when its text was edited (store.pending): its
    edit history goes, as the page said it would, and the languages it was to be generated in with it."""
    d = store.pdir(pid)
    if not (d / HISTORY).exists():   # (never edited, or settled before)
        return
    meta = json.loads(store.read_text(d / "meta.json"))
    if store.pending(pid, meta, store.read(pid, "en")):
        return
    shutil.rmtree(d / HISTORY, ignore_errors=True)
    if meta.pop("pending", None) is not None:
        tmp = d / "meta.json.tmp"
        tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, d / "meta.json")


def replace_text(pid, text, name=None, base=None):
    """A stored document's text replaced by an edited one, under the same id: a Markdown file's, or a converted file's
    (a PDF's Markdown, its OCR put right by the reader; its title, authors and source stay the file's, and the file
    stays beside it). Its notes, its folder and the model's replies (llm-cache) stay; its notes are found again in the
    new text (notes.reanchor), its pictures among the ones kept for the old (Images). The text it was last generated
    from is kept at its first edit (keep_text): each change the edits made to it can be put back until it is generated
    again; put back whole, nothing is kept. Its levels belonged to the old text: they go, and the next generation makes
    them again from the replies kept, so the model is asked only for the sections whose text changed (pipeline.py);
    none at all for a text put back. The languages they were in are kept in its meta ("pending", with those of an edit
    before not made again yet): the page says they are to be generated again, and does it for all of them at once
    (app.js), so a text can be put right in several places first and the model asked once. Returns the new title.
    LookupError: no such document, or none with a text to edit (text_of)."""
    with _REPLACING:
        return _replace(pid, text, name, base)


def _html_of(pid, text, was, name=None):
    """A stored document's text (its Markdown) as HTML, with the title and meta it gives (a converted file's are what was
    read from the file itself: its title, authors, Zotero's, stay)."""
    if pid.startswith("md-"):
        return _read_md(text, name or (was.get("source") or {}).get("name") or "document.md")
    return was.get("title", ""), markdown.to_html(text)[0], {}


def _replace(pid, text, name, base):
    d = store.pdir(pid)
    if text_of(pid) is None:
        raise LookupError(pid)
    was = json.loads(store.read_text(d / "meta.json"))
    title, html, meta = _html_of(pid, text, was, name)
    en = store.read(pid, "en")
    had = ([store.text_lang(pid, en)] if en else []) + store.languages(pid)
    meta = {**was, **meta, "id": pid, "replaced": store.stamp(), "pending": list(dict.fromkeys(had + was.get("pending", [])))}
    old = store.parsed(pid)
    tmp, gone = d.with_name(d.name + ".tmp"), d.with_name(d.name + ".old")
    for f in (tmp, gone):
        shutil.rmtree(f, ignore_errors=True)
        f.mkdir(parents=True)
    try:
        page, new = ids.freeze(semantic.normalize(html, resolve_img=Images(tmp / "img", base, kept=(d / HISTORY / "img", d / "img")).resolve,
                                                  sizes=True), meta, old, ids.load(pid))
        (tmp / "source.html").write_text(page, encoding="utf-8")
        (tmp / "source.md").write_text(text, encoding="utf-8")
        (tmp / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        if store.read_text(d / "source.md") != text:   # (not when saved again unchanged)
            keep_text(d)
        for f in REPLACED:   # each moved by a rename: a page opened meanwhile reads a file old or new, never half of one
            if (d / f).exists():
                (d / f).rename(gone / f)
            if (tmp / f).exists():
                (tmp / f).rename(d / f)
        shutil.rmtree(d / "previous", ignore_errors=True)   # (an earlier TextFold's, the text before the last edit)
        if original(pid) == text:   # every edit put back: none to show
            shutil.rmtree(d / HISTORY, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(gone, ignore_errors=True)
    ids.remember(pid, old, new)
    notes.reanchor(pid, old, new)
    return title


MARK = 0xE000   # Unicode's private use: characters no text has, put in a text to see where its places are read (places)


def places(pid, spans):
    """Where each of the places [from, to) of a document's text (text_of: its Markdown; the edit history's, app.js) is
    read on its page, found by a mark put at each end of each and the text read as the page is (two characters of
    Unicode's private use for each place): {words: [{unit, tokens: [first, last]}], at: {unit, token, after}}, the words
    it is (one run for each paragraph it is in; none for words taken out) and the word before which (after: after
    which, at a paragraph's end) it begins; or {section: id}, for a place in a heading; or None, for one read nowhere (a
    picture's address) or where the marks changed what the text is read as (one before a list's dash). A paragraph is
    known by its words: the one with the same words, the marks aside, among the page's. LookupError: no such
    document, or none with a text."""
    text = text_of(pid)
    if text is None:
        raise LookupError(pid)
    spans = [(min(max(0, int(a)), len(text)), min(max(int(a), int(b)), len(text))) for a, b in spans][:(0xF8FF - MARK) // 2]

    def back(at):   # a mark goes before the white space it follows: at a line's start, it would be read as its first
        while at and text[at - 1].isspace():   # word, and a heading's # or a list's dash, after it, as words
            at -= 1
        return at
    ends = sorted([(back(a), k, 0) for k, (a, b) in enumerate(spans)] + [(back(b), k, 1) for k, (a, b) in enumerate(spans)])
    marked, last = [], 0
    for at, k, end in ends:
        marked += [text[last:at], chr(MARK + 2 * k + end)]
        last = at
    marked.append(text[last:])
    d = store.pdir(pid)
    _, html, meta = _html_of(pid, "".join(marked), json.loads(store.read_text(d / "meta.json")))
    _, doc = ids.freeze(semantic.normalize(html, resolve_img=lambda src: src), meta)
    now = store.parsed(pid)
    plain = lambda x: re.sub("[\ue000-\uf8ff]", "", x)
    found = {}   # mark -> (unit, offset in its text) or ("§", section)
    ours, theirs = list(now["units"].items()), list(doc["units"].items())
    texts = [notes._spans(u["toks"], now["atoms"])[0] for _, u in ours]
    marks = [notes._spans(u["toks"], doc["atoms"])[0] for _, u in theirs]
    same = {i + k: j + k for i, j, n in difflib.SequenceMatcher(None, [plain(x).strip() for x in marks], texts, autojunk=False).get_matching_blocks()
            for k in range(n)}
    last = None
    for i, x in enumerate(marks):
        j = same.get(i)
        if j is None and plain(x).strip() or j is None and last is None:
            continue
        lead, gone = len(plain(x)) - len(plain(x).lstrip()), 0   # (a mark of its own, after a line's end: a space before it)
        for at, c in enumerate(x):
            if MARK <= ord(c) <= 0xF8FF:   # (marks alone where a paragraph ends make one: the end of the one before)
                found[ord(c)] = (j, min(len(texts[j]), max(0, at - gone - lead))) if j is not None else (last, len(texts[last]))
                gone += 1
        last = j if j is not None else last
    heads = [(c["num"] + c["title"]) for c in now["chunks"]]
    for i, j, n in difflib.SequenceMatcher(None, [plain(c["num"] + c["title"]) for c in doc["chunks"]], heads, autojunk=False).get_matching_blocks():
        for k in range(n):
            for c in doc["chunks"][i + k]["num"] + doc["chunks"][i + k]["title"]:
                if MARK <= ord(c) <= 0xF8FF:
                    found[ord(c)] = ("§", now["chunks"][j + k]["id"])
    out = []
    for k in range(len(spans)):
        a, b = found.get(MARK + 2 * k), found.get(MARK + 2 * k + 1)
        crossed = "\n" in text[back(spans[k][0]):spans[k][0]]   # (its marks went back past a line's end)
        if crossed and spans[k][0] == spans[k][1] and a is not None and a[0] == "§":   # (into a heading: the first paragraph under it)
            a = b = next(((i, 0) for i, (_, u) in enumerate(ours) if u.get("chunk") == a[1]), None)
        if b is not None and b[0] == "§":   # (ending in a heading: its start, gone back past the line's end, may be in the paragraph before)
            out.append({"section": b[1]})
            continue
        if b is not None and (a is None or a[0] == "§"):   # (beginning a paragraph after a heading: its start went back into it)
            a = (b[0], 0)
        if a is None or b is None:
            out.append(None)
            continue
        if a[1] >= len(texts[a[0]]) and crossed and (
                a[0] < b[0] or a == b and a[0] + 1 < len(ours) and ours[a[0] + 1][1].get("chunk") == ours[a[0]][1].get("chunk")):
            a = (a[0] + 1, 0)   # (gone back past a paragraph's end: it begins the next one, under the same heading)
            b = max(a, b)
        out.append({"words": [w for w in (_words(now, ours[i], a[1] if i == a[0] else 0, b[1] if i == b[0] else len(texts[i]))
                                          for i in range(a[0], b[0] + 1)) if w],
                    "at": _word_at(now, ours[a[0]], a[1])})
    return out


def _words(doc, unit, start, end):
    """The tokens of characters [start, end) of a unit's text (notes._spans), or None: none there (a space)."""
    uid, u = unit
    inside = [i for i, (a, b) in enumerate(notes._spans(u["toks"], doc["atoms"])[1]) if b > start and a < end]
    return {"unit": uid, "tokens": [inside[0], inside[-1]]} if inside else None


def _word_at(doc, unit, at):
    """The token of a unit at (or after) a character of its text; at its end, its last token."""
    uid, u = unit
    ends = [b for _, b in notes._spans(u["toks"], doc["atoms"])[1]]
    i = next((i for i, b in enumerate(ends) if b > at), None)
    return {"unit": uid, "token": i, "after": False} if i is not None else {"unit": uid, "token": len(ends) - 1, "after": True}


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
