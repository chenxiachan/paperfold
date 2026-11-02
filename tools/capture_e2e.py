"""The browser's button end to end (extension/, textfold/capture.py): the extension loaded in Playwright's Chromium, pages
served here; before TextFold's native host is registered, the page that says what to do (setup.html), opened once the
extension is installed and again by a click; then the host registered in that browser's own profile, as the app
registers it, the page saying it answers, six pages sent and read (a publisher's article by the reading views of
reader.js), and the levels of one asked of a TextFold standing in as running. Nothing here touches the reader's own
browser, settings or library.

    python3 tools/capture_e2e.py <repo> <a scratch folder>     (playwright installed)
"""
import base64, json, os, shutil, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO, WORK = Path(sys.argv[1]), Path(sys.argv[2])
WORDS = ("The river office kept the gauges for a century, and its records show how the spring floods rose and fell "
         "with the snow on the hills, year after year, in the same slow rhythm the town still lives by. ")
ARTICLE_FULL = "".join(f"<p>Paragraph {k}. {WORDS}</p>" for k in range(1, 7))
PAGES = {
    "/article": lambda cookie: ("<html><head><title>Rivers, for subscribers</title>"
        '<meta property="og:type" content="article"></head><body><nav>Home World</nav><article><h1>Rivers</h1>'
        + (ARTICLE_FULL if "session=reader" in cookie else f"<p>Paragraph 1. {WORDS}</p><div class=paywall>Subscribe to continue reading.</div>")
        + "</article></body></html>"),
    "/drawn": lambda c: ("<html><head><title>Drawn by its script</title></head><body><main id=m></main><script>"
        f"document.getElementById('m').innerHTML = {json.dumps(ARTICLE_FULL)};</script></body></html>"),
    "/shadow": lambda c: ("<html><head><title>In shadow roots</title></head><body><article><h1>Shadows</h1>"
        f"<p>Paragraph 0. {WORDS}</p><open-box></open-box><closed-box></closed-box>"
        '<p>A gauge is read every hour<span class="mark">*</span><span style="display:none">Since the telemetry of 2019.</span>, and the town listens.</p>'
        "</article><script>"
        "customElements.define('open-box', class extends HTMLElement { constructor() { super(); this.attachShadow({mode: 'open'}).innerHTML = "
        f"{json.dumps('<p>Open shadow. ' + WORDS + '</p>')}; }} }});"
        "customElements.define('closed-box', class extends HTMLElement { constructor() { super(); this.attachShadow({mode: 'closed'}).innerHTML = "
        f"{json.dumps('<p>Closed shadow. ' + WORDS + '</p>')}; }} }});"
        "</script></body></html>"),
    "/framed": lambda c: ("<html><head><title>In a frame</title></head><body><article><h1>Framed</h1>"
        f"<p>Paragraph 0. {WORDS}</p><iframe src='/inner' width=600 height=400></iframe></article></body></html>"),
    "/inner": lambda c: f"<html><body><p>Inside the frame. {WORDS}</p><p>The frame again. {WORDS}</p></body></html>",
    # a publisher's article as Elsevier draws one: its abstract called "abstract author", its citations links called
    # "anchor", its figures holding their download links before their captions, its references a list of its own
    "/press": lambda c: ("<html><head><title>Rivers | Example Press</title></head><body><header><nav>Journals Books</nav></header>"
        "<main><div class=publisher><h2>Published by: Example Press</h2></div><h1>Rivers</h1>"
        "<div class=buttons><a href=/pdf>View PDF</a></div>"
        f"<div class='abstract author'><h2>Abstract</h2><div class='abstract author'><p>Abstract. {WORDS}</p></div></div>"
        f"<section><h2>1. Introduction</h2><p>Paragraph 1. {WORDS} As the gauges show "
        "<a class='anchor anchor-primary' href='#b0010'><span class='anchor-text'>[2]</span></a>.</p>"
        "<figure id=f1><span><img src=/fig1.png height=40><ol><li><a class='anchor download-link' href=/fig1.png download>"
        "<span class='anchor-text'>Download: Download high-res image (12KB)</span></a></li></ol></span>"
        "<span class=captions><p><span class=label>Fig. 1</span>. The gauges at the river office.</p></span></figure>"
        f"<p>Paragraph 2. {WORDS}</p><p>Paragraph 3. {WORDS}</p></section>"
        "<section><h2>References</h2><ol class=references><li id=ref-b0010>Gauge, A. (2020). Spring floods.</li></ol></section>"
        "</main><footer>About Example Press</footer></body></html>"),
    # formulas MathJax 4 drew, with no MathML left in the page: their sources asked of its startup.document.math (a
    # stand-in here: TeX inline, Elsevier's MathML with its mml: prefix on display)
    "/mathjax": lambda c: ("<html><head><title>Gauges by formula</title></head><body><article><h1>Gauges by formula</h1>"
        f"<p>Paragraph 1. {WORDS}</p><p>With <mjx-container class=MathJax jax=CHTML><mjx-math aria-hidden=true><mjx-msub>"
        "<mjx-mi><mjx-c>𝑦</mjx-c></mjx-mi><mjx-script><mjx-mi><mjx-c>𝑖</mjx-c></mjx-mi></mjx-script></mjx-msub></mjx-math>"
        "</mjx-container> the reading of each gauge, the mean is</p><mjx-container class=MathJax jax=CHTML display=true>"
        f"<mjx-math aria-hidden=true><mjx-mi><mjx-c>𝑚</mjx-c></mjx-mi></mjx-math></mjx-container><p>Paragraph 2. {WORDS}</p>"
        "</article><script>const drawn = document.querySelectorAll('mjx-container'); window.MathJax = {startup: {document: {math: ["
        "{typesetRoot: drawn[0], math: 'y_i', display: false, inputJax: {name: 'TeX'}},"
        "{typesetRoot: drawn[1], math: '<mml:math xmlns:mml=\"http://www.w3.org/1998/Math/MathML\"><mml:mi>m</mml:mi><mml:mo>=</mml:mo>"
        "<mml:mfrac><mml:mn>1</mml:mn><mml:mi>n</mml:mi></mml:mfrac></mml:math>', display: true, inputJax: {name: 'MathML'}}]}}};"
        "</script></body></html>"),
}
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
asked = []   # (what the TextFold standing in as running was asked)

