"""A web page read with a recipe written for its site (docs/web-adapt.md, the skill in skills/web-adapt): which element
holds the article, which parts are furniture, which marks open notes, which controls hold the article's words, and
which elements are figures drawn by scripts. A recipe names elements by CSS selectors and never holds words: the
words are taken from the page by this code, and checked, every one, against the page as its reader sees it.

The same recipe is meant for a page as fetched (no scripts run), as a browser rendered it (the app's, or a browser
extension's, after its scripts), and, later, for the live page in a reader's browser: so its selectors are CSS that
both soupsieve (here) and querySelectorAll (there) read, and what a recipe can do stops at what the reader can see.
A snapshot is the page as its reader saw it, a subscriber's whole, and is read as it is: text it hides, or a
paywall's cut for a reader without access, is never sought elsewhere.

  python3 -m textfold adapt <url> [--snapshot page.html [--rendered]]           what an agent is given: the outline
  python3 -m textfold adapt <url> [--snapshot page.html] --try recipe.json [--keep]   the page read with a recipe
"""
import json
import re
import unicodedata
import urllib.parse

from . import webpage

FORMAT, VERSION = "textfold/web-recipe", 1
LISTS = ("drop", "notes", "content", "figures")
BLOCKISH = {"p", "div", "section", "article", "main", "aside", "nav", "header", "footer", "table", "ul", "ol", "li", "dl",
            "h1", "h2", "h3", "h4", "h5", "h6", "figure", "blockquote", "pre", "form", "details", "d-article", "d-figure"}
