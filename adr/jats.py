"""JATS XML, the format of PubMed Central, Europe PMC, bioRxiv and medRxiv, PLOS and eLife, as semantic HTML for
semantic.normalize.

The article's own structure carries over: sections with their titles, figures and tables with labels and captions,
formulas as the MathML the publisher wrote (its TeX, where given, as the formula's alttext), citations and
cross-references as links to their targets, footnotes, the reference list. The front matter gives the title,
authors, DOI, date and license.
"""
import re
from html import escape

from bs4 import BeautifulSoup, NavigableString, ProcessingInstruction, Tag

INLINE = {"italic": "em", "bold": "strong", "sub": "sub", "sup": "sup", "underline": "u", "monospace": "code",
          "sc": "span", "roman": "span", "sans-serif": "span", "named-content": "span", "styled-content": "span",
          "abbrev": "span", "strike": "del", "overline": "span", "email": "span", "uri": "span"}
CC = re.compile(r"https?://creativecommons\.org/(?:licenses|publicdomain)/[a-z-]+/\d(?:\.\d)?/?")
SKIP = {"object-id", "alt-text", "long-desc", "permissions", "attrib", "supplementary-material", "media", "counts",
        "custom-meta-group", "kwd-group", "funding-group", "related-article", "inline-graphic", "x"}


def _local(tag):
    return (tag.name or "").split(":")[-1]


def _text(el):
    return re.sub(r"\s+", " ", el.get_text(" ") if el is not None else "").strip()


def meta_of(soup):
    am = soup.find(lambda t: _local(t) == "article-meta")
    if am is None:
        return {"title": "", "authors": [], "doi": "", "date": "", "license": ""}
    title = _text(am.find(lambda t: _local(t) == "article-title"))
    authors = []
    for c in am.find_all(lambda t: _local(t) == "contrib"):
        if c.get("contrib-type", "author") != "author":
            continue
        sn, gn = c.find(lambda t: _local(t) == "surname"), c.find(lambda t: _local(t) == "given-names")
        coll = c.find(lambda t: _local(t) == "collab")
        if sn is not None:
            authors.append(f"{_text(sn)}, {_text(gn)}" if gn is not None else _text(sn))
        elif coll is not None:
            authors.append(_text(coll))
    doi = next((_text(a) for a in am.find_all(lambda t: _local(t) == "article-id") if a.get("pub-id-type") == "doi"), "")
    date = ""
    for pd in am.find_all(lambda t: _local(t) == "pub-date"):
        y = pd.find(lambda t: _local(t) == "year")
        if y is not None:
            m, d = pd.find(lambda t: _local(t) == "month"), pd.find(lambda t: _local(t) == "day")
            date = "-".join(x for x in (_text(y), _text(m).zfill(2) if m is not None else "", _text(d).zfill(2) if d is not None else "") if x)
            break
    lic = ""
    for el in am.find_all(lambda t: _local(t) in ("license_ref", "license", "ext-link")):
        found = [v for k, v in el.attrs.items() if k.split(":")[-1] == "href"] + [el.get_text(" ")]
        m = next((CC.search(x) for x in found if CC.search(x)), None)
        if m:
            lic = m.group(0)
            break
    return {"title": title, "authors": authors, "doi": doi, "date": date, "license": lic.strip()}


