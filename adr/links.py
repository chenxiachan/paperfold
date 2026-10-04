"""Argument links: which unit is the evidence for, the basis of, a caveat to, or the mechanism behind which.

Cross-references the author wrote ("Figure 2") come from the parser. These are
the links the author left implicit; one model call over the whole paper, seen
as its takeaways, finds them. Every link is kept as an edge from -> to.
"""
from . import llm
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


def build(doc, cfg, cache_dir, log=print, force=False):
    order = [uid for c in doc["chunks"] for uid in c["units"]]
    chunk_of = {uid: c for c in doc["chunks"] for uid in c["units"]}
    fig_label = {b["cap"]: b.get("label") for b in doc["blocks"] if b["k"] == "fig" and b.get("cap")}
    lines = []
    for n, uid in enumerate(order):
        u, c = doc["units"][uid], chunk_of[uid]
        lad = u["lad"]
        where = f"§{c['num']}" if c["num"] else c["title"]
        kind = f", {fig_label[uid]} caption" if uid in fig_label else ""
        lines.append(f"U{n} {where} [{lad['role']}{kind}] {plain(lad['brief'][:lad['tn']], doc['atoms'])}")
    target = max(20, len(order) // 2)
    prompt = f"""Paper: {doc['meta']['title']}

Every unit of the paper (paragraph, list item, or figure or table caption) as a one-line takeaway, in reading order, with its section and role:

{chr(10).join(lines)}

Find the argument links a reader would want to follow: where one unit is the evidence for, the basis of, a caveat to, or the explanation of another unit elsewhere in the paper. Relations, always from -> to:
- supports: from gives evidence (a result, figure, table, proof) for the claim made in to
- builds_on: from uses a method, definition, setup or result introduced in to
- qualifies: from limits, contradicts or adds a caveat to to
- explains: from gives the mechanism or theory behind the finding in to

Rules: link across distance, not neighbours (never two adjacent units of the same section); no vague topical similarity; each claim in the Abstract, Introduction, Discussion and Conclusion should receive the units that give its evidence, where the paper has them; appendix details should point to the main-text result they support; at most {MAX_FROM} links from any one unit; about {target} links in total.

Return JSON {{"links": [{{"from": "U12", "to": "U3", "rel": "supports"}}, ...]}}."""
    rec, cached = llm.call(prompt, SCHEMA, cfg, cache_dir, force)
    pos = {uid: n for n, uid in enumerate(order)}
    have = {(e["f"], e["t"]) for e in doc["edges"]}
    per_from, added = {}, []
    for x in rec["out"].get("links", []):
        try:
            f, t = order[int(str(x["from"]).lstrip("U"))], order[int(str(x["to"]).lstrip("U"))]
        except (ValueError, IndexError, KeyError):
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
    log(f"  {'·' if cached else '✓'} links: {len(added)} argument links, {len(have)} cross-references")
    return 0 if cached else (rec.get("cost") or 0)