BLOCKS = ("p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "figcaption", "blockquote", "dd", "dt", "pre", "caption")
GENERATED = re.compile(r"^(?:css|sc|jsx|emotion|styled|chakra|mui|tw)-[\w-]{4,}$|^_(?=[\w-]*\d)[\w-]{5,}$|^[A-Za-z]+_[\w-]+__[\w-]{5}$"
                       r"|^[A-Z][A-Za-z]+-[A-Za-z0-9]{5,6}$"   # (styled-components: BodyWrapper-cuqCAc)
                       r"|^(?=[\w-]{0,5}[A-Z])(?=[\w-]{0,5}[a-z0-9])[A-Za-z0-9-]{6}_[a-z][\w-]*$")   # (CSS modules: VeVOXq_container)
PAYWALL_CLASS = re.compile(r"paywall|piano|tp-modal|tp-container|metered|subscriber[-_]only|premium[-_]content|regwall|"
                           r"meter[-_]|gate[-_]?keeper|member[-_]only", re.I)
PAYWALL_WORDS = re.compile(r"subscribe to (?:continue|read|keep reading|unlock)|already a (?:subscriber|member)|for paid subscribers|"
                           r"member-only story|to continue reading|sign in to (?:continue|read)|this article is for subscribers|"
                           r"unlock this (?:article|story)|become a (?:paid )?(?:member|subscriber) to", re.I)


# ── the recipe ───────────────────────────────────────────────────────
def recipe_of(data):
    """A recipe checked for its shape: its selectors strings, its notes pairs. Raises ValueError naming what is wrong."""
    r = json.loads(data) if isinstance(data, (str, bytes)) else dict(data)
    if r.get("format", FORMAT) != FORMAT:
        raise ValueError(f"not a {FORMAT}")
    if not isinstance(r.get("article", ""), str):
        raise ValueError("article: one selector")
    for k in LISTS:
        v = r.setdefault(k, [])
        if not isinstance(v, list):
            raise ValueError(f"{k}: a list")
    for k in ("drop", "content", "figures"):
        if not all(isinstance(x, str) and x.strip() for x in r[k]):
            raise ValueError(f"{k}: selectors")
    if not all(isinstance(x, dict) and isinstance(x.get("mark"), str) and isinstance(x.get("note"), str) for x in r["notes"]):
        raise ValueError('notes: [{"mark": selector, "note": selector}]')
    for sel in [r.get("article") or ""] + r["drop"] + r["content"] + r["figures"] + [x[k] for x in r["notes"] for k in ("mark", "note")]:
        if re.search(r"::|:(?:hover|focus|active|visited|checked)\b", sel):
            raise ValueError(f"{sel}: a selector of what the page is, not of how it looks or what the reader does")
    return r


def _tag(page, recipe):
    """The page with the recipe's choices written on its elements (data-tf-*), as an extension would write them on the
    live page: soupsieve reads the selectors. Returns the page and, per selector, how many elements it matched."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page, "lxml")
    seen = {}

    def pick(sel):
        try:
            got = soup.select(sel)
        except Exception as e:   # (soupsieve's SelectorSyntaxError: a selector this code cannot read)
            raise ValueError(f"{sel}: {e}") from None
        seen[sel] = len(got)
        return got
    if recipe.get("article"):
        for el in pick(recipe["article"])[:1]:
            el["data-tf-article"] = "1"
    for sel in recipe["drop"]:
        for el in pick(sel):
            el["data-tf-drop"] = "1"
    for sel in recipe["content"]:
        for el in pick(sel):
            el["data-tf-content"] = "1"
    for sel in recipe["figures"]:
        for el in pick(sel):
            el["data-tf-figure"] = "1"
    k = 0
    for pair in recipe["notes"]:
        marks, notes = pick(pair["mark"]), pick(pair["note"])
        order = {id(el): i for i, el in enumerate(soup.find_all(True))}
        free = sorted(marks, key=lambda el: order.get(id(el), 0))
        for note in sorted(notes, key=lambda el: order.get(id(el), 0)):
            at = order.get(id(note), 0)
            # its mark: the one that names it (aria-describedby, aria-controls, a link to it), else the nearest before it
            nid = note.get("id")
            mark = next((m for m in free if nid and (nid in (m.get("aria-describedby") or "").split()
                                                     or nid in (m.get("aria-controls") or "").split()
                                                     or (m.get("href") or "").endswith("#" + nid))), None)
            mark = mark or next((m for m in reversed(free) if order.get(id(m), 0) < at), None)
            if mark is None:
                continue
            free.remove(mark)
            k += 1
            mark["data-tf-mark"], note["data-tf-note"] = str(k), str(k)
    return str(soup), seen


def seen(page, url):
    """The page as its reader sees it (webpage.visible), its scripts and styles out too: the words on it."""
    from lxml import etree
    root = webpage.visible(page, url)
    etree.strip_elements(root, "script", "style", with_tail=False)
    return root


# ── reading with it ──────────────────────────────────────────────────
def _lazy(root):
    """A picture a script fills in (data-src, srcset, a blank placeholder in src): its own address."""
    for img in root.iter("img"):
        src = img.get("src") or ""
        if src and not src.startswith("data:"):
            continue
        real = img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
        if not real and (img.get("srcset") or img.get("data-srcset")):
            real = (img.get("srcset") or img.get("data-srcset")).split(",")[0].strip().split(" ")[0]
        if real:
            img.set("src", real)


def _figure(el, url):
    """A figure drawn by the page's scripts: its caption, as the page writes it, a link to the figure on the page."""
    from lxml import html as lhtml
    cap = el.find(".//figcaption")
    if cap is None:   # (a caption in a div of its own: Distill's div.figcaption)
        cap = next((c for c in el.iter() if isinstance(c.tag, str) and "caption" in (c.get("class") or "").lower()), None)
    words = (cap.text_content() if cap is not None else "") or el.get("aria-label") or ""
    if not words.strip():
        head = next((h for h in el.iter("h1", "h2", "h3", "h4", "h5", "h6")), None)
        words = head.text_content() if head is not None else ""
    words = re.sub(r"\s+", " ", words).strip() or "↗"   # (a figure with no words of its own: the link alone)
    href = url.split("#")[0] + ("#" + el.get("id") if el.get("id") else "")
    p = lhtml.fragment_fromstring("<p></p>", create_parent=False)
    a = lhtml.Element("a", href=href)
    a.text = words
    p.append(a)
    return p


def _paragraphs(art):
    """Words with no paragraphs of their own, broken by two line breaks (the HTML of the 1990s, forums, many a
    newsletter): each run between the breaks a paragraph."""
    from lxml import html as lhtml
    BR = object()
    for el in reversed(list(art.iter())):   # (the innermost first: a font that holds the essay, before its cell)
        if not isinstance(el.tag, str) or el.tag in ("pre", "code", "table", "tr", "p", "ul", "ol", "dl"):
            continue
        kids = list(el)
        if not any(a.tag == "br" and b.tag == "br" and not (a.tail or "").strip() for a, b in zip(kids, kids[1:])):
            continue
        items = [el.text or ""]   # the words and elements in order, a line break as BR
        for c in kids:
            tail, c.tail = c.tail or "", None
            el.remove(c)
            items += [BR if c.tag == "br" else c, tail]
        el.text = None
        runs, cur, i = [], [], 0
        while i < len(items):
            if isinstance(items[i], lhtml.HtmlElement) and items[i].tag in BLOCKISH:   # (a quotation among the words: a block of its own)
                runs += [cur, items[i]]
                cur, i = [], i + 1
                continue
            if items[i] is BR:
                j, n = i, 0
                while j < len(items) and (items[j] is BR or (isinstance(items[j], str) and not items[j].strip())):
                    n += items[j] is BR
                    j += 1
                if n >= 2:
                    runs.append(cur)
                    cur, i = [], j
                    continue
                cur.append(lhtml.Element("br"))
            else:
                cur.append(items[i])
            i += 1
        runs.append(cur)
        for run in runs:
            if not isinstance(run, list):
                el.append(run)
                continue
            p = lhtml.Element("p")
            for part in run:
                if isinstance(part, str):
                    last = p[-1] if len(p) else None
                    if last is None:
                        p.text = (p.text or "") + part
                    else:
                        last.tail = (last.tail or "") + part
                else:
                    p.append(part)
            if p.text_content().strip() or p.find(".//img") is not None:
                el.append(p)
        if el.tag not in BLOCKISH and el is not art:
            el.tag = "div"   # (a font or a span that now holds paragraphs is a block: its own cell does not wrap it in one)


def apply(page, url, recipe):
    """The page read with a recipe: (its article's HTML, ready for semantic.normalize; the counts of what was done;
    how many elements each selector matched)."""
    from lxml import html as lhtml
    tagged, seen = _tag(page, recipe)
    root = webpage.visible(tagged, url)
    art = root.xpath('//*[@data-tf-article]')
    if recipe.get("article") and not art:
        raise ValueError(f"article: {recipe['article']} matched nothing the reader can see")
    art = art[0] if art else (root.find(".//body") if root.find(".//body") is not None else root)
    done = {"dropped": 0, "content": 0, "figures": 0, "figures without a caption": 0}
    for el in art.xpath('.//*[@data-tf-drop]'):
        if el.getparent() is not None:
            el.drop_tree()
            done["dropped"] += 1
    for el in art.xpath('.//*[@data-tf-content]'):
        if el.tag in ("button", "label", "summary", "a"):
            el.tag = "span"
        done["content"] += 1
    for el in art.xpath('.//*[@data-tf-figure]'):
        if el.getparent() is None:
            continue
        card = _figure(el, url)
        if card.text_content() == "↗":
            done["figures without a caption"] += 1
        card.tail = el.tail
        el.getparent().replace(el, card)
        done["figures"] += 1
    _lazy(art)
    here = url.split("#")[0]
    for a in art.iter("a"):   # (a link within the page, made whole by visible(): its anchor again, as footnotes need it)
        if (a.get("href") or "").startswith(here + "#"):
            a.set("href", a.get("href")[len(here):])
    for el in art.iter("figure"):   # a figure with nothing drawn in it, its paragraphs text (The Guardian's explainers): a box
        if el.find(".//p") is not None or any(True for _ in el.iter("h2", "h3", "h4")):
            if not any(True for _ in el.iter("img", "picture", "svg", "canvas", "video", "audio", "iframe", "table", "math")):
                el.tag = "div"
    _paragraphs(art)
    webpage._hover_marks(art)
    notes = webpage._notes(art)
    webpage._hidden_out(art)
    done["notes"] = len(notes)
    art.tag = "div"   # (a cell, a font, a custom element: the article's box, read as one)
    html = lhtml.tostring(art, encoding="unicode")
    return webpage._noted(html, notes), done, seen


# ── what an agent is given ───────────────────────────────────────────
def _norm(s):
    s = unicodedata.normalize("NFKC", s).replace("​", "").replace("­", "")
    s = s.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"}))
    return re.sub(r"\s+", " ", s).strip()


def _sig(el):
    cls = (el.get("class") or "").split()
    s = el.tag + (f"#{el.get('id')}" if el.get("id") else "") + "".join(f".{c}" for c in cls[:4]) + ("…" if len(cls) > 4 else "")
    attrs = [f'{k}="{el.get(k)}"' for k in ("role", "aria-label", "aria-describedby", "itemprop", "data-testid") if el.get(k)]
    attrs += [k for k in el.attrib if k.startswith("data-") and not k.startswith("data-tf-") and k != "data-testid"][:3]
    return s + (f" [{' '.join(attrs)}]"[:140] if attrs else "")


def outline(root, budget=320):
    """The page as a tree for an agent: each element's tag, id, classes and roles, how many words it holds, the first
    words of the small ones; a run of like siblings once, counted; a wrapper of one child joined to it. The smallest
    parts are left out until it fits in about `budget` lines."""
    body = root.find(".//body")
    body = body if body is not None else root
    LOUD = {"figure", "canvas", "svg", "iframe", "video", "audio", "table", "details", "article", "main", "aside", "nav", "footer", "header"}

    def words(el):
        return len(el.text_content().split())

    def walk(el, depth, floor, out):
        kids = [c for c in el if isinstance(c.tag, str) and not c.get("data-tf-css-hidden")]
        chain = [_sig(el)]
        while len(kids) == 1 and not (el.text or "").strip() and kids[0].tag not in LOUD:
            el = kids[0]
            chain.append(_sig(el))
            kids = [c for c in el if isinstance(c.tag, str) and not c.get("data-tf-css-hidden")]
        n = words(el)
        own = _norm(el.text_content())
        flat = not any(isinstance(d.tag, str) and d.tag in BLOCKISH for d in el.iterdescendants())
        leaf = n < floor or not kids or depth > 14 or flat   # (words and inline marks only: one block of text)
        line = "  " * depth + " > ".join(chain) + f"  ({n}w)"
        if leaf and own:
            line += f'  "{own[:70]}{"…" if len(own) > 70 else ""}"'
        out.append(line)
        if leaf:
            return
        i = 0
        while i < len(kids):
            c, j = kids[i], i + 1
            while j < len(kids) and _sig(kids[j]) == _sig(c):
                j += 1
            run = kids[i:j]
            each = [words(x) for x in run]
            if sum(each) or any(x.tag in LOUD for x in run):
                if j - i > 2 and max(each) <= sum(each) / 2:   # (like siblings, none holding most of the words: once)
                    first = next((x for x, n in zip(run, each) if n), c)
                    out.append("  " * (depth + 1) + f"{_sig(c)}  ×{j - i}  ({sum(each)}w in all)"
                               + (f'  first: "{_norm(first.text_content())[:60]}"' if sum(each) else ""))
                else:
                    for x, n in zip(run, each):
                        if n or x.tag in LOUD:
                            walk(x, depth + 1, floor, out)
            i = j
    for floor in (12, 30, 80, 200, 600, 2000):
        out = []
        walk(body, 0, floor, out)
        if len(out) <= budget:
            break
    return "\n".join(out[:budget]) + (f"\n… ({len(out) - budget} lines more)" if len(out) > budget else "")


def signals(page, root):
    """What a recipe may have to say: notes on hover, words in controls, figures drawn by scripts, a paywall's marks,
    how much of the page needs scripts to show, class names a build generates."""
    out = {}
    tips = root.xpath('//*[@role="tooltip"]')
    out["hover notes (role=tooltip)"] = f"{len(tips)}, e.g. {_sig(tips[0])}" if tips else 0
    plain = [el for el in root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " tooltip ") or contains(@class, "popover") '
                                     'or contains(@class, "footnote") or contains(@class, "sidenote")]') if el.get("role") != "tooltip"]
    out["note-like classes without a role"] = f"{len(plain)}, e.g. {_sig(plain[0])}" if plain else 0
    cells = root.xpath('//td//button[normalize-space()] | //th//button[normalize-space()]')
    out["buttons with words in table cells"] = f"{len(cells)}, e.g. {_sig(cells[0])} in {_sig(next(cells[0].iterancestors('table')))}" if cells else 0
    drawn = {t: len(root.xpath(f"//{t}")) for t in ("canvas", "svg", "iframe", "video", "audio")}
    out["drawn or embedded (canvas, svg, iframe, video, audio)"] = drawn
    figs = [f for f in root.iter("figure") if f.find(".//img") is None]
    out["figures without a picture"] = f"{len(figs)}: " + ", ".join(_sig(f) for f in figs[:6]) if figs else 0
    out["details / tab panels"] = len(root.xpath("//details | //*[@role='tabpanel']"))
    hid = root.xpath("//*[@data-tf-css-hidden]")
    if hid or root.xpath("//*[@data-tf-shadow]"):
        out["a browser's snapshot"] = (f"{len(hid)} elements it did not show (left out; one on a mark becomes a note), "
                                       f"{len(root.xpath('//*[@data-tf-shadow]'))} shadow roots spelled out, "
                                       f"{len(root.xpath('//*[@data-tf-frame]'))} frames put in place")
    # a paywall: what the page says of itself (schema.org), its classes, its words
    free = []
    for s in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page if isinstance(page, str) else "", re.S | re.I):
        try:
            j = json.loads(s)
        except ValueError:
            continue
        stack = j if isinstance(j, list) else [j]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if str(x.get("isAccessibleForFree", "")).lower() in ("false", "0"):
                    part = x.get("hasPart")
                    parts = part if isinstance(part, list) else [part] if part else []
                    free.append("isAccessibleForFree false" + "".join(f", hidden part {p.get('cssSelector')}" for p in parts if isinstance(p, dict)))
                stack += [v for v in x.values() if isinstance(v, (dict, list))]
            elif isinstance(x, list):
                stack += x
    walls = sorted({_sig(el) for el in root.iter() if isinstance(el.tag, str) and PAYWALL_CLASS.search((el.get("class") or "") + " " + (el.get("id") or ""))})
    said = PAYWALL_WORDS.findall(root.text_content())
    out["paywall"] = ("; ".join(free + walls[:4] + [f'the page says "{w}"' for w in said[:2]])) or "none seen"
    raw = page if isinstance(page, str) else page.decode("utf-8", "replace")
    scripts = sum(len(s) for s in re.findall(r"<script[^>]*>(.*?)</script>", raw, re.S | re.I))
    text = len(_norm(root.text_content()))
    marks = [m for m in ("__NEXT_DATA__", "__NUXT__", "__APOLLO_STATE__", "window.__INITIAL_STATE__", 'id="root"', 'id="app"') if m in raw]
    out["scripts"] = f"{scripts:,} characters of script, {text:,} of visible text" + (f"; {', '.join(marks)}" if marks else "")
    classes = [c for el in root.iter() if isinstance(el.tag, str) for c in (el.get("class") or "").split()]
    gen = [c for c in classes if GENERATED.match(c)]
    out["class names that look generated"] = f"{len(gen)} of {len(classes)}, e.g. {', '.join(sorted(set(gen))[:4])}" if gen else 0
    return out


