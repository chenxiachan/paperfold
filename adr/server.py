"""The local server: python -m adr serve  ->  http://localhost:3017  (ThoughtDAG keeps 3001)

  GET  /                      landing: paste a link, pick a language, the list of papers
  GET  /p/<id>?lang=xx        a paper in the reader
  GET  /api/papers            the papers on disk
  GET  /api/jobs              generation jobs (queued, running, recently finished)
  POST /api/generate          {paper, lang, force}: queue a generation; one runs at a time. paper: an arXiv id or
                              link, a PMC or PPR id, a DOI (Europe PMC, epmc.py), or a stored document's id
  POST /api/import            {name, text}: store a Markdown file as a paper (local.py); its id, to generate
  GET  /api/models            every model this computer can reach: local agents and API providers
  POST /api/models/select     {model, effort}: the model generations use
  POST /api/agents/scan       look for agents again (also done at startup)
  POST /api/providers/probe   {base, api_key | key, preset}: a provider's /models
  POST /api/providers/save    {key?, preset, name, base, api_key?, models}  ·  POST /api/providers/remove {key}
  POST /api/settings          {use_thoughtdag_env}  ·  POST /api/settings/test {model?}: one tiny call
  GET  /api/notes/<id>        the reader's notes on a paper (docs/notes-format.md)
  POST /api/notes/<id>        {op: "put", note} or {op: "delete", id}
  POST /api/ask               {paper, id, question}: the model answers a note's question; the answer is stored in it
  POST /api/papers/delete     {paper}: move a paper to papers/.trash (not while it is being generated)
  GET  /api/bridge             the ChatGPT bridge (127.0.0.1:10531): running and its models, or what starting it needs
  POST /api/bridge/start       start it detached (bridges.py)
  POST /api/openrouter/start   {back}: the OpenRouter consent URL (OAuth PKCE); GET /oauth/openrouter is its return

Loopback only, and POSTs from other origins are refused. Settings and keys live in
~/.paperfold/settings.json (mode 600), never in the project folder, which may be synced or shared.
"""
import json
import queue
import re
import tempfile
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import agents, bridges, build, langs, llm, local, models, notes, pipeline, providers, store

STATIC = {"app.js": "text/javascript", "app.css": "text/css", "reader.js": "text/javascript",
          "reader.css": "text/css", "i18n.js": "text/javascript"}
# fonts and KaTeX, kept here so that no page asks another server for them (web/vendor)
VENDOR_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".woff2": "font/woff2",
                ".txt": "text/plain; charset=utf-8"}


def vendor_file(rel):
    """A file of web/vendor by its path under /static/vendor/, or None: nothing outside it, nothing but those kinds."""
    root = (build.WEB / "vendor").resolve()
    f = (root / rel).resolve()
    return f if rel and root in f.parents and f.is_file() and f.suffix in VENDOR_TYPES else None


def models_payload():
    s = models.load_settings()
    cat, provs = models.catalog(s)
    selected = models.default_model(s, cat)
    return {
        "models": cat, "selected": selected, "selectedName": next((m["name"] for m in cat if m["id"] == selected), selected),
        "efforts": s.get("efforts") or {}, "bridge": bridges.bridge_status(),
        "agents": [{k: a[k] for k in ("runtime", "label", "binary", "path", "version", "runnable", "error")} | {"models": len(a["models"])}
                   for a in agents.STATE["agents"]],
        "scanning": agents.STATE["scanning"], "scannedAt": agents.STATE["scanned_at"],
        "providers": [{"key": p["key"], "name": p["name"], "source": p["source"], "base": p["base"], "protocol": p["protocol"],
                       "preset": p.get("preset"), "models": [m["id"] for m in p["models"]],
                       "hasKey": bool(p["api_key"]) and p["api_key"] not in ("none", "ollama")} for p in provs],
        "presets": providers.PRESETS[:-1] + [models.ANTHROPIC_PRESET, providers.PRESETS[-1]],
        "useThoughtdagEnv": s.get("use_thoughtdag_env", True), "thoughtdagEnv": providers.THOUGHTDAG_ENV.exists(),
    }


