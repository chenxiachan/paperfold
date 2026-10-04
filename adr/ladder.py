"""Each unit's ladder: Full ⊃ Key ⊃ Brief ⊃ Takeaway ⊃ Topic.

Same split as ThoughtDAG's ladder (src/lib/ladder.ts), for the same reason:
a model told to only delete words paraphrases anyway, and pure deletion
leaves the short levels meaningless. So:
  Full      the unit as the author wrote it
  Key       1 to 3 of its sentences, VERBATIM, chosen by the model as evidence
  Brief     takeaway + one sentence of reason, WRITTEN
  Takeaway  a headline sentence, WRITTEN (Brief starts with it)
  Topic     a noun phrase, cut from inside the takeaway when the model's
            phrase is there verbatim, else the model's phrase as written
Written words that also occur in the key sentences carry `m`, the index of
that source token, so the morph can slide the word instead of swapping it.
One model call per chunk (a heading and the units under it).
"""
import re
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .tokens import lcs_pairs, norm, plain, tokenize_text, words

ROLES = ["context", "gap", "claim", "method", "setup", "result", "analysis", "limitation"]
BUDGET = {"takeaway": 14, "reason": 22, "topic": 3, "section": 16}

SCHEMA = {
    "type": "object",
    "properties": {
        "section": {"type": "object", "properties": {"takeaway": {"type": "string"}, "topic": {"type": "string"}},
                    "required": ["takeaway", "topic"]},
        "units": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "role": {"type": "string", "enum": ROLES},
            "takeaway": {"type": "string"}, "topic": {"type": "string"}, "reason": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "integer"}}},
            "required": ["id", "role", "takeaway", "topic", "reason", "evidence"]}},
    },
    "required": ["section", "units"],
}

KIND = {"para": "paragraph", "item": "list item", "abstract": "abstract", "caption": "caption"}


def outline(doc, here):
    rows = []
    for c in doc["chunks"]:
        pad = "  " * max(0, c["level"] - 2)
        rows.append(f"{pad}{'▶ ' if c['id'] == here else ''}{(c['num'] + ' ') if c['num'] else ''}{c['title']}")
    return "\n".join(rows)


def prompt_for(doc, chunk):
    U, A = doc["units"], doc["atoms"]
    abstract = " ".join(plain(U[u]["toks"], A) for u in doc["chunks"][0]["units"]) if doc["chunks"] and doc["chunks"][0]["id"] == "abstract" else ""
    blocks = []
    for n, uid in enumerate(chunk["units"]):
        u = U[uid]
        kind = KIND.get(u["role"], "paragraph")
        if u["role"] == "caption":
            fig = next((b for b in doc["blocks"] if b.get("cap") == uid), {})
            kind = f"caption of {fig.get('label') or fig.get('kind', 'figure')}"
        if u.get("env"):
            kind = f"{kind} inside {u['env']['title']}"
        lines = [f"[U{n}] {kind}"] + [f"  {i}: {plain(u['toks'][s:e], A)}" for i, (s, e) in enumerate(u["sents"])]
        blocks.append("\n".join(lines))
    head = f"{chunk['num']} {chunk['title']}".strip()
    return f"""Paper: {doc['meta']['title']}

Paper abstract, for context:
{abstract}

Outline (▶ marks this section):
{outline(doc, chunk['id'])}

This section: {head}

Its units in reading order. A unit is a paragraph, a list item, or a figure or table caption; each unit's sentences are numbered from 0.

{chr(10).join(blocks)}

A reader zooms out of this paper level by level: full text, then key sentences, then brief, then takeaway, then topic. Write the short levels for every unit, and one takeaway for the whole section.

For each unit:
- role: the unit's job in the paper's argument, one of: context (background, prior work), gap (what prior work lacks or gets wrong), claim (a thesis or hypothesis the paper puts forward), method (what the authors built or how it works), setup (data, parameters, protocol), result (a measured finding), analysis (an interpretation, mechanism or theory), limitation (a caveat or future work).
- takeaway: ONE English sentence of at most {BUDGET['takeaway']} words stating what this unit establishes: the claim, design choice, number or finding itself, conclusion first, packed like a headline. Name the thing itself, not the activity ("this paragraph describes", "the authors discuss", "details of"). Keep the paper's own terms. Someone reading only the takeaways of the whole paper in order should be able to follow its argument.
- topic: the unit's subject as a bare noun phrase of at most {BUDGET['topic']} words, copied VERBATIM from inside the takeaway.
- reason: ONE more English sentence of at most {BUDGET['reason']} words that reads on from the takeaway and gives its main reason, mechanism, condition or consequence; do not restate the takeaway. Use "" when the unit is a single short sentence.
- evidence: the numbers of the 1 or 2 sentences (3 only when the unit has 7 or more) whose verbatim text best backs the takeaway, ascending; prefer sentences that state a result, a definition or a decision over sentences that only set up or list.

For the section: takeaway, ONE sentence of at most {BUDGET['section']} words stating what this section establishes in the paper; topic, at most {BUDGET['topic']} words copied verbatim from that takeaway.

Style: no em or en dashes as punctuation, use commas or colons (hyphenated terms such as "zero-shot" are fine). Units show math as $...$; when a symbol is essential to a takeaway or reason, copy its $...$ exactly as it appears in the unit, otherwise avoid math. No citations; no figure or table numbers except in a caption's own lines.

Return JSON: {{"section": {{"takeaway": "...", "topic": "..."}}, "units": [{{"id": "U0", "role": "...", "takeaway": "...", "topic": "...", "reason": "...", "evidence": [0]}}, ...]}} with exactly one entry per unit, in order."""


