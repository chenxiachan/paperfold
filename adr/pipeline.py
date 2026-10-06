"""Generate a paper in a language: fetch (an arXiv paper), parse, the English ladder and links (once), the translation.

Every step reports through `progress(stage, done, total)`; the server turns that into a progress bar.
"""
import urllib.error

from . import biorxiv, epmc, ladder, links, llm, models, store, translate, wiki
from .fetch import fetch


def task(cfg, name):
    """The model spec a task runs with: its reasoning level from the settings (models.for_task)."""
    return models.for_task(llm.spec_of(cfg), name)


def generate(ref, lang, cfg, force=False, jobs=4, progress=lambda *a: None, log=lambda *a: None):
    pid = store.resolve(ref)
    progress("fetch", 0, 1)
    if store.is_imported(pid):   # stored when it was opened (local.py), or fetched once from Europe PMC (epmc.py)
        if pid.startswith(("pmc", "ppr")):
            epmc.fetch(pid)
        elif pid.startswith(("biorxiv-", "medrxiv-")):
            biorxiv.fetch(pid, progress)
        elif pid.startswith("wiki-"):
            wiki.fetch(pid)
        d = store.pdir(pid)
    else:
        try:
            d = fetch(pid, store.DATA)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError("no-html")  # the app shows its own sentence for this
            raise
    progress("parse", 0, 1)
    doc = store.parsed(pid)
    cache = d / "llm-cache"
    model = llm.label(cfg)
    en = store.read(pid, "en")
    if en is None or (force and lang == "en"):
        ladder.build(doc, task(cfg, "ladder"), cache, jobs=jobs, log=log, progress=lambda a, b: progress("ladder", a, b), force=force)
        progress("links", 0, 1)
        links.build(doc, task(cfg, "links"), cache, log=log, force=force)
        store.save_en(doc, model)
        en = store.read(pid, "en")
    else:
        store.apply_en(doc, en)
    if lang != "en":
        tr = store.read(pid, f"tr-{lang}")
        if force or tr is None or tr.get("base") != en["version"]:
            translate.build(doc, lang, task(cfg, "translate"), cache, jobs=jobs, log=log, progress=lambda a, b: progress("translate", a, b), force=force)
            store.save_tr(doc, lang, en["version"], model)
    progress("done", 1, 1)
    return pid