# ── the check ────────────────────────────────────────────────────────
def _where(el, stop):
    for a in el.iterancestors():
        if a is stop:
            break
        cls = [c for c in (a.get("class") or "").split() if not GENERATED.match(c)]
        if a.get("id") or cls or a.tag in ("table", "figure", "aside", "nav", "footer", "header", "section"):
            return a.tag + (f"#{a.get('id')}" if a.get("id") else "") + "".join(f".{c}" for c in cls[:2])
    return el.tag


def _blocks(root):
    """The page's smallest blocks of text: [(element, its words, normalized)]."""
    out = []
    for el in root.iter(*BLOCKS):
        if any(d.tag in BLOCKS for d in el.iterdescendants() if isinstance(d.tag, str)):
            continue
        t = _norm(el.text_content())
        if t:
            out.append((el, t))
    return out


def shown(page, url, recipe=None):
    """The page as its reader reads it, with the recipe's choices on it: its notes and their marks out of the text (they
    show on hover), its pictures' alt texts in (a screen reader says them). (its tree, its words, normalized)"""
    root = seen(_tag(page, recipe)[0] if recipe else page, url)
    webpage._hover_marks(root)
    webpage._notes(root)
    webpage._hidden_out(root)
    for m in root.xpath('//*[@role="doc-noteref"] | //*[contains(concat(" ", @class, " "), " footnote-ref ")]'):
        webpage._swap(m, "")   # (an endnote's mark: in the reading, the note on hover)
    for img in root.iter("img"):
        if (img.get("alt") or "").strip():
            img.tail = f" {img.get('alt')} " + (img.tail or "")
    return root, _norm(webpage.NOTE_AT.sub("", root.text_content()))


