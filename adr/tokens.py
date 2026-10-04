"""Tokens, sentences and the word alignment the morph relies on.

A unit's text is a stream of tokens: words and punctuation carry their own
text, inline objects (math, citations, cross-references) are atoms that
stay whole. Every token remembers whether whitespace followed it in the
source, so a verbatim level renders exactly as the author wrote it.
"""
import re

# a token: {"t": text} or {"a": atom id}; optional "s": 1 (space after), "f": font classes
# a CJK character (Han or kana) is a token of its own (the morph slides characters, as ThoughtDAG's Chinese plaques do)
CJK = "\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f"  # kana too: Japanese is not spaced
WORD = re.compile(rf"[{CJK}]|\d+(?:[.,]\d+)+%?|[^\W_{CJK}]+(?:['’\-][^\W_{CJK}]+)*|\S", re.U)
ABBREV = {
    "e", "g", "i", "al", "etc", "vs", "cf", "fig", "figs", "eq", "eqs", "sec", "secs", "tab",
    "ref", "refs", "no", "approx", "resp", "ca", "viz", "dr", "mr", "ms", "prof", "st", "jr",
    "inc", "ltd", "co", "appx", "app", "thm", "def", "lem", "prop", "cor", "ch",
}
STOP = {
    "the", "a", "an", "of", "to", "in", "is", "are", "was", "were", "be", "been", "and", "or",
    "that", "this", "these", "those", "it", "its", "for", "on", "with", "as", "by", "at", "from",
    "we", "our", "their", "they", "which", "while", "than", "then", "into", "can", "not", "but",
    "such", "also", "has", "have", "had", "does", "do", "more", "most", "less", "only", "both",
    "的", "了", "是", "在", "和", "与", "或", "这", "那", "就", "也", "都", "而", "及", "其", "之", "对", "中", "为",
}


def is_cjk(s):
    return bool(re.search(f"[{CJK}]", s or ""))


def tokenize_text(text, font=None, out=None):
    """Append the tokens of a plain string to out; whitespace marks the previous token."""
    out = [] if out is None else out
    for m in re.finditer(r"\s+|" + WORD.pattern, text):
        piece = m.group(0)
        if piece.isspace():
            if out:
                out[-1]["s"] = 1
            continue
        tok = {"t": piece}
        if font:
            tok["f"] = font
        out.append(tok)
    return out


def split_sentences(toks):
    """Sentence ranges [start, end) over a token list."""
    bounds, start, n = [], 0, len(toks)
    for i, tk in enumerate(toks):
        t = tk.get("t")
        if t not in (".", "?", "!") or i + 1 >= n:
            continue
        end = i
        # a closing bracket or quote glued to the stop belongs to this sentence
        if not tk.get("s") and toks[i + 1].get("t") in (")", "]", "”", '"', "’") and toks[i + 1].get("s"):
            end = i + 1
        elif not tk.get("s"):
            continue
        if end + 1 >= n:
            continue
        prev = (toks[i - 1].get("t") or "") if i > 0 else ""
        if t == "." and (prev.lower() in ABBREV or re.fullmatch(r"[A-Z]", prev)):
            continue
        nxt = toks[end + 1]
        head = nxt.get("t") or ""
        if "a" in nxt or re.match(r"[A-Z0-9(\[“\"‘]", head):
            bounds.append((start, end + 1))
            start = end + 1
    if start < n:
        bounds.append((start, n))
    return bounds


def norm(tok, atoms):
    """What two tokens must share to count as the same word in the morph; '' never matches."""
    if "a" in tok:
        return "atom:" + re.sub(r"\s+", "", atoms.get(tok["a"], {}).get("alt", tok["a"]))
    if "x" in tok:
        return "atom:" + re.sub(r"\s+", "", tok["x"])
    w = re.sub(r"[^\w]", "", (tok.get("t") or "").lower())
    if not w or w in STOP:
        return ""
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def lcs_pairs(a, b):
    """Longest common subsequence of two lists of normalised words, as index pairs; '' never matches."""
    n, m = len(a), len(b)
    if not n or not m:
        return []
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] and a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        if a[i] and a[i] == b[j]:
            out.append((i, j))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def plain(toks, atoms, math_dollars=True):
    """A token run as text for the model: math as $latex$, other atoms as their visible text."""
    s = ""
    for k, tk in enumerate(toks):
        if "a" in tk:
            at = atoms.get(tk["a"], {})
            piece = f"${at.get('alt', '')}$" if at.get("kind") == "math" and math_dollars else at.get("text", "")
        elif "x" in tk:
            piece = f"${tk['x']}$"
        else:
            piece = tk["t"]
        s += piece
        if tk.get("s") and k + 1 < len(toks):
            s += " "
    return s.strip()


def words(toks):
    return sum(1 for tk in toks if "t" in tk and re.search(r"\w", tk["t"]))
