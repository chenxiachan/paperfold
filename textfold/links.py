"""Argument links: which unit is the evidence for, the basis of, a caveat to, or the mechanism behind which.

Cross-references the author wrote ("Figure 2") come from the parser. These are
the links the author left implicit; a model call over the whole paper, seen
as its takeaways, finds them. Every link is kept as an edge from -> to.

A paper too long for one call is asked in parts (#91: 2,290 units in one prompt,
a reply of some thousand links, cut off mid-answer after 900 seconds): a part
holds MAX_UNITS units, and every part is shown the abstract as well, as the
claims its units may be the evidence for, so that evidence far from the claim it
belongs to still reaches it. The parts are asked in parallel, their replies
merged in reading order, a link once, at most MAX_FROM from any one unit. A text
that fits one call is asked as it always was: its prompt, and the reply cached
for it, stay.
"""
from concurrent.futures import ThreadPoolExecutor

from . import kinds, llm
from .tokens import plain

RELS = ["supports", "builds_on", "qualifies", "explains"]
SCHEMA = {
    "type": "object",
    "properties": {"links": {"type": "array", "items": {"type": "object", "properties": {
        "from": {"type": "string"}, "to": {"type": "string"}, "rel": {"type": "string", "enum": RELS}},
        "required": ["from", "to", "rel"]}}},
    "required": ["links"],
}
MAX_FROM = 3
# A part of the links call: a line a unit is about 70 characters, so 400 of them ask for the few hundred links a reply
# a model finishes, where a whole book's units in one prompt ask for some thousand and come back cut off.
MAX_UNITS = 400
ABSTRACT_UNITS = 24   # the opening's units shown with every part: the claims the evidence is for, not the whole opening


def _line(doc, uid, c, n, fig_label):
    """A unit as the model reads it here: where it is, what it does in the argument, and what it says."""
    lad, atoms = doc["units"][uid]["lad"], doc["atoms"]
    where = f"§{c['num']}" if c["num"] else c["title"]
    kind = f", {fig_label[uid]} caption" if uid in fig_label else ""
    return f"U{n} {where} [{lad['role']}{kind}] {plain(lad['brief'][:lad['tn']], atoms)}"