MARKS = re.compile(r"\[\d{1,3}\]|↩︎|↩|\u21a9\ufe0e?")   # (a footnote's mark and its way back, on the page: on hover in the reading)


def _runs(toks):
    """A paragraph's words between its atoms (formulas, notes, references): [text]."""
    out, cur = [], ""
    for tk in toks:
        if "t" not in tk:
            out.append(cur)
            cur = ""
            continue
        cur += tk["t"] + (" " if tk.get("s") else "")
    return [r for r in out + [cur] if r.strip()]


def check(page, url, html, recipe=None):
    """The reading (html, normalized) against the page as its reader sees it: words taken that the page does not show
    (there should be none), the page's blocks the reading lacks (within the recipe's article, when it names one),
    grouped by where they are, and paragraphs a reader's browser could not find again by their first words."""
    from bs4 import BeautifulSoup
    from . import semantic
    from .parse import parse
    from .tokens import plain
    root, text = shown(page, url, recipe)
    flat = text.replace(" ", "")   # (two blocks side by side on the page, a title and its authors, have no space between)
    norm = semantic.normalize(html, sizes=True)
    doc = parse(norm, {"id": "web-check"})
    soup = BeautifulSoup(norm, "lxml")
    told = []   # (a note's words: a block of the page, an endnote, may be one)
    for c in soup.select("span.ltx_note_content"):
        for m in c.select("sup.ltx_note_mark"):
            m.decompose()
        told.append(_norm(c.get_text(" ")).replace(" ", ""))
    for note in soup.select("span.ltx_note"):   # (a note is on hover, as on the page: not in the sentence)
        note.decompose()
    got = _norm(soup.get_text(" ").replace("🖼", " "))   # (a picture this check does not fetch: its place, not a word)
    units = [_norm(plain(u["toks"], doc["atoms"], math_dollars=False)) for u in doc["units"].values()]
    not_seen, twice = [], []
    for u in doc["units"].values():
        for run in (r.replace("🖼", " ") for r in _runs(u["toks"])):   # (the words between its formulas and other atoms: a formula reads otherwise on the page)
            for piece in re.split(r"(?<=[.!?。！？])\s+", _norm(run)):
                if len(piece.split()) >= 5 and piece.replace(" ", "") not in flat:
                    not_seen.append(piece)
    for t in units:
        head = " ".join(t.replace("🖼", " ").split()[:10])
        if len(t.split()) >= 6 and flat.count(head.replace(" ", "")) != 1:
            twice.append(head)
    hit = root.xpath('//*[@data-tf-article]') if recipe and recipe.get("article") else []
    area = hit[0] if hit else root
    carded = 0
    for el in area.xpath('.//*[@data-tf-drop] | .//*[@data-tf-figure]'):
        if el.getparent() is not None:
            carded += len(_blocks(el)) if el.get("data-tf-figure") else 0
            el.drop_tree()
    missing, flat_got = {}, got.replace(" ", "") + "|" + "|".join(told)
    page_blocks = sum(1 for _, t in _blocks(area) if len(t.split()) >= 8 or len(t) >= 24)
    for el, t in _blocks(area):
        t = _norm(webpage.NOTE_AT.sub("", t))
        f = MARKS.sub("", t).replace(" ", "")
        if not f or f in flat_got:
            continue
        said = [MARKS.sub("", x).replace(" ", "") for x in re.split(r"(?<=[.!?。！？])\s+", t) if len(x.split()) >= 4 or len(x) >= 12]
        if len(said) > 1 and sum(x in flat_got for x in said) >= 0.8 * len(said):
            continue   # (a long block, its sentences there: told apart by an atom or a space the reading moved)
        missing.setdefault(_where(el, area), []).append(t)
    return {"words": len(got.split()), "paragraphs": len(units), "notes": norm.count("ltx_note ltx_role_footnote"),
            "not on the page": not_seen[:8], "not on the page (count)": len(not_seen),
            "missing": {k: (len(v), v[:3]) for k, v in sorted(missing.items(), key=lambda kv: -len(kv[1]))[:12]},
            "missing (blocks)": sum(len(v) for v in missing.values()), "in figures shown as a link": carded,
            "not found again by its words": len(twice), "not found again (e.g.)": twice[:3], "page blocks": page_blocks}


