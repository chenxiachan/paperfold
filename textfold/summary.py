"""Every note of the library in one list, and a summary of the notes the reader picks from it.

The notes page (/notes) lists every highlight, note and conversation of every document, newest first (everything).
The reader ticks the ones to think over, and make() writes their summary as a document of the library, dated and kept
as it was made, in the folder of summaries. Its first section is the summary, a paragraph a point: the point, why,
then the notes it rests on, word for word, by the numbers they were sent with. The point and its reason are that
paragraph's written levels (Takeaway, Key) and the notes are its evidence (Brief), so unfolding a point reads the notes
it came from. The second section is every note picked, under the document it is on.

Those are copies, made with the summary: a note and its text may change after it. Each copy links to the place as it
is now (#n=, the note; #u=, its paragraph, opened when the note is gone). A point the model gave no note for says so.
Without a model the summary is the second section alone: no point is written.
"""
import json
import re
import time

from . import ladder, langs, library, llm, local, notes, store
from .tokens import plain

SCHEMA = {"type": "object", "properties": {
    "overview": {"type": "object", "properties": {"takeaway": {"type": "string"}, "topic": {"type": "string"}},
                 "required": ["takeaway", "topic"]},
    "points": {"type": "array", "items": {"type": "object", "properties": {
        "point": {"type": "string"}, "reason": {"type": "string"}, "topic": {"type": "string"},
        "notes": {"type": "array", "items": {"type": "integer"}}},
        "required": ["point", "reason", "topic", "notes"]}}},
    "required": ["overview", "points"]}

SYSTEM = ("You summarize a reader's own notes for them. You stay within what the notes say, keep their qualifiers, "
          "and name the notes each point rests on.")

PROMPT = """These are notes a reader made while reading, numbered. Each is a passage they marked in a text (quote), \
what they wrote about it (wrote), or a question they asked about it with the answer's one-line conclusion.

Write what the reader was thinking across these notes, in 2 to 6 points. For each point:
- point: one sentence that states it and reads on its own;
- reason: one sentence on why, from the notes;
- topic: two to four words copied from the point, as they stand in it;
- notes: the numbers of the notes it rests on.
Stay within what the notes say: add no claim they do not make, and keep their qualifiers (may, only when, but). Where \
notes disagree, or a later one revises an earlier one, say so in that point. Then one sentence for the whole set \
(overview.takeaway) and its topic, two to four words copied from that sentence.

Write in {language}. Quote nothing: the reader sees the notes under each point.

Texts:
{texts}

Notes:
{items}
"""

LANG_NAMES = {"zh": "Simplified Chinese", "zh-Hant": "Traditional Chinese", "ja": "Japanese", "ko": "Korean",
              "de": "German", "fr": "French", "es": "Spanish", "pt": "Portuguese", "it": "Italian", "ru": "Russian",
              "ar": "Arabic", "en": "English"}

WORDS = {
    "en": {"title": "Summary · {date} · {docs} texts · {n} notes", "points": "Summary", "picked": "The notes picked",
           "intro": "Made on {when} from {n} notes picked in {docs} texts. Unfold a point to read the notes it rests "
                    "on. The notes below are copies made then: a text or a note may have changed since, and "
                    "\"there\" opens it as it is now.",
           "local": "Made on {when} from {n} notes picked in {docs} texts. No model was available, so only the notes "
                    "are listed. They are copies made then: \"there\" opens each as it is now.",
           "wrote": "I wrote: ", "asked": "I asked: ", "answer": "Answer: ", "there": "there",
           "no_basis": "(The model named no note for this point.)", "folder": "Summaries", "stop": "."},
    "zh": {"title": "总结 · {date} · {docs} 篇 · {n} 条", "points": "总结", "picked": "所选的笔记",
           "intro": "{when} 生成，依据 {docs} 篇文本里勾选的 {n} 条笔记。展开每一点，读到它依据的笔记和原句。下面的笔记是当时的快照，"
                    "文本和笔记后来可能改过，点“原处”打开它现在的样子。",
           "local": "{when} 生成，依据 {docs} 篇文本里勾选的 {n} 条笔记。没有可用的模型，这里只列出笔记。它们是当时的快照，"
                    "点“原处”打开它现在的样子。",
           "wrote": "我写：", "asked": "我问：", "answer": "回答：", "there": "原处",
           "no_basis": "（模型没有为这一点标出依据。）", "folder": "总结", "stop": "。"},
}
WORDS["zh-Hant"] = {**WORDS["zh"], "title": "總結 · {date} · {docs} 篇 · {n} 條", "points": "總結", "picked": "所選的筆記",
                    "intro": "{when} 生成，依據 {docs} 篇文本裡勾選的 {n} 條筆記。展開每一點，讀到它依據的筆記和原句。下面的筆記是當時的快照，"
                             "文本和筆記後來可能改過，點「原處」打開它現在的樣子。",
                    "local": "{when} 生成，依據 {docs} 篇文本裡勾選的 {n} 條筆記。沒有可用的模型，這裡只列出筆記。它們是當時的快照，"
                             "點「原處」打開它現在的樣子。",
                    "wrote": "我寫：", "asked": "我問：", "answer": "回答：", "there": "原處",
                    "no_basis": "（模型沒有為這一點標出依據。）", "folder": "總結"}
