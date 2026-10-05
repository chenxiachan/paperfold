"""Any semantic HTML as the document parse.py reads.

Sources other than arXiv's LaTeXML page (Markdown now; JATS XML, Word and EPUB later) are first written as plain
semantic HTML: headings, paragraphs, lists, tables, figures, math, footnotes. normalize() rewrites that HTML in the
shape LaTeXML gives arXiv's pages (sections with titles, ltx_p paragraphs, figures with captions, equation tables,
footnotes inside the text), so every source is cut into units by one parser and drawn by one reader.

It is also where a document is made safe. The reader runs on the local server's origin, so a script in a file could
drive that server: only the elements and attributes a document needs are kept, and links and images only where they
point somewhere harmless.
"""
import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

DROP = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "textarea", "select", "option",
        "template", "link", "meta", "noscript", "svg", "canvas", "video", "audio", "base", "frame", "frameset", "head",
        "title"}
KEEP = {"a", "b", "blockquote", "br", "caption", "cite", "code", "dd", "del", "div", "dl", "dt", "em", "figcaption",
        "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li", "mark", "ol", "p", "pre",
        "s", "section", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul"}
MATHML = {"math", "semantics", "annotation", "annotation-xml", "mrow", "mi", "mn", "mo", "ms", "mtext", "mspace",
          "mfrac", "msqrt", "mroot", "msub", "msup", "msubsup", "munder", "mover", "munderover", "mmultiscripts",
          "mprescripts", "none", "mtable", "mtr", "mlabeledtr", "mtd", "mstyle", "mpadded", "mphantom", "menclose",
          "merror", "mfenced"}
ATTRS = {"id", "class", "title", "lang", "dir", "href", "src", "alt", "colspan", "rowspan", "start", "value"}
INLINE_SPAN = {"mark", "u", "small", "abbr", "q", "ins"}   # read as text; their look is not worth an atom
BLOCK = {"p", "ul", "ol", "dl", "table", "figure", "pre", "blockquote", "hr", "div", "section",
         "h1", "h2", "h3", "h4", "h5", "h6"}

SECTION_CLASS = ["ltx_section", "ltx_subsection", "ltx_subsubsection", "ltx_paragraph"]
HEAD_NUM = re.compile(r"^\s*((?:\d+\.)*\d+\.?|[A-Z]\.(?:\d+\.?)*|[IVX]+\.)\s+(?=\S)")
CAPTION = re.compile(r"^\s*((?:(?:Extended Data|Supplementary|Supplemental|Appendix)\s+)?"
                     r"(?:Figure|Fig\.?|Table|Tab\.?|Abbildung|Abb\.|Tabelle|Figura|Tabla|Tableau|图|圖|表)"
                     r"\s*S?[A-Z]?\d+(?:\.\d+)*[a-z]?)\s*[:.：]\s*", re.I)
TABLE_NOTE = re.compile(r"^\s*(?:Table|Tabelle|表)\s*[:：]\s*", re.I)   # Pandoc's caption line: "Table: ..."
ABSTRACT = re.compile(r"^(abstract|summary|tl;?dr|摘要|概要|zusammenfassung|résumé|resumen|riassunto|аннотация)$", re.I)
REFERENCES = re.compile(r"^(references|bibliography|works cited|literature( cited)?|sources|参考文献|參考文獻|"
                        r"literatur(verzeichnis)?|références|referencias|bibliografia|riferimenti( bibliografici)?|"
                        r"список литературы|литература)$", re.I)


def normalize(html, resolve_img=None):
    """Semantic HTML -> the HTML parse.parse reads. resolve_img(src) gives where the page finds an image (img/...) or
    None when it cannot be had; without it, images are left out."""
    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    _sanitize(root)
    _math(soup, root)
    _footnotes(soup, root)
    _images(soup, root, resolve_img)
    _tables(soup, root)
    for el in root.find_all(["blockquote", "div", "section", "article", "main", "header", "footer", "aside"]):
        if not _ours(el):
            el.unwrap()   # a quotation's paragraphs are read like any other; containers carry nothing of their own
    for el in root.find_all("hr"):
        el.decompose()
    for el in root.find_all(INLINE_SPAN):
        el.name = "span"
    _lists(soup, root)
    blocks = _flow(soup, root)
    art = soup.new_tag("article", attrs={"class": "ltx_document"})
    _sections(soup, art, blocks)
    for el in art.find_all(True):
        _keep_classes(el)
    return str(art)


def _ours(el):
    return any(c.startswith("ltx_") for c in el.get("class", []))


def _sanitize(root):
    for el in list(root.find_all(True)):
        if getattr(el, "decomposed", False):
            continue
        name = (el.name or "").lower()
        if name in DROP:
            el.decompose()
            continue
        if name in MATHML:
            for k in list(el.attrs):
                if k.lower().startswith("on") or k.lower() in ("href", "src", "style") or ":" in k and k != "xmlns":
                    del el.attrs[k]
            continue
        if name not in KEEP:
            el.unwrap()
            continue
        align = re.search(r"text-align:\s*(left|right|center)", el.get("style", "")) if name in ("td", "th") else None
        for k in list(el.attrs):
            if k.lower() not in ATTRS:
                del el.attrs[k]
        if align:   # a Markdown table's column alignment, as LaTeXML's class
            el["class"] = [f"ltx_align_{align.group(1)}"]
        if name == "a" and not re.match(r"^(#|https?://|mailto:)", el.get("href", ""), re.I):
            el.attrs.pop("href", None)
        if name == "img" and re.match(r"^(javascript|vbscript|data:(?!image/(png|jpe?g|gif|webp)))", el.get("src", ""), re.I):
            el.attrs.pop("src", None)


def _keep_classes(el):
    cls = [c for c in el.get("class", []) if c.startswith(("ltx_", "pf-"))]
    if cls:
        el["class"] = cls
    else:
        el.attrs.pop("class", None)


# ── math ──────────────────────────────────────────────────────────────
def tex_math(latex, display=False):
    """LaTeX as MathML that carries its source (alttext), as LaTeXML writes formulas: the browser draws it with no
    script, and the model reads the LaTeX. A formula the converter cannot read stays as its source."""
    latex = latex.strip()
    try:
        from latex2mathml.converter import convert
        m = BeautifulSoup(convert(latex, display="block" if display else "inline"), "lxml").find("math")
    except Exception:
        m = None
    if m is None:
        span = BeautifulSoup("<code></code>", "lxml").find("code")
        span.string = f"${latex}$"
        return span
    m["alttext"] = latex
    return m


def _strip_delims(s):
    s = s.strip()
    for a, b in (("$$", "$$"), ("\\[", "\\]"), ("\\(", "\\)"), ("$", "$")):
        if s.startswith(a) and s.endswith(b) and len(s) > len(a) + len(b) - 1:
            return s[len(a):len(s) - len(b)]
    return s


def _equation(soup, math):
    t = soup.new_tag("table", attrs={"class": "ltx_equation ltx_eqn_table"})
    tr = soup.new_tag("tr", attrs={"class": "ltx_equation ltx_eqn_row"})
    for cls in ("ltx_eqn_cell ltx_eqn_center_padleft", "ltx_eqn_cell ltx_align_center", "ltx_eqn_cell ltx_eqn_center_padright"):
        tr.append(soup.new_tag("td", attrs={"class": cls}))
    tr.find_all("td")[1].append(math)
    tbody = soup.new_tag("tbody")
    tbody.append(tr)
    t.append(tbody)
    return t


def _math(soup, root):
    """markdown-it's and Pandoc's math (span.math.inline, div.math.block, span.math.display) becomes MathML; MathML
    that came as such keeps its LaTeX annotation as its alttext."""
    for el in root.find_all(["span", "div"], class_="math"):
        cls = el.get("class", [])
        display = el.name == "div" or "display" in cls or "block" in cls
        m = tex_math(_strip_delims(el.get_text("")), display)
        el.replace_with(_equation(soup, m) if display and m.name == "math" else m)
    for m in root.find_all("math"):
        if not m.get("alttext"):
            ann = m.find("annotation", attrs={"encoding": "application/x-tex"})
            if ann:
                m["alttext"] = ann.get_text("").strip()
        if m.get("display") == "block" and not m.find_parent("table", class_="ltx_equation"):
            ph = soup.new_tag("span")
            m.replace_with(ph)
            ph.replace_with(_equation(soup, m))


# ── footnotes ─────────────────────────────────────────────────────────
def _footnotes(soup, root):
    """A footnote list at the end (markdown-it, Pandoc) moves into the text, where its mark is: LaTeXML's shape, which
    the reader shows on hover."""
    notes = {}
    for box in root.find_all(["section", "div", "ol"], class_=re.compile(r"^footnotes")):
        for li in box.find_all("li", id=True):
            for back in li.find_all("a", class_=re.compile("footnote-back|footnote-backref")):
                back.decompose()
            for back in li.find_all("a", href=re.compile(r"^#fnref")):
                back.decompose()
            notes[li["id"]] = li
    if not notes:
        return
    n = 0
    for a in root.find_all("a", href=True):
        fid = a["href"][1:] if a["href"].startswith("#") else None
        if fid not in notes:
            continue
        n += 1
        mark = re.sub(r"[\[\]\s]", "", a.get_text("")) or str(n)
        note = soup.new_tag("span", attrs={"class": "ltx_note ltx_role_footnote"})
        sup = soup.new_tag("sup", attrs={"class": "ltx_note_mark"})
        sup.string = mark
        outer = soup.new_tag("span", attrs={"class": "ltx_note_outer"})
        content = soup.new_tag("span", attrs={"class": "ltx_note_content"})
        sup2 = soup.new_tag("sup", attrs={"class": "ltx_note_mark"})
        sup2.string = mark
        content.append(sup2)
        for p in list(notes[fid].children):
            if isinstance(p, Tag) and p.name == "p":
                for x in list(p.contents):
                    content.append(x.extract())
                content.append(" ")
            elif isinstance(p, (Tag, NavigableString)) and str(p).strip():
                content.append(p.extract() if isinstance(p, Tag) else str(p))
        outer.append(content)
        note.append(sup)
        note.append(outer)
        host = a.parent if a.parent and a.parent.name == "sup" and len(a.parent.find_all(True)) == 1 else a
        host.replace_with(note)
    for box in root.find_all(["section", "div", "ol"], class_=re.compile(r"^footnotes")):
        box.decompose()
    for hr in root.find_all("hr", class_="footnotes-sep"):
        hr.decompose()


# ── figures and tables ────────────────────────────────────────────────
def _caption(soup, text_el, label_re=CAPTION):
    """A figcaption from a paragraph (or caption): its "Figure 3:" label, when it has one, as LaTeXML's tag."""
    cap = soup.new_tag("figcaption", attrs={"class": "ltx_caption"})
    for x in list(text_el.contents):
        cap.append(x.extract())
    first = next((x for x in cap.contents if isinstance(x, NavigableString) and x.strip()), None)
    if first is not None:
        m = label_re.match(str(first))
        if m:
            tag = soup.new_tag("span", attrs={"class": "ltx_tag ltx_tag_figure"})
            tag.string = m.group(1) + ": "
            first.replace_with(str(first)[m.end():])
            cap.insert(0, tag)
    return cap


def _sibling(el, step):
    s = el.next_sibling if step > 0 else el.previous_sibling
    while s is not None and isinstance(s, NavigableString) and not s.strip():
        s = s.next_sibling if step > 0 else s.previous_sibling
    return s if isinstance(s, Tag) else None


def _lone_img(p):
    kids = [c for c in p.contents if not (isinstance(c, NavigableString) and not c.strip()) and getattr(c, "name", None) != "br"]
    return kids[0] if len(kids) == 1 and getattr(kids[0], "name", None) == "img" else None


def _images(soup, root, resolve_img):
    for p in root.find_all("p"):
        img = _lone_img(p)
        if img is None:
            continue
        fig = soup.new_tag("figure", attrs={"class": "ltx_figure"})
        fig.append(img.extract())
        nxt = _sibling(p, 1)
        if nxt is not None and nxt.name == "p" and CAPTION.match(nxt.get_text("")) and not CAPTION.match(nxt.get_text("")).group(1).lower().startswith(("tab", "表")):
            fig.append(_caption(soup, nxt))
            nxt.decompose()
        elif (img.get("alt") or "").strip() and not re.search(r"\.(png|jpe?g|gif|webp|svg)$", img["alt"], re.I):
            cap = soup.new_tag("p")
            cap.string = img["alt"].strip()
            fig.append(_caption(soup, cap))
        p.replace_with(fig)
    for img in root.find_all("img"):
        where = resolve_img(img.get("src", "")) if resolve_img and img.get("src") else None
        if where:
            img["src"] = where
        else:   # an image the document names but that could not be had: its name stays, as a placeholder
            ph = soup.new_tag("span", attrs={"class": "pf-missing"})
            ph.string = "🖼 " + (img.get("src", "").split("/")[-1] or img.get("alt") or "image")
            img.replace_with(ph)
    for fig in root.find_all("figure"):
        if fig.find("table") and not fig.find("img"):
            continue   # a table's figure: _tables
        fig["class"] = ["ltx_figure"]
        cap = fig.find("figcaption")
        if cap is not None and "ltx_caption" not in cap.get("class", []):
            p = soup.new_tag("p")
            for x in list(cap.contents):
                p.append(x.extract())
            cap.replace_with(_caption(soup, p))


def _tables(soup, root):
    for t in root.find_all("table"):
        if _ours(t):
            continue   # an equation's table
        t["class"] = ["ltx_tabular", "ltx_centering"]
        rows = t.find_all("tr")
        for n, tr in enumerate(rows):
            head = tr.find_parent("thead") is not None or all(c.name == "th" for c in tr.find_all(["td", "th"]))
            for c in tr.find_all(["td", "th"]):
                cls = ["ltx_td"] + (["ltx_th", "ltx_border_b"] if head else []) + (["ltx_border_tt"] if n == 0 else []) + \
                      (["ltx_border_bb"] if n == len(rows) - 1 else [])
                c["class"] = cls + [x for x in c.get("class", []) if x.startswith("ltx_align_")]
        fig = t.find_parent("figure")
        if fig is None:
            fig = soup.new_tag("figure")
            t.replace_with(fig)
            fig.append(t)
        fig["class"] = ["ltx_table"]
        cap = fig.find("figcaption") or t.find("caption")
        src = None
        if cap is None:
            before, after = _sibling(fig, -1), _sibling(fig, 1)
            if before is not None and before.name == "p" and CAPTION.match(before.get_text("")):
                src = before
            elif after is not None and after.name == "p" and (CAPTION.match(after.get_text("")) or TABLE_NOTE.match(after.get_text(""))):
                src = after
        else:
            src = cap
        if src is not None:
            p = soup.new_tag("p")
            for x in list(src.contents):
                p.append(x.extract())
            first = next((x for x in p.contents if isinstance(x, NavigableString) and x.strip()), None)
            if first is not None and TABLE_NOTE.match(str(first)):
                first.replace_with(TABLE_NOTE.sub("", str(first), count=1))
            src.decompose()
            fig.insert(0, _caption(soup, p))


# ── lists ─────────────────────────────────────────────────────────────
def _wrap_inline(soup, el):
    """Text written straight into a list item (a tight list) becomes a paragraph, as LaTeXML writes every item."""
    run = []

    def flush():
        if any(not (isinstance(x, NavigableString) and not x.strip()) for x in run):
            p = soup.new_tag("p")
            run[0].insert_before(p)
            for x in run:
                p.append(x.extract())
        run.clear()

    for ch in list(el.contents):
        if isinstance(ch, Tag) and ch.name in BLOCK:
            flush()
        else:
            run.append(ch)
    flush()


def _lists(soup, root):
    for lst in root.find_all(["ul", "ol"]):
        n = int(lst.get("start", 1)) if str(lst.get("start", "1")).isdigit() else 1
        for li in lst.find_all("li", recursive=False):
            _wrap_inline(soup, li)
            if lst.name == "ol":
                n = int(li["value"]) if str(li.get("value", "")).isdigit() else n
                tag = soup.new_tag("span", attrs={"class": "ltx_tag ltx_tag_item"})
                tag.string = f"{n}."
                li.insert(0, tag)
                n += 1
    for dd in root.find_all("dd"):
        _wrap_inline(soup, dd)


# ── the flow and its sections ─────────────────────────────────────────
def _flow(soup, root):
    """The document as a flat run of blocks: loose inline text becomes paragraphs, a paragraph holding a block (a
    display formula Pandoc wrote inside it) is split around it."""
    out, run = [], []

    def flush():
        if any(not (isinstance(x, NavigableString) and not x.strip()) for x in run):
            p = soup.new_tag("p")
            for x in run:
                p.append(x.extract() if isinstance(x, Tag) else NavigableString(str(x)))
            out.append(p)
        run.clear()

    for ch in list(root.contents):
        if isinstance(ch, Tag) and (ch.name in BLOCK or _ours(ch)):
            flush()
            out.extend(_split_p(soup, ch) if ch.name == "p" else [ch.extract()])
        elif isinstance(ch, (Tag, NavigableString)):
            run.append(ch)
    flush()
    return out


def _split_p(soup, p):
    p = p.extract()
    if not p.find(lambda t: t.name in ("table", "figure", "ul", "ol", "pre", "div")):
        return [p]
    parts, cur = [], soup.new_tag("p")
    for ch in list(p.contents):
        if isinstance(ch, Tag) and ch.name in ("table", "figure", "ul", "ol", "pre", "div"):
            if cur.get_text("").strip() or cur.find(True):
                parts.append(cur)
            parts.append(ch.extract())
            cur = soup.new_tag("p")
        else:
            cur.append(ch.extract() if isinstance(ch, Tag) else NavigableString(str(ch)))
    if cur.get_text("").strip() or cur.find(True):
        parts.append(cur)
    return parts


def slug(text):
    s = re.sub(r"[^\w\- ]", "", text.lower(), flags=re.U).strip()
    return re.sub(r"\s+", "-", s)


def _sections(soup, art, blocks):
    heads = [b for b in blocks if re.fullmatch(r"h[1-6]", b.name or "")]
    is_head = {id(h) for h in heads}   # by identity: bs4 compares tags by content, and two headings may read alike
    top = min((int(h.name[1]) for h in heads), default=1)
    used, anchors = set(), {}
    lead = bool(blocks) and id(blocks[0]) not in is_head
    explicit_abstract = next((h for h in heads if ABSTRACT.match(h.get_text(" ", strip=True))), None) if not lead else None
    stack = [(1, art)]
    if lead:   # text before the first heading: an untitled first section, the document's "abstract" (it is read
        sec = soup.new_tag("section", attrs={"class": "ltx_section", "id": "abstract"})   # as context for the rest)
        art.append(sec)
        stack.append((2, sec))
        used.add("abstract")
    bib = []
    for b in blocks:
        if id(b) in is_head:
            depth = min(int(b.name[1]) - top, 3)
            rank = 2 + depth
            while stack[-1][0] >= rank:
                stack.pop()
            text = b.get_text(" ", strip=True)
            if REFERENCES.match(text):
                sec = soup.new_tag("section", attrs={"class": "ltx_bibliography"})
                bib.append(sec)
            else:
                sid = "abstract" if b is explicit_abstract else "sec-" + (slug(text) or str(len(used)))
                base, k = sid, 2
                while sid in used:
                    sid, k = f"{base}-{k}", k + 1
                used.add(sid)
                anchors[slug(text)] = sid
                if b.get("id"):   # a source's own id for the section (JATS: <sec id="sec2">), which its links use
                    anchors[b["id"]] = sid
                sec = soup.new_tag("section", attrs={"class": SECTION_CLASS[depth], "id": sid})
            h = soup.new_tag(f"h{rank}", attrs={"class": "ltx_title ltx_title_section"})
            for x in list(b.contents):
                h.append(x.extract() if isinstance(x, Tag) else NavigableString(str(x)))
            first = next((x for x in h.contents if isinstance(x, NavigableString) and x.strip()), None)
            m = HEAD_NUM.match(str(first)) if first is not None and h.contents and first is h.contents[0] else None
            if m:
                tag = soup.new_tag("span", attrs={"class": "ltx_tag ltx_tag_section"})
                tag.string = m.group(1).rstrip(".")
                first.replace_with(str(first)[m.end():])
                h.insert(0, tag)
            sec.append(h)
            stack[-1][1].append(sec)
            stack.append((rank, sec))
        else:
            if b.name == "p":
                b["class"] = ["ltx_p"]
            stack[-1][1].append(b)
    for sec in bib:
        _bibliography(soup, sec)
    for p in art.find_all("p"):
        p["class"] = ["ltx_p"]
    for a in art.find_all("a", href=re.compile(r"^#")):   # [Methods](#methods): the section's own id
        if a["href"][1:] in anchors:
            a["href"] = "#" + anchors[a["href"][1:]]


def _bibliography(soup, sec):
    """A references section is a list of works, not text to fold: LaTeXML's bibliography, shown at Full."""
    items = []
    for ch in [c for c in sec.contents if isinstance(c, Tag) and not re.fullmatch(r"h[1-6]", c.name)]:
        if ch.name in ("ul", "ol"):
            for li in ch.find_all("li", recursive=False):
                tag = li.find(class_="ltx_tag")
                if tag:
                    tag.decompose()
                items.append(li)
        elif ch.get_text("").strip():
            items.append(ch)
        ch.extract()
    ul = soup.new_tag("ul", attrs={"class": "ltx_biblist"})
    for n, it in enumerate(items, 1):   # a work keeps the id its citations point at (JATS: <ref id="B3">)
        li = soup.new_tag("li", attrs={"class": "ltx_bibitem", "id": it.get("id") or f"bib{n}"})
        for x in list(it.contents):
            li.append(x.extract() if isinstance(x, Tag) else NavigableString(str(x)))
        ul.append(li)
    sec.append(ul)
