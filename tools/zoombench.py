"""How smooth the zoom is, measured as the screen sees it.

    python3 tools/zoombench.py <paper id> [WIDTHxHEIGHT] [v03,v05,...]

Opens out/compare/<paper id>/<version>.html in Chromium with the Mac's GPU (Metal) at 2x pixels, plays the same
gestures on each (a pinch out, a pinch in, a drag of the level bar, a click on Full) and reads Chrome's own frame
trace: frames presented, frames dropped, and the longest gaps between presented frames.

Why this way: frame intervals measured from requestAnimationFrame in a default headless browser (software rendering,
1x pixels) only see the main thread. v0.8 looked perfect that way (every frame under 17 ms) and still dropped one frame
in five on a real GPU at 2x, which is what the reader felt. Needs `pip install playwright` and `playwright install chromium`.
"""
import time, json, sys
from playwright.sync_api import sync_playwright
from pathlib import Path
B = (Path(__file__).resolve().parent.parent / 'out' / 'compare' / (sys.argv[1] if len(sys.argv) > 1 else '2605.00089')).as_uri() + '/'
VW, VH = (int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else '1512x982').split('x'))
VERS = (sys.argv[3] if len(sys.argv) > 3 else 'v03,v05,v06,v07,v08').split(',')
CATS = ['benchmark', 'cc', 'disabled-by-default-devtools.timeline.frame']
def frames(buf):
    ev = json.loads(buf); ev = ev['traceEvents'] if isinstance(ev, dict) else ev
    seen = {}
    for e in ev:
        if e.get('name') != 'PipelineReporter' or e.get('ph') != 'b': continue
        fr = e['args']['frame_reporter']
        if fr.get('frame_type') == 'FORKED': continue
        seen[(fr.get('frame_source'), fr.get('frame_sequence'))] = (e['ts'] / 1000, fr['state'])
    return sorted(seen.values())
def stats(fr):
    act = [f for f in fr if f[1] != 'STATE_NO_UPDATE_DESIRED']
    if not act: return 'no frames'
    t0, t1 = act[0][0], act[-1][0]
    pres = [t for t, s in fr if s.startswith('STATE_PRESENTED') and t0 <= t <= t1]
    drop = sum(1 for t, s in act if s == 'STATE_DROPPED')
    gaps = sorted((b - a for a, b in zip(pres, pres[1:])), reverse=True)
    return {'ms': round(t1 - t0), 'presented': len(pres), 'dropped': drop, 'drop%': round(100 * drop / max(1, drop + len(pres))), 'worst gaps ms': [round(g) for g in gaps[:4]]}
def run(pg, b, act):
    b.start_tracing(page=pg, categories=CATS); act(); return stats(frames(b.stop_tracing()))
with sync_playwright() as p:
    br = p.chromium.launch(channel='chromium', args=['--use-angle=metal', '--enable-gpu-rasterization'])
    for v in VERS:
        pg = br.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=2)
        pg.goto(B + v + '.html'); time.sleep(1.0)
        pg.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)"); pg.mouse.move(VW // 2 - 50, VH // 2 - 60); time.sleep(2.5)
        def pinch(d, n=110):
            def f():
                pg.keyboard.down('Control')
                for i in range(n): pg.mouse.wheel(0, d); time.sleep(0.016)
                pg.keyboard.up('Control'); time.sleep(1.2)
            return f
        lv = lambda: pg.evaluate("document.getElementById('doc').dataset.level")
        r1 = run(pg, br, pinch(6.5)); l1 = lv(); time.sleep(2.5)
        r2 = run(pg, br, pinch(-6.5)); l2 = lv(); time.sleep(2.5)
        btn = pg.evaluate("[...document.querySelectorAll('#zoombar button')].map(b => { const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })")
        def drag():
            pg.mouse.move(*btn[0]); pg.mouse.down()
            for i in range(1, 61): pg.mouse.move(btn[0][0] + (btn[4][0] - btn[0][0]) * i / 60, btn[0][1]); time.sleep(0.016)
            pg.mouse.up(); time.sleep(1.2)
        r3 = run(pg, br, drag); l3 = lv(); time.sleep(2.5)
        def click(): pg.mouse.click(*btn[0]); time.sleep(1.5)
        r4 = run(pg, br, click); l4 = lv()
        print(f'{v}  pinch out ->L{l1}: {r1}\n     pinch in  ->L{l2}: {r2}\n     slider drag ->L{l3}: {r3}\n     click Full  ->L{l4}: {r4}', flush=True)
        pg.close()
    br.close()