def to_html(xml):
    """(semantic HTML, meta) for a JATS article."""
    soup = BeautifulSoup(xml, "lxml-xml")
    meta = meta_of(soup)
    out = []
    am = soup.find(lambda t: _local(t) == "article-meta")
    abstract = None
    if am is not None:
        abstracts = am.find_all(lambda t: _local(t) == "abstract")
        abstract = next((a for a in abstracts if not a.get("abstract-type")), abstracts[0] if abstracts else None)
    if abstract is not None:
        out.append("<h2>Abstract</h2>")
        for ch in abstract.find_all(recursive=False):
            if _local(ch) == "sec":   # a structured abstract (Background, Methods, ...): its parts as paragraphs
                head = _text(ch.find(lambda t: _local(t) == "title", recursive=False))
                for p in ch.find_all(lambda t: _local(t) == "p", recursive=False):
                    out.append(f"<p>{f'<strong>{escape(head)}.</strong> ' if head else ''}{_inline(p)}</p>")
                    head = ""
            elif _local(ch) == "p":
                out.append(f"<p>{_inline(ch)}</p>")
    body = soup.find(lambda t: _local(t) == "body")
    notes = []
    # figures and tables an archive keeps apart (<floats-group>) go after the paragraph that first cites them
    fg = soup.find(lambda t: _local(t) == "floats-group")
    floats = {f["id"]: f for f in (fg.find_all(recursive=False) if fg is not None else [])
              if f.get("id") and _local(f) in ("fig", "table-wrap", "fig-group")}
    ctx = {"floats": floats, "placed": set()}
    if body is not None:
        out.extend(_blocks(body, 2, notes, ctx))
    out.extend(_float(f) for fid, f in floats.items() if fid not in ctx["placed"])
    back = soup.find(lambda t: _local(t) == "back")
    if back is not None:
        for ch in back.find_all(recursive=False):
            name = _local(ch)
            if name in ("ack", "app-group", "app", "sec", "glossary"):
                apps = ch.find_all(lambda t: _local(t) == "app", recursive=False) if name == "app-group" else [ch]
                for a in apps:
                    title = _text(a.find(lambda t: _local(t) == "title", recursive=False)) or ("Acknowledgments" if name == "ack" else "")
                    label = _text(a.find(lambda t: _local(t) == "label", recursive=False))
                    out.append(f"<h2{_id(a)}>{escape(' '.join(x for x in (label, title) if x))}</h2>")
                    out.extend(_blocks(a, 3, notes, ctx))
            elif name == "fn-group":
                notes.extend(ch.find_all(lambda t: _local(t) == "fn"))
            elif name == "ref-list":
                out.append(_refs(ch))
    for fn in soup.find_all(lambda t: _local(t) == "fn" and t.get("id")):
        if fn not in notes and fn.find_parent(lambda t: _local(t) == "table-wrap-foot") is None:
            notes.append(fn)
    if notes:
        items = "".join(f'<li id="{escape(fn.get("id", ""))}">{"".join(f"<p>{_inline(p)}</p>" for p in fn.find_all(lambda t: _local(t) == "p"))}</li>'
                        for fn in notes if fn.get("id"))
        out.append(f'<section class="footnotes"><ol>{items}</ol></section>')
    return "\n".join(out), meta


def _id(el):
    return f' id="{escape(el["id"])}"' if el.get("id") else ""


def _float(f):
    return _table(f) if _local(f) == "table-wrap" else "".join(_figure(x) for x in f.find_all(lambda t: _local(t) == "fig")) \
        if _local(f) == "fig-group" else _figure(f)


def _blocks(el, depth, notes, ctx):
    out = []
    for ch in el.find_all(recursive=False):
        name = _local(ch)
        if name in ("title", "label"):   # a section's own: its heading, written by the caller
            continue
        if name == "sec":   # its title keeps its markup (a subscript in "m<sub>X</sub>dC")
            title = _inline(ch.find(lambda t: _local(t) == "title", recursive=False)).strip()
            label = escape(_text(ch.find(lambda t: _local(t) == "label", recursive=False)))
            if title or label:
                out.append(f"<h{min(depth, 6)}{_id(ch)}>{' '.join(x for x in (label, title) if x)}</h{min(depth, 6)}>")
            out.extend(_blocks(ch, depth + 1, notes, ctx))
        elif name == "p":
            out.extend(_para(ch))
            for x in ch.find_all(lambda t: _local(t) == "xref"):
                for rid in (x.get("rid") or "").split():
                    if rid in ctx["floats"] and rid not in ctx["placed"]:
                        ctx["placed"].add(rid)
                        out.append(_float(ctx["floats"][rid]))
        elif name in ("list", "def-list"):
            out.append(_list(ch))
        elif name == "fig":
            out.append(_figure(ch))
        elif name == "fig-group":
            out.extend(_figure(f) for f in ch.find_all(lambda t: _local(t) == "fig"))
        elif name == "table-wrap":
            out.append(_table(ch))
        elif name == "disp-formula":
            out.append(_formula(ch, True))
        elif name in ("boxed-text", "statement", "disp-quote", "sec-meta", "notes"):
            out.extend(_blocks(ch, depth, notes, ctx))
        elif name == "fn-group":
            notes.extend(ch.find_all(lambda t: _local(t) == "fn"))
        elif name == "ref-list":   # inside a section of its own ("References"): the list under that heading
            out.append(_refs(ch, heading=False))
        elif name in ("preformat", "code"):
            out.append(f"<pre><code>{escape(ch.get_text(''))}</code></pre>")
        elif name not in SKIP and _text(ch):
            out.append(f"<p>{_inline(ch)}</p>")
    return out