def report(c):
    run = (f"   <- the page has {c['page blocks']} blocks of text here: paragraphs run together?"
           if c.get("page blocks", 0) >= 8 and c["paragraphs"] < c["page blocks"] / 2 else "")
    lines = [f"words: {c['words']:,}  paragraphs: {c['paragraphs']}  notes: {c['notes']}" + run,
             f"words the page does not show: {c['not on the page (count)']}" + "".join(f'\n    "{p[:110]}"' for p in c["not on the page"]),
             f"blocks of the page not in the reading: {c['missing (blocks)']}"
             + (f" (and {c['in figures shown as a link']} in the figures the recipe shows as a link)" if c.get("in figures shown as a link") else "")]
    for where, (n, eg) in c["missing"].items():
        lines.append(f"    {where}: {n}" + "".join(f'\n        "{e[:90]}"' for e in eg))
    lines.append(f"paragraphs a browser could not find again by their first words alone: {c['not found again by its words']}"
                 + "".join(f'\n    "{e[:90]}"' for e in c["not found again (e.g.)"]))
    return "\n".join(lines)


def snapshot(url, path=None, rendered=False):
    """The page: fetched as TextFold fetches it (no scripts run), or a file saved before, as fetched or as a browser
    rendered it. (text, its address, how it was had)."""
    if path:
        from pathlib import Path
        return Path(path).read_text(encoding="utf-8", errors="replace"), url, "rendered" if rendered else "saved"
    data, final, charset = webpage._get(url)
    return data.decode(charset or "utf-8", "replace"), final, "fetched"


