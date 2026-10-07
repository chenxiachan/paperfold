"""A paper's original typeset pages, for the reader's side-by-side view: arXiv's PDF of the version read, or the
publisher's PDF that PubMed Central keeps in its open data. Fetched once, when the reader first asks, and kept beside
the paper as source.pdf. Wikipedia articles and Markdown files have none."""
import json
import re
import threading
import urllib.error
import urllib.request

from . import store
from .fetch import UA

LIMIT = 100 * 2**20       # no paper's PDF is larger; anything that is, is not one
_lock = threading.Lock()  # two requests for the same paper download it once


def candidates(pid, meta):
    """Where the PDF may be, in order."""
    if re.fullmatch(r"\d{4}\.\d{4,5}", pid):
        yield f"https://arxiv.org/pdf/{pid}{meta.get('version') or ''}"
    elif re.fullmatch(r"pmc\d+", pid):
        n = pid[3:]
        for v in (1, 2, 3):   # the open data's versions of an article
            yield f"https://pmc-oa-opendata.s3.amazonaws.com/PMC{n}.{v}/PMC{n}.{v}.pdf"


def has_source(pid):
    """Whether the paper is of a kind that can have one (the reader shows its button only then)."""
    return bool(re.fullmatch(r"\d{4}\.\d{4,5}|pmc\d+", pid))


def path(pid):
    """The paper's PDF on disk, fetched now if it is not there yet; None if there is none to fetch."""
    d = store.pdir(pid)
    f = d / "source.pdf"
    if f.exists():
        return f
    meta = json.loads((d / "meta.json").read_text())
    with _lock:
        if f.exists():
            return f
        for url in candidates(pid, meta):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                    data = r.read(LIMIT + 1)
            except (urllib.error.URLError, OSError):
                continue
            if data[:5] == b"%PDF-" and len(data) <= LIMIT:
                tmp = f.with_suffix(".part")
                tmp.write_bytes(data)
                tmp.replace(f)
                return f
    return None