def _para(p):
    """A paragraph; the blocks JATS lets a paragraph hold (a formula, a list, a figure) come out after their text."""
    out, cur = [], []
    for ch in p.children:
        name = _local(ch) if isinstance(ch, Tag) else ""
        if name in ("disp-formula", "list", "fig", "table-wrap", "def-list"):
            if "".join(cur).strip():
                out.append(f"<p>{''.join(cur)}</p>")
            cur = []
            out.append(_formula(ch, True) if name == "disp-formula" else _list(ch) if name in ("list", "def-list")
                       else _figure(ch) if name == "fig" else _table(ch))
        else:
            cur.append(_node(ch))
    if "".join(cur).strip():
        out.append(f"<p>{''.join(cur)}</p>")
    return out


def _list(el):
    if _local(el) == "def-list":
        rows = []
        for it in el.find_all(lambda t: _local(t) == "def-item", recursive=False):
            term, d = it.find(lambda t: _local(t) == "term"), it.find(lambda t: _local(t) == "def")
            rows.append(f"<dt>{_inline(term) if term is not None else ''}</dt><dd>{_inline(d) if d is not None else ''}</dd>")
        return f"<dl>{''.join(rows)}</dl>"
    tag = "ol" if el.get("list-type") in ("order", "alpha-lower", "alpha-upper", "roman-lower", "roman-upper") else "ul"
    items = []
    for it in el.find_all(lambda t: _local(t) == "list-item", recursive=False):
        parts = []
        for ch in it.find_all(recursive=False):
            if _local(ch) == "p":
                parts.append(f"<p>{_inline(ch)}</p>")
            elif _local(ch) in ("list", "def-list"):
                parts.append(_list(ch))
        items.append(f"<li>{''.join(parts)}</li>")
    return f"<{tag}>{''.join(items)}</{tag}>"


def _caption(el):
    label = _text(el.find(lambda t: _local(t) == "label", recursive=False))
    cap = el.find(lambda t: _local(t) == "caption", recursive=False)
    parts = []
    if cap is not None:
        title = cap.find(lambda t: _local(t) == "title", recursive=False)
        if title is not None:
            t = _inline(title).strip()
            parts.append(t if re.search(r"[.!?]$", _text(title)) else t + ".")
        parts += [_inline(p) for p in cap.find_all(lambda t: _local(t) == "p", recursive=False)]
    text = " ".join(x for x in parts if x)
    if label and text:
        return f"<figcaption>{escape(label)}: {text}</figcaption>"
    return f"<figcaption>{escape(label)}{text}</figcaption>" if (label or text) else ""


CDN = "https://cdn.ncbi.nlm.nih.gov/pmc/"


def _hwp(el):
    return next((v for k, v in el.attrs.items() if k == "hwp:id"), "")


def _graphic(el, inline=False):
    """An image by its file name; where PubMed Central keeps it (its XML names the blob in a processing instruction,
    <?cloudpmc-path blobs/...?> or <?image-cloudpmc-urn urn:cdn:blobs/...?>); or, in bioRxiv's and medRxiv's XML, by
    the HighWire id their site serves it under: a figure's or table's "F1.large.jpg", any other "embed/graphic-6.gif"
    (biorxiv.py finds those)."""
    g = el.find(lambda t: _local(t) in ("graphic", "inline-graphic"))
    if g is None:
        return ""
    href = next((v for k, v in g.attrs.items() if k.split(":")[-1] == "href"), "")
    if _hwp(el) and _local(el) in ("fig", "table-wrap"):
        href = f"{_hwp(el)}.large.jpg"
    elif _hwp(g):
        href = f"embed/{_hwp(g)}.gif"
    for pi in g.children:
        if isinstance(pi, ProcessingInstruction):
            m = re.match(r"\s*(?:cloudpmc-path\s+|image-cloudpmc-urn\s+urn:cdn:)(blobs/\S+)", str(pi))
            if m:
                href = CDN + m.group(1)
                break
    if not href:
        return ""
    # an image in a line of text (a formula drawn as a picture) stays in the line: parse.py reads it as an atom
    cls = ' class="pf-inline"' if inline else ""
    return f'<img src="{escape(href)}" alt=""{cls}>'