MOST = 120          # notes in one summary: more is asked to be picked again, not cut
MARK = re.compile(r"^\s*\[(\d+)\]")


def everything(papers):
    """Every note of the documents listed (the server's list: titles, names), each with the id of its document, the
    newest first; and which summaries each note went into: {papers: {id: {title, name, lang, summary}}, notes: [...],
    summaries: {id: {title, made}}, used: {"<paper>|<note>": [summary ids]}}."""
    out, rows, sums, used = {}, [], {}, {}
    for p in papers:
        pid = p["id"]
        has = (store.pdir(pid) / "notes.json").exists()
        if not has and not p.get("summary"):
            continue
        meta = json.loads(store.read_text(store.pdir(pid) / "meta.json"))
        title = p.get("name") or p.get("title") or pid
        if isinstance(meta.get("summary"), dict):
            sums[pid] = {"title": title, "made": str(meta["summary"].get("made") or "")}
            for x in meta["summary"].get("notes") or []:
                if isinstance(x, dict) and x.get("paper") and x.get("note"):
                    used.setdefault(f"{x['paper']}|{x['note']}", []).append(pid)
        try:
            ns = notes.read(pid).get("notes") or [] if has else []
        except (OSError, ValueError):
            continue   # (a notes file half written by a program of its own: the others are listed)
        if not ns:
            continue
        out[pid] = {"title": p.get("title") or pid, "name": p.get("name") or "", "lang": store.text_lang(pid),
                    "summary": pid in sums}
        rows += [{**n, "paper": pid} for n in ns if isinstance(n, dict) and n.get("id")]
    rows.sort(key=lambda n: n.get("created") or "", reverse=True)
    return {"papers": out, "notes": rows, "summaries": sums, "used": used}