class Jobs:
    def __init__(self):
        self.items, self.q = {}, queue.Queue()
        threading.Thread(target=self.work, daemon=True).start()

    def submit(self, ref, lang, force):
        pid = store.resolve(ref)
        for j in self.items.values():  # the same request already waiting or running is that job
            if j["pid"] == pid and j["lang"] == lang and j["status"] in ("queued", "running"):
                return j
        job = {"id": uuid.uuid4().hex[:10], "pid": pid, "lang": lang, "force": bool(force), "status": "queued",
               "stage": "queued", "done": 0, "total": 0, "error": "", "log": [], "created": time.time(), "finished": None}
        self.items[job["id"]] = job
        self.q.put(job["id"])
        return job

    def work(self):
        while True:
            job = self.items[self.q.get()]
            job["status"] = "running"

            def progress(stage, done, total, job=job):
                job.update(stage=stage, done=done, total=total)

            def log(line, job=job):
                job["log"] = (job["log"] + [line])[-40:]

            try:
                spec = models.resolve(None)  # the model chosen in the settings, resolved once per job
                job["model"] = spec["id"]
                pipeline.generate(job["pid"], job["lang"], spec, force=job["force"], progress=progress, log=log)
                job["status"] = "done"
            except Exception as e:  # shown in the app; the traceback stays in the job log
                job.update(status="error", error="no-model" if str(e).startswith("No model is available") else str(e))
                log(traceback.format_exc()[-800:])
            job["finished"] = time.time()
            PAGES.pop(job["pid"], None)

    def list(self):
        now = time.time()
        return [j for j in self.items.values() if j["status"] in ("queued", "running") or now - (j["finished"] or now) < 600]


PAGES = {}  # pid -> (signature of its layers and template, rendered page)


def reader_page(pid):
    layers = store.pdir(pid) / "layers"
    sig = tuple(sorted((f.name, f.stat().st_mtime) for f in layers.glob("*.json"))) if layers.exists() else ()
    sig += ((build.WEB / "template.html").stat().st_mtime,)  # a changed page template re-renders too
    hit = PAGES.get(pid)
    if not hit or hit[0] != sig:
        hit = (sig, build.page(store.assemble(pid), app=True))
        PAGES[pid] = hit
    return hit[1]


def landing_page(jobs):
    s = models.load_settings()
    chosen = models.default_model(s)
    boot = {"papers": store.papers(), "jobs": jobs.list(), "model": models.label(chosen, s) if chosen else "",
            "bridge": bridges.bridge_status(), "langs": [[code, v[1]] for code, v in langs.LANGS.items()]}
    t = (build.WEB / "app.html").read_text()
    return t.replace("{{HEAD}}", build.fonts_head(build.APP_ASSETS)).replace("{{BOOT}}", json.dumps(boot, ensure_ascii=False).replace("</", "<\\/"))