def _figure(fig):
    return f"<figure{_id(fig)}>{_graphic(fig)}{_caption(fig)}</figure>"


def _table(tw):
    table = tw.find(lambda t: _local(t) == "table")
    body = _xhtml(table) if table is not None else _graphic(tw)
    foot = tw.find(lambda t: _local(t) == "table-wrap-foot")
    note = f"<p>{_inline(foot)}</p>" if foot is not None and _text(foot) else ""
    return f"<figure{_id(tw)}>{_caption(tw)}{body}</figure>{note}"


def _xhtml(el):
    """A JATS table is XHTML's: kept, its cells' content read as inline JATS."""
    name = _local(el)
    if name in ("td", "th"):
        span = "".join(f' {k}="{escape(el[k])}"' for k in ("colspan", "rowspan") if el.get(k))
        return f"<{name}{span}>{_inline(el)}</{name}>"
    if name in ("table", "thead", "tbody", "tfoot", "tr"):
        return f"<{name}>{''.join(_xhtml(c) for c in el.find_all(recursive=False))}</{name}>"
    return ""


def _formula(el, display):
    """The MathML the publisher wrote, its TeX (when given) as alttext; else the TeX; else the formula's image."""
    math = el.find(lambda t: _local(t) == "math")
    tex = el.find(lambda t: _local(t) == "tex-math")
    tex_src = re.sub(r"^\\documentclass.*?\\begin\{document\}|\\end\{document\}$", "", tex.get_text(""), flags=re.S).strip() if tex is not None else ""
    tex_src = tex_src.strip("$").strip()
    if math is not None:
        m = _mathml(math)
        if tex_src:
            m = m.replace("<math", f'<math alttext="{escape(tex_src)}"', 1)
        if display:
            m = m.replace("<math", '<math display="block"', 1) if 'display="block"' not in m else m
        if not display:
            return m
        label = _text(el.find(lambda t: _local(t) == "label", recursive=False))
        no = f'<td class="ltx_eqn_cell ltx_eqn_eqno">{escape(label)}</td>' if label else ""
        return (f'<table class="ltx_equation ltx_eqn_table"{_id(el)}><tr class="ltx_equation ltx_eqn_row">'
                f'<td class="ltx_eqn_cell ltx_eqn_center_padleft"></td><td class="ltx_eqn_cell ltx_align_center">{m}</td>'
                f'<td class="ltx_eqn_cell ltx_eqn_center_padright"></td>{no}</tr></table>')
    if tex_src:
        cls = "math display" if display else "math inline"
        return f'<span class="{cls}">{escape(tex_src)}</span>'
    img = _graphic(el, inline=not display)   # a formula only as a picture (bioRxiv, medRxiv)
    if not display or not img:
        return img
    return (f'<table class="ltx_equation ltx_eqn_table"{_id(el)}><tr class="ltx_equation ltx_eqn_row">'
            f'<td class="ltx_eqn_cell ltx_eqn_center_padleft"></td><td class="ltx_eqn_cell ltx_align_center">{img}</td>'
            f'<td class="ltx_eqn_cell ltx_eqn_center_padright"></td></tr></table>')


def _mathml(math):
    """MathML with its namespace prefix dropped (mml:mi -> mi), as an HTML page holds it."""
    def walk(n):
        if isinstance(n, NavigableString):
            return escape(str(n)) if n.strip() or not isinstance(n.parent, Tag) else escape(str(n))
        if not isinstance(n, Tag):
            return ""
        name = _local(n)
        attrs = "".join(f' {k.split(":")[-1]}="{escape(v if isinstance(v, str) else " ".join(v))}"' for k, v in n.attrs.items()
                        if ":" not in k and k not in ("id", "overflow"))
        return f"<{name}{attrs}>{''.join(walk(c) for c in n.children)}</{name}>"
    return walk(math)