def _flat(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _md(s):
    """Text as Markdown that reads as the text: its marks escaped."""
    return re.sub(r"([\\`*_\[\]<>#|~$])", r"\\\1", _flat(s))


def _day(stamp):
    return (stamp or "")[:10]


def _picked(items):
    """[{paper, note}] as [(pid, title, note)], the notes found, in the order they were made in, a text's together (the
    text whose first note came first, first). ValueError: none of them found, or too many."""
    by_doc, order = {}, []
    for it in items if isinstance(items, list) else []:
        pid, nid = str((it or {}).get("paper", "")), str((it or {}).get("note", ""))
        if not store.valid_id(pid) or not (store.pdir(pid) / "meta.json").exists():
            continue
        if pid not in by_doc:
            by_doc[pid] = set()
            order.append(pid)
        by_doc[pid].add(nid)
    groups = []
    for pid in order:
        meta = json.loads(store.read_text(store.pdir(pid) / "meta.json"))
        title = library.name_of(pid) or meta.get("title") or pid
        ns = sorted((n for n in notes.read(pid).get("notes") or [] if n.get("id") in by_doc[pid]), key=lambda n: n.get("created") or "")
        if ns:
            groups.append([(pid, title, n) for n in ns])
    out = [x for g in sorted(groups, key=lambda g: g[0][2].get("created") or "") for x in g]
    if not out:
        raise ValueError("no notes picked")
    if len(out) > MOST:
        raise ValueError(f"too many notes: {len(out)} (at most {MOST})")
    return out


def _for_model(k, title_no, n):
    a = n.get("anchor") or {}
    q = _flat((a.get("quote") or {}).get("exact"))
    bits = [f"[{k}] (T{title_no}, {_day(n.get('created'))})"]
    if q:
        bits.append(f'quote: "{q}"')
    if (n.get("text") or "").strip():
        bits.append(f'wrote: "{_flat(n["text"])}"')
    for t in notes.turns(n)[:4]:
        if t.get("q"):
            bits.append(f'asked: "{_flat(t["q"])}"' + (f' answer: "{_flat(t["takeaway"])}"' if t.get("takeaway") else ""))
    return " ".join(bits)


def _for_page(k, pid, title, n, W):
    """A note as the summary keeps it: its number, the passage, what the reader wrote or asked, where, and a link there."""
    a = n.get("anchor") or {}
    q = _flat((a.get("quote") or {}).get("exact"))
    bits = [f"[{k}]"]   # (the reader's own words first: they are what a note's line shows when it is folded)
    if (n.get("text") or "").strip():
        bits.append(_end(W["wrote"] + _md(n["text"]), W))
    for t in notes.turns(n)[:4]:
        if t.get("q"):
            bits.append(_end(W["asked"] + _md(t["q"]), W))
        if t.get("takeaway"):
            bits.append(_end(W["answer"] + _md(t["takeaway"]), W))
    if q:
        bits.append(f"“{_md(q)}”")
    lang = a.get("lang") or ""
    there = f"/p/{pid}" + (f"?lang={lang}" if lang else "") + f"#n={n['id']}" + (f"&u={a['unit']}" if a.get("unit") else "")
    bits.append(f"({_md(title)}, {_day(n.get('created'))}, [{W['there']}]({there})){W['stop']}")   # (a note ends a sentence)
    return " ".join(bits)


def _end(s, W):
    """A sentence ended, as the reader's own words often are not."""
    return s if re.search(r"[.!?。！？…]$", s) else s + W["stop"]


def _texts(picked):
    seen = {}
    for pid, title, _ in picked:
        seen.setdefault(pid, (len(seen) + 1, title))
    return seen


def ask_model(picked, spec, ui, cache_dir):
    """The model's summary of the notes: (overview, points), each point's notes the numbers sent that it named."""
    seen = _texts(picked)
    texts = "\n".join(f"T{no}. {title}" for no, title in seen.values())
    items = "\n".join(_for_model(k, seen[pid][0], n) for k, (pid, _, n) in enumerate(picked, 1))
    prompt = PROMPT.format(language=LANG_NAMES.get(ui, "English"), texts=texts, items=items)
    rec, _ = llm.call(prompt, SCHEMA, spec, cache_dir, timeout=600, system=SYSTEM)
    out = rec["out"] if isinstance(rec.get("out"), dict) else {}
    points = []
    for p in out.get("points") or []:
        if not isinstance(p, dict) or not _flat(p.get("point")):
            continue
        nums = []
        for x in p.get("notes") or []:
            if isinstance(x, int) and 1 <= x <= len(picked) and x not in nums:
                nums.append(x)   # (a number that was not sent is left out: the point says what it rests on, or that it rests on none)
        points.append({"point": _flat(p["point"]), "reason": _flat(p.get("reason")), "topic": _flat(p.get("topic")), "notes": nums})
    ov = out.get("overview") if isinstance(out.get("overview"), dict) else {}
    return {"takeaway": _flat(ov.get("takeaway")), "topic": _flat(ov.get("topic"))}, points


def write_md(picked, W, when, points):
    seen = _texts(picked)
    n, docs = len(picked), len(seen)
    title = W["title"].format(date=when[:10], docs=docs, n=n)
    page = {k: _for_page(k, pid, t, note, W) for k, (pid, t, note) in enumerate(picked, 1)}
    out = [f"# {_md(title)}", "", (W["intro"] if points else W["local"]).format(when=when, docs=docs, n=n), ""]
    if points:
        out += [f"## {W['points']}", ""]
        for p in points:
            head = f"**{_md(p['point'])}** {_md(p['reason'])}".strip()
            body = " ".join(page[k] for k in p["notes"]) or W["no_basis"]
            out += [f"{head} {body}", ""]
    out += [f"## {W['picked']}", ""]
    for pid, (no, t) in seen.items():
        out += [f"### {_md(t)}", ""]
        out += [page[k] + "\n" for k, (p, _, _) in enumerate(picked, 1) if p == pid]
    return title, "\n".join(out)


def _evidence(u, atoms):
    """The sentences of a point's paragraph from the first note on ([3] …): the notes it rests on, all of them."""
    first = next((i for i, (s, e) in enumerate(u["sents"]) if MARK.match(plain(u["toks"][s:e], atoms))), None)
    return [] if first is None else list(range(first, len(u["sents"])))


def _line(n, W):
    """A note in one line, as its copy shows it folded: what the reader wrote, else asked, else the passage."""
    first = next((t["q"] for t in notes.turns(n) if t.get("q")), "")
    q = _flat(((n.get("anchor") or {}).get("quote") or {}).get("exact"))
    return _flat(n.get("text")) or (W["asked"] + _flat(first) if first else "") or f"“{q}”"


def _topic(line):
    """A line's topic: its first clause when that is short (twelve characters of a CJK line, four words of another),
    else none (the ladder takes the line's head words, as for any text folded without a model)."""
    head = re.split(r"[，。；：！？、,.;:!?]", line.strip("“”\"' "))[0].strip()
    short = len(head) <= 12 if ladder._cjk_share(head) > 0.2 else len(head.split()) <= 4
    return head if head and short else ""


def fold_it(pid, overview, points, model, W, lines, made=""):
    """The levels of a summary: the points' as the model wrote them (evidence: the notes they rest on); each note's
    copy folds to the reader's own words (lines: by its number)."""
    doc = store.parsed(pid)
    doc["meta"]["lang"] = W["lang"] if W["lang"] in langs.LANGS else store.text_lang(pid)   # (the reader's: notes in many)
    cjk = ladder.cjk_doc(doc)
    A = doc["atoms"]
    for u in doc["units"].values():
        m = MARK.match(plain(u["toks"][u["sents"][0][0]:u["sents"][0][1]], A)) if u["sents"] else None
        first = plain(u["toks"][u["sents"][0][0]:u["sents"][0][1]], A) if u["sents"] else ""
        if made and first.startswith(made):   # the summary's first line: when it was made, from what
            u["lad"] = ladder.assemble(u, {"takeaway": first, "reason": "", "topic": made, "role": "context", "evidence": [0]}, A, "", cjk)
        elif m and int(m.group(1)) in lines:   # a note's copy
            line = f"[{m.group(1)}] {lines[int(m.group(1))]}"
            u["lad"] = ladder.assemble(u, {"takeaway": line, "reason": "", "topic": _topic(lines[int(m.group(1))].removeprefix(W["asked"])),
                                           "role": "claim", "evidence": [0]}, A, "", cjk)
        else:
            u["lad"] = ladder.local(u, A, cjk)
    chunk = next((c for c in doc["chunks"] if _flat(c.get("title")) == W["points"]), None) if points else None
    if chunk and len(chunk["units"]) == len(points):
        for uid, p in zip(chunk["units"], points):
            u = doc["units"][uid]
            ev = (_evidence(u, A) if p["notes"] else []) or [0]
            o = {"takeaway": p["point"], "reason": p["reason"], "topic": p["topic"], "role": "claim", "evidence": ev}
            u["lad"] = ladder.assemble(u, o, A, model, cjk)
            u["lad"]["ev"] = ev   # (every note it rests on at Brief, not a paper's three sentences)
        if overview.get("takeaway"):
            chunk["lad"] = ladder.section_ladder(overview, 3, doc, chunk)
    for c in doc["chunks"]:
        c.setdefault("lad", None)
    store.save_en(doc, model)


def make(items, spec, ui="en", when=None):
    """A summary of the notes picked ([{paper, note}]) as a document of the library, in the folder of summaries: its
    id. spec: the model (None: the notes listed, no point written)."""
    W = {**(WORDS.get(ui) or WORDS["en"]), "lang": ui if ui in WORDS else "en"}
    picked = _picked(items)
    when = when or time.strftime("%Y-%m-%d %H:%M")
    overview, points, model = {}, [], ""
    if spec is not None:
        cache = store.library_root() / "summary-cache"
        cache.mkdir(parents=True, exist_ok=True)
        overview, points = ask_model(picked, spec, ui, cache)
        model = llm.label(spec)
    title, md = write_md(picked, W, when, points)
    name = f"summary-{when[:10]}.md"
    t, html, meta = local._read_md(md, name)
    meta["label"] = t   # (the reader's bar names it by its title, not by a file it never was)
    pid = local.make_id(t, md)
    meta["summary"] = {"made": when, "model": model, "notes": [{"paper": p, "note": n["id"]} for p, _, n in picked]}
    local.store_doc(pid, html, {"id": pid, **meta}, "source.md", md, lambda folder: local.Images(folder, None).resolve, sizes=True)
    fold_it(pid, overview, points, model, W, {k: _line(n, W) for k, (_, _, n) in enumerate(picked, 1)}, when)
    fs = library.folders()
    f = next((x for x in fs["folders"] if x["name"] == W["folder"] and not x.get("parent")), None)
    library.change({"op": "move", "papers": [pid], "folder": f["id"]} if f else {"op": "new", "name": W["folder"], "papers": [pid]})
    return pid