def clean(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    s = re.sub(r"\s*——\s*", "，", s)
    s = re.sub(r"\s*[—–]\s*|\s+-\s+", ", ", s)
    return re.sub(r"[\s.;,!?:。；，！？：、]+$", "", s)


MARK = re.compile(r"⟦(a\d+)[^⟧]*⟧|\$([^$]+)\$")


def written(text, u, atoms, ev, toks=None, sents=None):
    """A written line as tokens. A marker ⟦a12⟧ is that atom; $...$ that matches one of the unit's own formulas
    becomes that atom too (the formula then slides between levels), anything else is rendered with KaTeX."""
    toks, sents = (u["toks"], u["sents"]) if toks is None else (toks, sents)
    out = []
    key_atoms = [tk["a"] for s in ev if s < len(sents) for tk in toks[sents[s][0]:sents[s][1]] if "a" in tk]
    all_atoms = key_atoms + [tk["a"] for tk in toks if "a" in tk]
    squash = lambda x: re.sub(r"\s+", "", x)  # noqa: E731
    pos = 0
    for m in MARK.finditer(text):
        tokenize_text(text[pos:m.start()], None, out)
        if m.group(1):
            if m.group(1) in atoms:
                out.append({"a": m.group(1)})
        else:
            hit = next((a for a in all_atoms if atoms[a].get("kind") == "math" and squash(atoms[a].get("alt", "")) == squash(m.group(2))), None)
            out.append({"a": hit} if hit else {"x": m.group(2)})
        pos = m.end()
    tokenize_text(text[pos:], None, out)
    return out


def locate(topic, take):
    """The topic as a run of the takeaway's tokens: indices, or [] when it is not in there verbatim."""
    squash = lambda tk: re.sub(r"\W", "", (tk.get("t") or "").lower())  # noqa: E731
    want = re.sub(r"\W", "", topic.lower())
    if not want:
        return []
    for i in range(len(take)):
        if not squash(take[i]) or not want.startswith(squash(take[i])):
            continue
        acc = ""
        for j in range(i, len(take)):
            acc += squash(take[j])
            if acc == want:
                return list(range(i, j + 1))
            if not want.startswith(acc):
                break
    return []


def is_word(tk):
    return "a" in tk or "x" in tk or bool(re.search(r"\w", tk.get("t", "")))


def head_words(toks, n):
    """Indices of the first n words (punctuation between them included, none at the end)."""
    idx, w = [], 0
    for i, tk in enumerate(toks):
        if is_word(tk) and w == n:
            break
        idx.append(i)
        w += is_word(tk)
    while idx and not is_word(toks[idx[-1]]):
        idx.pop()
    return idx


def assemble(u, o, atoms, model):
    ns = len(u["sents"])
    ev = sorted({int(x) for x in (o.get("evidence") or []) if isinstance(x, int) and 0 <= x < ns})[:3] or [0]
    take_text, reason_text = clean(o.get("takeaway")), clean(o.get("reason"))
    if not take_text:
        return local(u, atoms)
    take = written(take_text, u, atoms, ev)
    brief = [dict(tk) for tk in take]
    if reason_text:
        brief.append({"t": ".", "s": 1})
        brief += written(reason_text, u, atoms, ev)
    brief.append({"t": "."})
    if take:
        take[-1].pop("s", None)
    tn = len(take)
    align(u, brief, ev, atoms)
    topic = topic_tokens(clean(o.get("topic")), brief, tn, u, atoms, ev)
    return {"role": o.get("role") if o.get("role") in ROLES else "context", "ev": ev, "brief": brief, "tn": tn,
            "topic": topic, "model": model}


def align(u, brief, ev, atoms, toks=None, sents=None):
    toks, sents = (u["toks"], u["sents"]) if toks is None else (toks, sents)
    key = [i for s in ev if s < len(sents) for i in range(*sents[s])]
    for bi, kj in lcs_pairs([norm(tk, atoms) for tk in brief], [norm(toks[i], atoms) for i in key]):
        brief[bi]["m"] = key[kj]


def local(u, atoms):
    """No model reply: the first sentence stands in for brief, its head for the shorter levels."""
    s, e = u["sents"][0]
    brief = [dict(tk, m=s + k) for k, tk in enumerate(u["toks"][s:e])]
    head = head_words(brief, BUDGET["takeaway"])
    tn = (head[-1] + 1) if head else len(brief)
    topic = [{**{x: brief[i][x] for x in ("t", "a", "x", "s", "f") if x in brief[i]}, "k": i} for i in head_words(brief[:tn], 3)]
    return {"role": "context", "ev": [0], "brief": brief, "tn": tn, "topic": topic, "model": "local"}


def topic_tokens(text, brief, tn, u, atoms, ev, budget=None, toks=None, sents=None):
    """Topic tokens; `k` is the takeaway token a topic word slides from. A phrase the model wrote that is not in the
    takeaway verbatim is kept when short (ThoughtDAG does the same): it read better than a cut of the takeaway's head."""
    budget = budget or BUDGET["topic"]
    loc = locate(text, brief[:tn])
    if loc:
        return [{**{x: brief[i][x] for x in ("t", "a", "x", "s", "f") if x in brief[i]}, "k": i} for i in loc]
    if text and sum(map(is_word, tokenize_text(text))) <= budget + 2:
        own = written(text, u, atoms, ev, toks, sents)
        for ti, bi in lcs_pairs([norm(tk, atoms) for tk in own], [norm(tk, atoms) for tk in brief[:tn]]):
            own[ti]["k"] = bi
        if own:
            own[-1].pop("s", None)
        return own
    return [{**{x: brief[i][x] for x in ("t", "a", "x", "s", "f") if x in brief[i]}, "k": i} for i in head_words(brief[:tn], budget)]


def section_ladder(o, topic_budget=3, doc=None, chunk=None):
    take_text = clean((o or {}).get("takeaway"))
    if not take_text:
        return None
    if doc and chunk:  # $...$ in a section line becomes one of the section's own formulas
        pool = [{"a": tk["a"]} for uid in chunk["units"] for tk in doc["units"][uid]["toks"] if "a" in tk]
        take = written(take_text, {"toks": pool, "sents": []}, doc["atoms"], [])
    else:
        take = tokenize_text(take_text)
    return {"take": take, "topic": locate(clean(o.get("topic")), take) or head_words(take, topic_budget)}


def build(doc, cfg, cache_dir, jobs=4, log=print, progress=None, force=False):
    chunks = [c for c in doc["chunks"] if c["units"]]
    cost, warnings, errors = 0.0, [], []
    model = llm.label(cfg)

    def run(c):
        try:
            return c, llm.call(prompt_for(doc, c), SCHEMA, cfg, cache_dir, force), None
        except Exception as e:  # one failed chunk falls back to local ladders, the rest still build
            return c, None, e

    if progress:
        progress(0, len(chunks))
    with ThreadPoolExecutor(jobs) as ex:
        for n_done, (c, res, err) in enumerate(ex.map(run, chunks), 1):
            if progress:
                progress(n_done, len(chunks))
            if err:
                errors.append(err)
                log(f"  ! {c['id']}: {err}")
                continue
            rec, cached = res
            cost += 0 if cached else (rec.get("cost") or 0)
            out = rec["out"]
            by_id = {x.get("id"): x for x in out.get("units", [])}
            for n, uid in enumerate(c["units"]):
                o = by_id.get(f"U{n}")
                u = doc["units"][uid]
                u["lad"] = assemble(u, o, doc["atoms"], model) if o else local(u, doc["atoms"])
                if not o:
                    warnings.append(f"{uid}: missing from reply")
                elif words(u["lad"]["brief"][:u["lad"]["tn"]]) > BUDGET["takeaway"] + 4:
                    warnings.append(f"{uid}: long takeaway ({words(u['lad']['brief'][:u['lad']['tn']])} words)")
            c["lad"] = section_ladder(out.get("section"), 3, doc, c)
            log(f"  {'·' if cached else '✓'} {c['id']:<14} {len(c['units']):>2} units")
    if chunks and len(errors) == len(chunks):  # nothing came back: a backend problem, not a paper problem
        raise RuntimeError(str(errors[0]))
    for u in doc["units"].values():
        u.setdefault("lad", local(u, doc["atoms"]))
    for w in warnings:
        log(f"  ~ {w}")
    return cost