def _node(n):
    if isinstance(n, NavigableString):
        return escape(str(n))
    if not isinstance(n, Tag):
        return ""
    name = _local(n)
    if name in SKIP:
        return ""
    if name == "inline-formula":
        return _formula(n, False)
    if name == "disp-formula":
        return _formula(n, True)
    if name == "xref":
        rid, kind = (n.get("rid") or "").split()[0] if n.get("rid") else "", n.get("ref-type", "")
        inner = _inline(n) or escape(rid)
        if kind == "bibr":
            return f'<cite class="ltx_cite"><a href="#{escape(rid)}">{inner}</a></cite>'
        if kind == "fn":
            return f'<sup><a href="#{escape(rid)}">{inner}</a></sup>'
        return f'<a href="#{escape(rid)}">{inner}</a>' if rid else inner
    if name in ("ext-link", "uri"):
        href = next((v for k, v in n.attrs.items() if k.split(":")[-1] == "href"), "") or n.get_text("")
        return f'<a href="{escape(href)}">{_inline(n)}</a>'
    if name == "break":
        return "<br>"
    if name == "sup" and _cites_only(n):   # superscript citations (¹ or ²⁻⁴): a citation, drawn raised
        links = "".join(f'<a href="#{escape(c["rid"].split()[0])}">{_inline(c)}</a>' if isinstance(c, Tag) else escape(str(c))
                        for c in n.children)
        return f'<cite class="ltx_cite"><sup>{links}</sup></cite>'
    if name == "name":   # <surname>Montell</surname><given-names>DJ</given-names>: "Montell DJ"
        return escape(" ".join(_text(n.find(lambda t: _local(t) == k)) for k in ("surname", "given-names")
                               if n.find(lambda t: _local(t) == k) is not None))
    if name == "person-group":
        names = [c for c in n.children if isinstance(c, Tag) and _local(c) in ("name", "collab")]
        if names and all(isinstance(c, Tag) or not str(c).strip() for c in n.children):
            return ", ".join(_node(c) for c in names) + ". "
    tag = INLINE.get(name)
    return f"<{tag}>{_inline(n)}</{tag}>" if tag else _inline(n)


def _cites_only(sup):
    """A superscript that holds citations and nothing else but the commas and dashes between them."""
    tags = [c for c in sup.children if isinstance(c, Tag)]
    rest = "".join(str(c) for c in sup.children if not isinstance(c, Tag))
    return bool(tags) and all(_local(c) == "xref" and c.get("ref-type") == "bibr" and c.get("rid") for c in tags) \
        and not re.sub(r"[\s,;–—-]", "", rest)


def _inline(el):
    return "".join(_node(c) for c in el.children) if el is not None else ""


def _refs(rl, heading=True):
    items = []
    for ref in rl.find_all(lambda t: _local(t) == "ref"):
        cit = ref.find(lambda t: _local(t) in ("mixed-citation", "element-citation", "citation"))
        label = _text(ref.find(lambda t: _local(t) == "label", recursive=False))
        text = _cite_text(cit) if cit is not None else escape(_text(ref))
        items.append(f'<li{_id(ref)}>{escape(label) + " " if label and not text.startswith(label) else ""}{text}</li>')
    title = _text(rl.find(lambda t: _local(t) == "title", recursive=False)) or "References"
    return (f"<h2>{escape(title)}</h2>" if heading else "") + f"<ul>{''.join(items)}</ul>"


def _cite_text(cit):
    """A reference as it reads; an element-citation (fields, no punctuation) is joined with the usual separators."""
    if _local(cit) == "mixed-citation":
        return _inline(cit)
    names = [", ".join(x for x in (_text(n.find(lambda t: _local(t) == "surname")), _text(n.find(lambda t: _local(t) == "given-names"))) if x)
             for n in cit.find_all(lambda t: _local(t) == "name")]
    get = lambda k: _text(cit.find(lambda t: _local(t) == k))   # noqa: E731
    parts = ["; ".join(names), f"({get('year')})" if get("year") else "", get("article-title") or get("chapter-title"),
             f"<em>{escape(get('source'))}</em>" if get("source") else "", get("volume"), get("fpage")]
    return escape(". ".join(p for p in parts[:1] if p)) + " " + " ".join(p if p.startswith("<em>") else escape(p) for p in parts[1:] if p)
