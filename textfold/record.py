"""Every note of the library in one list, and a reading record of the notes the reader picks from it.

The notes page (/notes) lists every highlight, note and conversation of every document, newest first (everything).
The reader picks some (a day, a month, the days of a stretch, a text) and asks four questions of them: what did I
read, what was I curious about, what did I get, what did I attend to. The record answers them from the notes and the
texts alone, no model: the texts the notes are on, each with its own line; the questions asked, each with its answer
in a line; what the reader wrote; the passages marked, under the section each is in and that section's own line.
Each note keeps its text and its section with it, so it reads without the reader recalling where it came from.

It is a document of the library (record()), dated and kept as it was made, in the folder of records, each entry
linking to its place as it is now (#n=, the note; #u=, its paragraph, opened when the note is gone); or Markdown for
Obsidian (obsidian()), each text a [[link]] to the note TextFold's reader saves for it (named alike) and each note a
link to its block there (^n-…), and a textfold:// link that opens the place in TextFold.
"""
import calendar
import json
import re
import time

from . import fold, langs, ladder, library, local, notes, store
from .tokens import plain

WORDS = {
    "en": {"title": "Reading record · {period}", "read": "What I read", "curious": "What I was curious about",
           "got": "What I got", "attend": "What I attended to", "to": "to", "notes": "{n} notes",
           "intro": "Made on {when} from {n} notes in {d} texts, under four questions. Each entry is a copy made then: "
                    "\"there\" opens it as it is now.",
           "answer": "Answer: ", "there": "there", "open": "open", "folder": "Reading records", "whole": "the whole text",
           "made_with": "Made with TextFold"},
    "zh": {"title": "阅读记录 · {period}", "read": "读了什么", "curious": "好奇什么", "got": "得到了什么", "attend": "关注的点",
           "to": "至", "notes": "{n} 条笔记", "intro": "{when} 生成，依据 {d} 篇文本里的 {n} 条笔记，按四个问题排列。每一条都是当时的快照，点“原处”打开它现在的样子。",
           "answer": "回答：", "there": "原处", "open": "打开", "folder": "阅读记录", "whole": "整篇文本", "made_with": "用 TextFold 生成"},
}
WORDS["zh-Hant"] = {**WORDS["zh"], "title": "閱讀記錄 · {period}", "read": "讀了什麼", "curious": "好奇什麼", "got": "得到了什麼",
                    "attend": "關注的點", "notes": "{n} 條筆記",
                    "intro": "{when} 生成，依據 {d} 篇文本裡的 {n} 條筆記，按四個問題排列。每一條都是當時的快照，點「原處」打開它現在的樣子。",
                    "answer": "回答：", "there": "原處", "open": "開啟", "folder": "閱讀記錄", "whole": "整篇文本", "made_with": "用 TextFold 生成"}
MOST = 400   # notes in one record


def everything(papers):
    """Every note of the documents listed (the server's list: titles, names), each with the id of its document, the
    newest first; and which records each note went into: {papers: {id: {title, name, lang, summary}}, notes: [...],
    summaries: {id: {title, made}}, used: {"<paper>|<note>": [record ids]}}."""
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