def parts(units):
    """The units of the links call in as few runs as hold MAX_UNITS each, of about equal length."""
    n = max(1, -(-units // MAX_UNITS))
    size = -(-units // n) if units else 0
    return [list(range(i, min(i + size, units))) for i in range(0, units, size)] if size else [[]]


def prompt_for(doc, lines, part=None, abstract=(), total=0, target=20):
    """The links call's prompt. part: the units this call is asked about, of a text too long for one call; None: every
    unit of it, in the one call it has always been."""
    if part is None:
        scope = ("Every unit of the paper (paragraph, list item, or figure or table caption) as a one-line takeaway, "
                 "in reading order, with its section and role:")
        body, opening = "\n".join(lines[n] for n in range(total)), ""
    else:
        scope = (f"This part of the paper, units U{part[0]} to U{part[-1]} of {total} (a paragraph, list item, or "
                 "figure or table caption each) as a one-line takeaway, in reading order, with its section and role:")
        body = "\n".join(lines[n] for n in part)
        # (the opening as the claims this part's units may be the evidence for; the part that holds it has it already)
        opening = ("\n\nThe abstract is given too, as the claims these units may be the evidence for:\n\n"
                   + "\n".join(lines[n] for n in abstract)) if abstract and part[0] > abstract[0] else ""
    return kinds.adapt(f"""Paper: {doc['meta']['title']}

{scope}

{body}{opening}

Find the argument links a reader would want to follow: where one unit is the evidence for, the basis of, a caveat to, or the explanation of another unit elsewhere in the paper. Relations, always from -> to:
- supports: from gives evidence (a result, figure, table, proof) for the claim made in to
- builds_on: from uses a method, definition, setup or result introduced in to
- qualifies: from limits, contradicts or adds a caveat to to
- explains: from gives the mechanism or theory behind the finding in to

Rules: link across distance, not neighbours (never two adjacent units of the same section); no vague topical similarity; each claim in the Abstract, Introduction, Discussion and Conclusion should receive the units that give its evidence, where the paper has them; appendix details should point to the main-text result they support; at most {MAX_FROM} links from any one unit; about {target} links in total.

Return JSON {{"links": [{{"from": "U12", "to": "U3", "rel": "supports"}}, ...]}}.""", doc["meta"])


def build(doc, cfg, cache_dir, log=print, force=False, jobs=4):
    order = [uid for c in doc["chunks"] for uid in c["units"]]
    chunk_of = {uid: c for c in doc["chunks"] for uid in c["units"]}
    fig_label = {b["cap"]: b.get("label") for b in doc["blocks"] if b["k"] == "fig" and b.get("cap")}
    pos = {uid: n for n, uid in enumerate(order)}
    lines = [_line(doc, uid, chunk_of[uid], n, fig_label) for n, uid in enumerate(order)]
    runs = parts(len(order))
    abstract = ([pos[uid] for uid in doc["chunks"][0]["units"][:ABSTRACT_UNITS]]
                if doc["chunks"] and doc["chunks"][0]["id"] == "abstract" else [])
    target = max(20, len(order) // 2)   # (the whole text's: a part of it asks for its share)
    asks = [None] if len(runs) == 1 else runs

    def run(part):
        n = len(order) if part is None else len(part)
        prompt = prompt_for(doc, lines, part, abstract, len(order),
                            target if part is None else max(8, target * n // max(1, len(order))))
        try:
            return llm.call(prompt, SCHEMA, cfg, cache_dir, force, system=llm.system_for(doc["meta"])), None
        except Exception as e:   # one part failed: the links it would have given are missing, the others' are kept
            return None, e

    got, errors = {}, []
    with ThreadPoolExecutor(jobs) as ex:   # (a book's parts asked together; a paper's one call, as it was)
        for i, (res, err) in llm.as_answered(ex, lambda it: (it[0], run(it[1])), list(enumerate(asks)), log, llm.label(cfg)):
            if err:
                errors.append(err)
                log(f"  ! links{f' part {i + 1} of {len(asks)}' if len(asks) > 1 else ''}: {err}")
                continue
            got[i] = res
    if len(errors) == len(asks):   # nothing came back: a backend problem, not a paper's, and the caller keeps the levels
        raise errors[0]
    recs = [got[i] for i in range(len(asks)) if i in got]   # (in reading order, whatever came back first)
    have = {(e["f"], e["t"]) for e in doc["edges"]}
    per_from, added = {}, []
    for i in (i for i in range(len(asks)) if i in got):
        shown = None if asks[i] is None else set(asks[i]) | set(abstract)   # a part names only the units it was shown
        for x in got[i][0]["out"].get("links", []):
            try:
                a, b = int(str(x["from"]).lstrip("U")), int(str(x["to"]).lstrip("U"))
                f, t = order[a], order[b]
            except (ValueError, IndexError, KeyError, TypeError):
                continue
            if min(a, b) < 0 or shown is not None and not (a in shown and b in shown):
                continue
            if f == t or x.get("rel") not in RELS or (f, t) in {(e["f"], e["t"]) for e in added}:
                continue
            if chunk_of[f] is chunk_of[t] and abs(pos[f] - pos[t]) == 1:
                continue
            if per_from.get(f, 0) >= MAX_FROM:
                continue
            per_from[f] = per_from.get(f, 0) + 1
            added.append({"f": f, "t": t, "tk": "unit", "rel": x["rel"]})
    # an argument link says more than the bare cross-reference between the same two units
    doc["edges"] = [e for e in doc["edges"] if (e["f"], e["t"]) not in {(a["f"], a["t"]) for a in added}] + added
    log(f"  {'·' if all(c for _, c in recs) else '✓'} links: {len(added)} argument links"
        f"{f' in {len(asks)} parts' if len(asks) > 1 else ''}, {len(have)} cross-references")
    return sum(0 if cached else (rec.get("cost") or 0) for rec, cached in recs)
