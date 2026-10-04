"""Generate a paper in a language: fetch, parse, the English ladder and links (once), the translation.

Every step reports through `progress(stage, done, total)`; the server turns that into a progress bar.
"""
import urllib.error

from . import ladder, links, llm, models, store, translate
from .fetch import fetch, paper_id


def task(cfg, name):
    """The model spec a task runs with: its reasoning level from the settings (models.for_task)."""
    return models.for_task(llm.spec_of(cfg), name)


def generate(ref, lang, cfg, force=False, jobs=4, progress=lambda *a: None, log=lambda *a: None):
    pid = paper_id(ref)
    progress("fetch", 0, 1)
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