def _local_day(stamp):
    """A note's day where the reader is (its time is kept in UTC)."""
    try:
        return time.strftime("%Y-%m-%d", time.localtime(calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S"))))
    except (TypeError, ValueError):
        return (stamp or "")[:10]


def _words(W, s):
    """A line the reader's own words end, ended."""
    return s if re.search(r"[.!?。！？…]$", s) else s + ("。" if re.search(r"[　-鿿]$", s) else ".")


def _picked(items):
    """[{paper, note}] as [(pid, title, note)], the notes found, in the order they were made, a text's together (the
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


def gather(items, W):
    """What the four questions are answered from: the texts (each with its own line, its notes' days and how many), the
    questions asked, what the reader wrote, the passages marked by section (each with that section's line)."""
    picked = _picked(items)
    texts, asked, wrote, marked = {}, [], [], {}
    for pid, title, n in picked:
        if pid not in texts:
            try:
                doc = fold.document(pid, None)
            except Exception:   # (a text that no longer reads: its notes are listed without its sections)
                doc = {"sections": []}
            # its own line: its abstract's, else its first paragraph's that says something (a caption, a list's item,
            # a heading-length line do not)
            units = [u for s in doc["sections"] for u in s.get("units") or []]
            first = next((u for u in units if u.get("kind") == "abstract"), None) or next(
                (u for u in units if u.get("kind") == "paragraph" and len(_flat(u.get("takeaway"))) >= 12), None)
            line = _flat((first or {}).get("takeaway"))
            where = {u["id"]: s for s in doc["sections"] for u in s.get("units") or []}
            texts[pid] = {"title": title, "line": line, "days": [], "n": 0, "where": where, "lang": store.text_lang(pid)}
        t = texts[pid]
        t["days"].append(_local_day(n.get("created")))
        t["n"] += 1
        a = n.get("anchor") or {}
        sec = t["where"].get(a.get("unit")) or {}
        entry = {"pid": pid, "title": title, "note": n, "day": _local_day(n.get("created")),
                 "section": _flat(sec.get("title")) or (W["whole"] if not a.get("unit") else ""), "quote": _flat((a.get("quote") or {}).get("exact"))}
        for turn in notes.turns(n):
            if _flat(turn.get("q")):
                asked.append({**entry, "q": _flat(turn["q"]), "a": _flat(turn.get("takeaway"))})
        if _flat(n.get("text")):
            wrote.append({**entry, "text": _flat(n["text"])})
        if entry["quote"]:
            sid = sec.get("id") or ""
            marked.setdefault(pid, {}).setdefault(sid, {"title": _flat(sec.get("title")), "line": _flat(sec.get("takeaway")), "notes": []})["notes"].append(entry)
    return picked, texts, asked, wrote, marked


def _period(picked, W):
    days = sorted({_local_day(n.get("created")) for _, _, n in picked})
    return days[0] if len(days) == 1 else f"{days[0]} {W['to']} {days[-1]}"


def _span(days, W):
    days = sorted(days)
    return days[0][5:] if days[0] == days[-1] else f"{days[0][5:]} {W['to']} {days[-1][5:]}"


def _there(e):
    a = e["note"].get("anchor") or {}
    lang = a.get("lang") or ""
    return f"/p/{e['pid']}" + (f"?lang={lang}" if lang else "") + f"#n={e['note']['id']}" + (f"&u={a['unit']}" if a.get("unit") else "")


def record_md(items, W, when):
    """The record as TextFold reads it: a heading a question, a paragraph an entry, each opening with its line (what
    the levels fold it to: lines, below)."""
    picked, texts, asked, wrote, marked = gather(items, W)
    period, lines = _period(picked, W), []
    out = [f"# {_md(W['title'].format(period=period))}", "",
           W["intro"].format(when=when, n=len(picked), d=len(texts)), ""]

    def para(line, rest):
        lines.append(line)
        out.extend([f"{_md(_words(W, line))} {rest}".strip(), ""])

    src = lambda e: f"({_md(e['title'])}{' · ' + _md(e['section']) if e['section'] else ''}, {e['day']}, [{W['there']}]({_there(e)}))"  # noqa: E731
    out += [f"## {W['read']}", ""]
    for pid, t in texts.items():
        para(t["title"], f"{_md(_words(W, t['line'])) if t['line'] else ''} ({W['notes'].format(n=t['n'])}, {_span(t['days'], W)}, [{W['open']}](/p/{pid}))")
    if asked:
        out += [f"## {W['curious']}", ""]
        for e in asked:
            para(e["q"], f"{W['answer'] + _md(_words(W, e['a'])) if e['a'] else ''} {src(e)}")
    if wrote:
        out += [f"## {W['got']}", ""]
        for e in wrote:
            para(e["text"], src(e))
    if marked:
        out += [f"## {W['attend']}", ""]
        for pid, secs in marked.items():
            out += [f"### {_md(texts[pid]['title'])}", ""]
            for s in secs.values():
                quotes = " ".join(f"“{_md(e['quote'])}” ([{W['there']}]({_there(e)}))" for e in s["notes"])
                head = s["title"] or W["whole"]
                para(head, f"{_md(_words(W, s['line'])) + ' ' if s['line'] else ''}{quotes}")
    return W["title"].format(period=period), "\n".join(out), lines, picked


def _topic(line):
    """A line's topic, words of it as they stand: the line itself when short, else its first clause when that is."""
    cjk = ladder._cjk_share(line) > 0.2
    if (len(line) <= 24) if cjk else (len(line.split()) <= 10):
        return line
    head = re.split(r"[，。；：！？、,.;:!?]", line)[0].strip()
    return head if head and ((len(head) <= 14) if cjk else (len(head.split()) <= 5)) else line


def fold_lines(pid, lines, lang, made):
    """A record's levels: each entry folds to its own line (the text's title, the question, the reader's words, the
    section), never to a cut of the sentence a model would have chosen; the first, to when it was made. Its language
    is the reader's, whatever the passages quoted are in."""
    doc = store.parsed(pid)
    doc["meta"]["lang"] = lang if lang in langs.LANGS else store.text_lang(pid)
    cjk, A = ladder.cjk_doc(doc), doc["atoms"]
    units = [uid for c in doc["chunks"] for uid in c["units"]]
    for u in doc["units"].values():
        u["lad"] = ladder.local(u, A, cjk)
    paras = [uid for uid in units if doc["units"][uid]["sents"]]
    fold = lambda uid, line, topic, role: ladder.assemble(doc["units"][uid], {"takeaway": line, "reason": "", "topic": topic, "role": role, "evidence": [0]}, A, "", cjk)  # noqa: E731
    if paras:   # (the first: when it was made, from what)
        u = doc["units"][paras[0]]
        doc["units"][paras[0]]["lad"] = fold(paras[0], plain(u["toks"][u["sents"][0][0]:u["sents"][0][1]], A), made, "context")
    if len(paras) - 1 == len(lines):
        for uid, line in zip(paras[1:], lines):
            doc["units"][uid]["lad"] = fold(uid, line, _topic(line), "claim")
    for c in doc["chunks"]:
        c.setdefault("lad", None)
    store.save_en(doc, "")


def record(items, ui="en", when=None):
    """The reading record of the notes picked ([{paper, note}]) as a document of the library, in the folder of
    records: its id."""
    W = WORDS.get(ui) or WORDS["en"]
    when = when or time.strftime("%Y-%m-%d %H:%M")
    title, md, lines, picked = record_md(items, W, when)
    t, html, meta = local._read_md(md, "record.md")
    meta["label"] = t
    pid = local.make_id(t, md)
    meta["summary"] = {"kind": "record", "made": when, "notes": [{"paper": p, "note": n["id"]} for p, _, n in picked]}
    local.store_doc(pid, html, {"id": pid, **meta}, "source.md", md, lambda folder: local.Images(folder, None).resolve, sizes=True)
    fold_lines(pid, lines, ui, when)
    fs = library.folders()
    f = next((x for x in fs["folders"] if x["name"] == W["folder"] and not x.get("parent")), None)
    library.change({"op": "move", "papers": [pid], "folder": f["id"]} if f else {"op": "new", "name": W["folder"], "papers": [pid]})
    return pid


def _file(pid, title):
    """The name the reader's own Markdown for Obsidian gives a text's notes (reader.js fileName), so [[it]] links there."""
    return re.sub(r'[\\/:*?"<>|]+', " ", f"{pid} {title}")[:90].strip()


def obsidian(items, ui="en", when=None):
    """The reading record as Markdown for Obsidian: (file name, text)."""
    W = WORDS.get(ui) or WORDS["en"]
    when = when or time.strftime("%Y-%m-%d %H:%M")
    picked, texts, asked, wrote, marked = gather(items, W)
    period = _period(picked, W)
    title = W["title"].format(period=period)
    q = lambda s: json.dumps(str(s), ensure_ascii=False)  # noqa: E731
    link = lambda pid: f"[[{_file(pid, texts[pid]['title'])}|{texts[pid]['title']}]]"  # noqa: E731

    def tf(e):
        a = e["note"].get("anchor") or {}
        return f"textfold://open?paper={e['pid']}&n={e['note']['id']}" + (f"&lang={a['lang']}" if a.get("lang") else "")

    def src(e):
        where = f"{e['title']}{' · ' + e['section'] if e['section'] else ''}"
        return f"[[{_file(e['pid'], e['title'])}#^{e['note']['id']}|{where}]] · {e['day']} · [{W['there']}]({tf(e)})"

    out = ["---", f"title: {q(title)}", "type: textfold/reading-record", f"period: {q(period)}", f"made: {q(when)}",
           f"texts: [{', '.join(q('[[' + _file(p, t['title']) + ']]') for p, t in texts.items())}]",
           f"notes: {len(picked)}", "tags: [textfold, reading-record]", "---", "", f"# {title}", "",
           f"## {W['read']}", ""]
    for pid, t in texts.items():
        out.append(f"- {link(pid)} · {W['notes'].format(n=t['n'])} · {_span(t['days'], W)}")
        if t["line"]:
            out.append(f"    - {t['line']}")
    out.append("")
    if asked:
        out += [f"## {W['curious']}", ""]
        for e in asked:
            out += [f"> [!question] {e['q']}"] + ([f"> {e['a']}"] if e["a"] else []) + [f"> {src(e)}", ""]
    if wrote:
        out += [f"## {W['got']}", ""]
        out += [f"- {e['text']} · {src(e)}" for e in wrote] + [""]
    if marked:
        out += [f"## {W['attend']}", ""]
        for pid, secs in marked.items():
            out += [f"### {link(pid)}", ""]
            for s in secs.values():
                out += [f"**{s['title'] or W['whole']}**" + (f" · {s['line']}" if s["line"] else ""), ""]
                for e in s["notes"]:
                    out += [f"> {e['quote']}", f"> [{W['there']}]({tf(e)}) · [[{_file(e['pid'], e['title'])}#^{e['note']['id']}|{e['day']}]]", ""]
    out += ["---", "", f"*{W['made_with']} · {when}*", ""]
    name = re.sub(r'[\\/:*?"<>|]+', " ", title).strip() + ".md"
    return name, "\n".join(out)