class Pages(BaseHTTPRequestHandler):
    def do_POST(self):
        asked.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
        body = b'{"id": "job-e2e"}'
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/fig1.png":
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", str(len(PNG)))
            self.end_headers(); self.wfile.write(PNG); return
        page = PAGES.get(self.path.split("?")[0])
        body = (page(self.headers.get("Cookie") or "") if page else "no").encode()
        self.send_response(200 if page else 404); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

srv = ThreadingHTTPServer(("127.0.0.1", 0), Pages); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
ext = WORK / "ext"; shutil.rmtree(ext, ignore_errors=True); shutil.copytree(REPO / "extension", ext)
m = json.loads((ext / "manifest.json").read_text()); m["host_permissions"] = ["http://127.0.0.1/*"]   # (a test's stand-in for the click)
(ext / "manifest.json").write_text(json.dumps(m))
home, data, prof = WORK / "home", WORK / "data", WORK / "profile"
for p in (home, data, prof): shutil.rmtree(p, ignore_errors=True); p.mkdir(parents=True)
os.environ.update(TEXTFOLD_DATA=str(data), PYTHONPATH=str(REPO), HOME=str(home))   # (the host's settings: these)
sys.path.insert(0, str(REPO))
from textfold import capture

def send(ctx, sw, path):
    pg = ctx.new_page(); pg.goto(base + path); pg.wait_for_timeout(600); pg.bring_to_front()
    reply = sw.evaluate("async () => { const [tab] = await chrome.tabs.query({active: true, lastFocusedWindow: true}); return await self.capture(tab); }")
    return pg, reply

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(prof), channel="chromium", headless=True,
                                               args=[f"--disable-extensions-except={ext}", f"--load-extension={ext}"])
    sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
    ext_id = sw.url.split("/")[2]
    print("extension:", ext_id)
    for _ in range(40):   # (installed, no TextFold yet: the page that says what to do opens by itself)
        if any("setup.html" in x.url for x in ctx.pages): break
        sw.evaluate("() => new Promise((r) => setTimeout(r, 250))")   # (a wait in which Playwright hears of new pages)
    print("installed, no TextFold ->", [x.url.split("/")[-1] for x in ctx.pages if "setup.html" in x.url])
    pg, reply = send(ctx, sw, "/article?before=install")
    pg.wait_for_timeout(400)
    print("clicked, no TextFold ->", reply, "| tabs:", [x.url.split("/")[-1] for x in ctx.pages if "setup.html" in x.url])
    setup = ctx.pages[-1]; setup.wait_for_timeout(600)
    print("  the page says:", setup.eval_on_selector("#state", "e => [e.dataset.state, document.getElementById('title').textContent, document.getElementById('steps').children.length]"))
    print("host manifest:", capture.install([ext_id], dirs={"chromium": prof / "NativeMessagingHosts"}, home=home, app=True))
    setup.click("#check"); setup.wait_for_timeout(1500)
    print("  checked again:", setup.eval_on_selector("#state", "e => [e.dataset.state, document.getElementById('text').textContent]"))
    ctx.add_cookies([{"name": "session", "value": "reader", "url": base}])
    results = {}
    for path in ("/article", "/drawn", "/shadow", "/framed", "/press", "/mathjax"):
        pg, reply = send(ctx, sw, path)
        results[path] = reply
        print(path, "->", reply)
    ctx.clear_cookies()
    pg, reply = send(ctx, sw, "/article?as=visitor")
    results["/article?as=visitor"] = reply; print("/article?as=visitor ->", reply)
    pg, reply = send(ctx, sw, "/article")
    print("/article again ->", reply)
    (data / "server.json").write_text(json.dumps({"format": "textfold/server", "url": base, "pid": os.getpid()}))   # (TextFold running)
    pg, reply = send(ctx, sw, "/drawn?while=running")
    pg.wait_for_timeout(800)
    print("while TextFold runs ->", reply, "| tabs:", [x.url.replace(base, "") for x in ctx.pages][-2:], "| asked:", asked)
    ctx.close()