def brief(url, page, final, how):
    """What an agent is given, as text: the snapshot, the page's outline, its signals, and the check of TextFold's
    reading of it with no recipe."""
    root = seen(page, final)
    out = [f"# {final}", f"snapshot: {how}; {len(page):,} characters", "", "## Signals"]
    out += [f"- {k}: {v}" for k, v in signals(page, root).items()]
    webpage._hidden_out(root)   # (a browser's snapshot: the outline is of what it showed)
    out += ["", "## Outline (what the reader can see)", outline(root), "", "## TextFold's reading with no recipe"]
    try:
        _, html, _ = webpage.read(page, final)
        out.append(report(check(page, final, html)))
    except ValueError as e:
        out.append(f"none: {e} (too few words: the page may show its text with scripts, or behind a sign-in)")
    return "\n".join(out)


def tried(page, final, recipe):
    """The page read with a recipe, and the check of it, as text."""
    html, done, matched = apply(page, final, recipe)
    wall = signals(page, seen(page, final))["paywall"]
    out = ([f"NOTE: the page marks a paywall ({wall[:160]}). A subscriber's snapshot holds the whole article; one taken "
            "without access may hold part of it: then say so, and never ask for what it does not show.", ""] if wall != "none seen" else [])
    out += ["## Selectors", *[f"- {s}: {n}" + ("   <- matched nothing" if not n else "") for s, n in matched.items()],
            "", "## Done", *[f"- {k}: {v}" for k, v in done.items()], "", "## The reading, checked",
            report(check(page, final, html, recipe))]
    return "\n".join(out), html


def host_of(url):
    return re.sub(r"^www\.", "", (urllib.parse.urlparse(url).hostname or "").lower())
