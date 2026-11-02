// The page as its reader sees it, serialized in the page itself: what the extension runs in the tab's frames when
// the reader asks for it (background.js), and what TextFold's own tests run in a browser. Shadow roots are spelled out
// in place, their slots filled with what is assigned to them (a closed one too, where the browser lets an extension
// open it); an element the browser does not show (display none, visibility hidden, opacity 0) is marked
// data-tf-css-hidden, for TextFold to read as a note when it hangs on a mark and to leave out otherwise; an iframe is a
// marker (<!--TF-FRAME-k-->) with its address, which the caller fills with that frame's own serialization. Scripts and
// styles are left out, but for JSON-LD, which says what the page is. Nothing is sent from here: the value of this
// script is the snapshot, {url, title, html}.
(() => {
  const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const q = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  const shadow = (el) => {   // (an extension may open a closed one; a page's own script sees the open ones)
    try {
      if (typeof chrome !== 'undefined' && chrome.dom && chrome.dom.openOrClosedShadowRoot) return chrome.dom.openOrClosedShadowRoot(el);
    } catch (e) { /* not an extension's script */ }
    return el.shadowRoot;
  };
  let frames = 0;
  const attrs = (el, extra) => {
    let s = '';
    for (const a of el.attributes) s += ` ${a.name}="${q(a.value)}"`;
    for (const [k, v] of extra) s += ` ${k}="${q(v)}"`;
    return s;
  };
  function ser(n, body) {
    if (n.nodeType === 3) return esc(n.data);
    if (n.nodeType !== 1) return '';
    const tag = n.localName;
    if (tag === 'slot') {
      const got = n.assignedNodes({ flatten: true });
      return (got.length ? got : [...n.childNodes]).map((c) => ser(c, body)).join('');
    }
    if (tag === 'script') return n.type === 'application/ld+json' ? `<script type="application/ld+json">${esc(n.textContent)}</script>` : '';
    if (tag === 'style' || tag === 'template' || tag === 'noscript') return '';
    const extra = [];
    if (body) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse' || parseFloat(cs.opacity) === 0) extra.push(['data-tf-css-hidden', '1']);
    }
    const root = shadow(n);
    if (root) extra.push(['data-tf-shadow', '1']);
    if (tag === 'iframe' || tag === 'frame') {
      const k = String(frames++);
      let src = '';
      try { src = new URL(n.getAttribute('src') || 'about:blank', document.baseURI).href; } catch (e) { /* a broken address */ }
      return `<div${attrs(n, [...extra, ['data-tf-frame', k], ['data-tf-frame-src', src]])}><!--TF-FRAME-${k}--></div>`;
    }
    if (VOID.has(tag)) return `<${tag}${attrs(n, extra)}>`;
    const kids = root ? [...root.childNodes] : [...n.childNodes];
    return `<${tag}${attrs(n, extra)}>${kids.map((c) => ser(c, body || tag === 'body')).join('')}</${tag}>`;
  }
  const html = `<!doctype html><html${attrs(document.documentElement, [])}>${ser(document.head, false)}${ser(document.body, true)}</html>`;
  return { url: location.href, title: document.title, html };
})();