srv.shutdown()

for path, r in results.items():
    if not r.get("ok"):
        continue
    d = data / "papers" / r["paper"]
    html = (d / "source.html").read_text(encoding="utf-8")
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    import re
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    print(f"{path:22} title={meta['title']!r} via={meta['source'].get('via')} kind={meta.get('snapshot_kind')} reader={meta.get('reader')} "
          f"paragraphs={html.count('<p class=\"ltx_p\"')} notes={html.count('ltx_role_footnote')} "
          f"snapshot={'snapshot.html' in os.listdir(d)} | " +
          " ".join(f"{w}:{w in text}" for w in ("Paragraph 6.", "Subscribe to continue", "Open shadow.", "Closed shadow.", "Inside the frame.", "Since the telemetry")))
    if path == "/mathjax":
        print(" " * 23 + f"tex_inline={'alttext=\"y_i\"' in html} mathml_display={'<mfrac><mn>1</mn> <mi>n</mi></mfrac>' in html} "
              f"its_latex={'alttext=\"m = \\frac{1}{n}\"' in html} "
              f"equations={html.count('ltx_equation ltx_eqn_table')} drawing_left={'mjx-' in html or '𝑦' in html}")
    if path == "/press":
        print(" " * 23 + " ".join(f"{w}:{w in text}" for w in ("Abstract.", "[2]", "Fig. 1", "The gauges at the river office.",
              "Download high-res", "Published by", "View PDF", "Spring floods.", "About Example Press", "Journals Books"))
              + f" figure_img={'<img' in html and 'img/' in html} sections={html.count('ltx_title_section')}")