def make_handler(jobs):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
            data = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(data)

        def json(self, obj, code=200):
            self.send(code, json.dumps(obj, ensure_ascii=False))

        def do_GET(self):
            u = urlparse(self.path)
            try:
                if u.path == "/":
                    return self.send(200, landing_page(jobs), "text/html; charset=utf-8")
                if u.path == "/api/bridge":
                    return self.json(bridges.bridge_status(fresh=True))
                if u.path == "/api/openrouter/minted":   # the app, waiting while the system browser authorises
                    return self.json({"minted": bool(bridges.minted())})
                if u.path == "/oauth/openrouter":   # OpenRouter sends the reader back here with a code
                    code = (parse_qs(u.query).get("code") or [""])[0]
                    desktop = bridges.for_desktop()
                    key, err, back = bridges.openrouter_finish(code)
                    back = back if back.startswith("/") else "/"
                    to = f"{back}#or-minted" if key else f"{back}#or-failed={quote(err or '')}"
                    if desktop:   # this tab is the system browser's: the app, waiting for the key, takes it from here
                        page = (f'<!doctype html><meta charset="utf-8"><title>PaperFold</title><body style="font-family:system-ui;'
                                f'display:grid;place-items:center;height:100vh;margin:0;background:#FAF9F7;color:#1f1d1a">'
                                f'<div style="text-align:center;line-height:1.7"><h2>{"✓" if key else "✕"} OpenRouter</h2>'
                                f'<p style="color:#6b6558">{"回到 PaperFold 即可，本页可以关闭。<br>Return to PaperFold; this tab can be closed." if key else (err or "")}</p></div>')
                        return self.send(200, page, "text/html; charset=utf-8")
                    page = (f'<!doctype html><meta charset="utf-8"><title>PaperFold</title><body style="font-family:system-ui;'
                            f'display:grid;place-items:center;height:100vh;margin:0;background:#FAF9F7;color:#1f1d1a">'
                            f'<div style="text-align:center"><h2>{"✓ OpenRouter" if key else "OpenRouter ✕"}</h2></div>'
                            f'<script>location.replace({json.dumps(to)})</script>')
                    return self.send(200, page, "text/html; charset=utf-8")
                m = re.fullmatch(r"/p/([\w.-]+)", u.path)
                if m and store.valid_id(m.group(1)):
                    if not (store.pdir(m.group(1)) / "source.html").exists():
                        self.send_response(302)
                        self.send_header("Location", "/")
                        self.end_headers()
                        return
                    return self.send(200, reader_page(m.group(1)), "text/html; charset=utf-8")
                if u.path.startswith("/static/") and u.path[8:] in STATIC:
                    return self.send(200, (build.WEB / u.path[8:]).read_bytes(), STATIC[u.path[8:]] + "; charset=utf-8")
                if u.path.startswith("/static/vendor/"):
                    f = vendor_file(unquote(u.path[len("/static/vendor/"):]))
                    if f:
                        return self.send(200, f.read_bytes(), VENDOR_TYPES[f.suffix], cache="max-age=86400")
                if u.path == "/api/papers":
                    return self.json(store.papers())
                if u.path == "/api/jobs":
                    return self.json(jobs.list())
                if u.path in ("/api/models", "/api/settings"):
                    return self.json(models_payload())
                m = re.fullmatch(r"/api/notes/([\w.-]+)", u.path)
                if m and store.valid_id(m.group(1)) and (store.pdir(m.group(1)) / "meta.json").exists():
                    return self.json(notes.read(m.group(1)))
                if u.path == "/favicon.ico":
                    return self.send(204, b"", "image/x-icon")
                self.json({"error": "not found"}, 404)
            except Exception as e:
                self.json({"error": str(e)}, 500)

        def do_POST(self):
            u = urlparse(self.path)
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1"):
                return self.json({"error": "forbidden"}, 403)  # another site may not drive this server
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if size > 12_000_000:   # a Markdown file is far smaller; this is a request gone wrong
                    return self.json({"error": "too-large"}, 413)
                body = json.loads(self.rfile.read(size) or b"{}")
                s = models.load_settings()
                if u.path == "/api/generate":
                    lang = body.get("lang") or "en"
                    if lang not in langs.LANGS:
                        return self.json({"error": f"unknown language {lang}"}, 400)
                    try:
                        job = jobs.submit(body.get("paper", ""), lang, body.get("force"))
                    except ValueError as e:   # not a paper's reference, or (a DOI) none Europe PMC can read in full
                        return self.json({"error": str(e) if str(e) in ("no-fulltext", "no-article") else "bad-ref"}, 400)
                    return self.json(job)
                if u.path == "/api/import":
                    text, name = str(body.get("text") or ""), str(body.get("name") or "document.md")[:200]
                    if not text.strip():
                        return self.json({"error": "empty"}, 400)
                    try:
                        pid = local.import_text(text, name)
                    except ValueError:
                        return self.json({"error": "not-markdown"}, 400)
                    return self.json({"paper": pid, "title": json.loads((store.pdir(pid) / "meta.json").read_text())["title"]})
                m = re.fullmatch(r"/api/notes/([\w.-]+)", u.path)
                if m and store.valid_id(m.group(1)) and (store.pdir(m.group(1)) / "meta.json").exists():
                    try:
                        if body.get("op") == "delete":
                            return self.json(notes.delete(m.group(1), str(body.get("id", ""))))
                        return self.json(notes.put(m.group(1), body.get("note")))
                    except ValueError as e:
                        return self.json({"error": str(e)}, 400)
                if u.path == "/api/bridge/start":
                    try:
                        return self.json(bridges.bridge_start())
                    except RuntimeError as e:
                        return self.json({"error": str(e)}, 400)
                if u.path == "/api/openrouter/start":
                    callback = f"http://{self.headers.get('Host') or 'localhost:3017'}/oauth/openrouter"
                    return self.json({"url": bridges.openrouter_start(callback, str(body.get("back") or "/"), bool(body.get("desktop")))})
                if u.path == "/api/papers/delete":
                    pid = str(body.get("paper", ""))
                    if not store.valid_id(pid) or not (store.pdir(pid) / "meta.json").exists():
                        return self.json({"error": "no such paper"}, 404)
                    if any(j["pid"] == pid and j["status"] in ("queued", "running") for j in jobs.list()):
                        return self.json({"error": "busy"}, 409)
                    store.trash(pid)
                    PAGES.pop(pid, None)
                    return self.json(store.papers())
                if u.path == "/api/ask":
                    pid = str(body.get("paper", ""))
                    if not store.valid_id(pid) or not (store.pdir(pid) / "meta.json").exists():
                        return self.json({"error": "no such paper"}, 404)
                    try:
                        return self.json(notes.ask(pid, str(body.get("id", "")), str(body.get("question", "")).strip()[:2000],
                                                   models.for_task(models.resolve(None), "ask"), ui=str(body.get("ui") or "")))
                    except ValueError as e:
                        return self.json({"error": str(e)}, 400)
                    except Exception as e:  # the model failed: the note keeps its question, the reader can ask again
                        return self.json({"error": str(e)[:600]}, 502)
                if u.path == "/api/models/select":
                    s["model"] = body.get("model") or None
                    if "effort" in body and s["model"]:
                        if body["effort"]:
                            s["efforts"][s["model"]] = body["effort"]
                        else:
                            s["efforts"].pop(s["model"], None)
                    models.save_settings(s)
                    return self.json(models_payload())
                if u.path == "/api/agents/scan":
                    agents.scan()
                    return self.json(models_payload())
                if u.path == "/api/providers/probe":
                    key = (bridges.minted() if body.get("minted") else None) or body.get("api_key") or \
                        next((p.get("api_key") for p in s["providers"] if p["key"] == body.get("key")), "")
                    preset = next((p for p in providers.PRESETS + [models.ANTHROPIC_PRESET] if p["id"] == body.get("preset")), None)
                    if preset and preset.get("fixed"):  # MiniMax and Anthropic have no /models a key can list
                        found = [{"id": i} for i in preset["fixed"]]
                    else:
                        try:
                            found = providers.probe(body.get("base", ""), key)
                        except Exception as e:
                            return self.json({"error": str(e)}, 400)
                    for rid in (preset or {}).get("recommend", []):  # recommended ids the probe left out
                        if rid not in {m["id"] for m in found}:
                            found.append({"id": rid, "recommended": True})
                    current = next((p.get("models") for p in s["providers"] if p["key"] == body.get("key")), None)
                    picked = providers.preselect(found, preset, [m["id"] for m in current] if current else None,
                                                 free_first=(preset or {}).get("id") == "openrouter")
                    return self.json({"models": found, "picked": picked, "recommend": (preset or {}).get("recommend", [])})
                if u.path == "/api/providers/save":
                    preset = body.get("preset") or "custom"
                    known = providers.PRESETS + [models.ANTHROPIC_PRESET]
                    name = (body.get("name") or "").strip() or next((p["name"] for p in known if p["id"] == preset), "") or "Custom"
                    key = body.get("key") or re.sub(r"[^a-z0-9]+", "-", f"{preset}-{name}".lower()).strip("-")
                    old = next((p for p in s["providers"] if p["key"] == key), {})
                    row = {"key": key, "preset": preset, "name": name, "base": (body.get("base") or "").strip().rstrip("/"),
                           "api_key": (bridges.take_minted() if body.get("minted") else None) or body.get("api_key") or old.get("api_key", ""),
                           "models": [{"id": i} for i in (body.get("models") or [])][:providers.MAX_MODELS]}
                    if preset == "anthropic":
                        row["protocol"] = "anthropic"
                    s["providers"] = ([p for p in s["providers"] if p["key"] != key] + [row])[-providers.MAX_PROVIDERS:]
                    models.save_settings(s)
                    return self.json(models_payload())
                if u.path == "/api/providers/remove":
                    s["providers"] = [p for p in s["providers"] if p["key"] != body.get("key")]
                    models.save_settings(s)
                    return self.json(models_payload())
                if u.path == "/api/settings":
                    if "use_thoughtdag_env" in body:
                        s["use_thoughtdag_env"] = bool(body["use_thoughtdag_env"])
                    models.save_settings(s)
                    return self.json(models_payload())
                if u.path == "/api/settings/test":
                    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
                    try:
                        spec = models.resolve(body.get("model"))
                        t0 = time.time()
                        with tempfile.TemporaryDirectory() as tmp:
                            rec, _ = llm.call('Return JSON {"ok": true}.', schema, spec, Path(tmp), force=True, timeout=180)
                        return self.json({"ok": bool(rec["out"].get("ok")), "model": spec["id"], "seconds": round(time.time() - t0, 1)})
                    except Exception as e:
                        return self.json({"ok": False, "error": str(e)[:600]})
                self.json({"error": "not found"}, 404)
            except Exception as e:
                self.json({"error": str(e)}, 500)

        def log_message(self, *args):
            pass

    return Handler


def serve(port=3017):
    jobs = Jobs()
    # look for the agents on this computer while the server comes up
    threading.Thread(target=agents.scan, kwargs={"log": print}, daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(jobs))
    print(f"PaperFold on http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
