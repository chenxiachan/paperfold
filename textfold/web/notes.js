// The notes page (/notes): every highlight, note and question of the library, by text or by day. By text (the first
// view), each text once, the one written in last first, its notes in the order they were made, folded to a line; by
// day, the newest day first, a text under each day it was written in. A note unfolds in place to the paragraph it is
// on and the line of its section (the text as it is now, /api/doc), or opens there (#n=). The notes ticked are
// summarized (/api/summary) into a document of the library, which opens.
(() => {
  const I18N = window.DR_I18N;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } },
  };
  try {   // the brightness and the style chosen in a text's Aa menu (reader.js, textfold.type), here too
    const v = JSON.parse(store.get('textfold.type') || 'null') || {}, r = document.documentElement;
    if (['light', 'dark'].includes(v.mode)) r.dataset.theme = v.mode;
    if (v.style === 'paper') r.dataset.style = v.style;
  } catch { /* (written by hand) */ }
  const ui = (() => { const v = store.get('pf-ui-lang'); return v && I18N.NATIVE[v] ? v : I18N.guess(); })();
  const T = I18N.t(ui);
  document.documentElement.lang = I18N.htmlLang(ui);
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const $ = (id) => document.getElementById(id);
  const fold = (s) => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  const LEVELS = ['Topic', 'Takeaway', 'Key', 'Brief', 'Full'];
  const ORDER = 'textfold.notes.order';
  const CHEV = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  let data = { papers: {}, notes: [] }, kind = 'all', query = '';
  let order = store.get(ORDER) === 'day' ? 'day' : 'doc';
  const picked = new Set(), open = new Set(), docs = {};
  const flipped = new Set();   // the texts folded or unfolded by hand, against the view's way (by text: folded)
  let groups = new Map();      // what each text's box on the page holds: its notes shown
  const key = (n) => `${n.paper}|${n.id}`;
  // as the reader counts them (notes.py, kind): a question, a note with words, a highlight
  const kindOf = (n) => (n.kind === 'ask' ? 'ask' : (n.text || '').trim() ? 'note' : 'hl');
  const turns = (n) => (Array.isArray(n.thread) ? n.thread : []).filter((t) => t && t.q);
  const titleOf = (pid) => { const p = data.papers[pid] || {}; return p.name || p.title || pid; };
  const quoteOf = (n) => (n.anchor && n.anchor.quote && n.anchor.quote.exact) || '';
  const hay = (n) => fold([n.text, quoteOf(n), ...turns(n).flatMap((t) => [t.q, t.takeaway]), titleOf(n.paper)].join(' '));
  const at = (n) => new Date(n.created || 0);
  const dayOf = (n) => { const d = at(n); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const fmt = (o) => new Intl.DateTimeFormat(I18N.htmlLang(ui), o);
  const dayName = (t) => {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const s = fmt({ month: 'long', day: 'numeric', weekday: 'short' }).format(t);
    return t === today.getTime() ? `${T.nb_today} · ${s}` : t === today.getTime() - 864e5 ? `${T.nb_yesterday} · ${s}` : s;
  };
  const short = (t) => fmt({ month: 'numeric', day: 'numeric' }).format(t);
  const clock = (n) => fmt({ hour: '2-digit', minute: '2-digit' }).format(at(n));
  const stamp = (n) => (order === 'doc' ? `${short(at(n))} ${clock(n)}` : clock(n));
  const lineOf = (n) => (n.text || '').trim() || (turns(n)[0] || {}).q || quoteOf(n);   // a note in a line, folded
  const placeOf = (n) => {
    const a = n.anchor || {}, lang = a.lang ? `?lang=${encodeURIComponent(a.lang)}` : '';
    return `/p/${n.paper}${lang}#n=${n.id}${a.unit ? `&u=${encodeURIComponent(a.unit)}` : ''}`;
  };

  function shown() {
    const q = fold(query.trim());
    return data.notes.filter((n) => (kind === 'all' || kindOf(n) === kind) && (!q || hay(n).includes(q)));
  }

  function noteHtml(n) {
    const a = n.anchor || {}, k = kindOf(n), quote = quoteOf(n);
    const said = a.shown && a.shown.exact;   // made on a line the model wrote (Key, Takeaway): its words, said so
    const qa = turns(n).map((t) => `<p><b>${esc(T.nb_asked)}</b>${esc(t.q)}</p>${t.takeaway ? `<p><b>${esc(T.nb_answer)}</b>${esc(t.takeaway)}</p>` : ''}`).join('');
    const passage = said ? `<blockquote class="nb-quote">${esc(said)}<span class="nb-written">${esc(T.nb_written.replace('{lvl}', LEVELS[a.level] || ''))}</span></blockquote>`
      : quote ? `<blockquote class="nb-quote">${esc(quote)}</blockquote>` : a.on === 'paper' ? `<blockquote class="nb-quote">${esc(T.nb_whole)}</blockquote>` : '';
    const ctx = open.has(key(n));
    return `<article class="nb-note${picked.has(key(n)) ? ' picked' : ''}" data-key="${esc(key(n))}">` +
      `<input type="checkbox" class="nb-check" aria-label="${esc(T.nb_pick)}"${picked.has(key(n)) ? ' checked' : ''}>` +
      `<div class="nb-nbody"><div class="nb-meta"><span class="nb-kind ${k}">${esc(T[`nb_k_${k}`])}</span><span>${esc(stamp(n))}</span></div>` +
      ((n.text || '').trim() ? `<p class="nb-text">${esc(n.text.trim())}</p>` : '') + (qa ? `<div class="nb-qa">${qa}</div>` : '') + passage +
      `<div class="nb-acts">${a.unit ? `<button type="button" class="nb-unfold" aria-expanded="${ctx}">${esc(ctx ? T.nb_fold : T.nb_unfold)}</button>` : ''}` +
      `<a href="${esc(placeOf(n))}">${esc(T.nb_there)} ↗</a></div>` +
      `<div class="nb-ctx"${ctx ? '' : ' hidden'}></div></div></article>`;
  }

  // a text's box: its notes (shown), folded to its title, how many, over which days, and its latest note's line
  function boxHtml(g, gk) {
    const ns = g.notes, p = data.papers[g.pid] || {};
    const searching = !!query.trim();
    const shut = searching ? false : (order === 'doc') !== flipped.has(gk);
    const all = ns.every((n) => picked.has(key(n))), some = ns.some((n) => picked.has(key(n)));
    const days = ns.map(dayOf), a = Math.min(...days), b = Math.max(...days);
    const span = order === 'doc' ? ` · ${a === b ? short(a) : T.nb_span.replace('{a}', short(a)).replace('{b}', short(b))}` : '';
    const last = ns.reduce((x, y) => ((y.created || '') > (x.created || '') ? y : x));
    return `<div class="nb-doc${shut ? ' shut' : ''}" data-g="${esc(gk)}"><div class="nb-dhead">` +
      `<input type="checkbox" class="nb-check nb-dcheck" aria-label="${esc(T.nb_pick_doc)}"${all ? ' checked' : ''}${!all && some ? ' data-some="1"' : ''}>` +
      `<button type="button" class="nb-dtitle" aria-expanded="${!shut}">${CHEV}<span>${esc(titleOf(g.pid))}</span>` +
      `${p.summary ? `<span class="nb-tag">${esc(T.nb_summary_doc)}</span>` : ''}</button>` +
      `<span class="nb-dn">${esc(T.nb_dn.replace('{n}', ns.length))}${esc(span)}</span>` +
      `<a class="nb-dopen" href="/p/${esc(g.pid)}${p.lang ? `?lang=${esc(p.lang)}` : ''}" title="${esc(T.nb_open)}" aria-label="${esc(T.nb_open)}">↗</a></div>` +
      (shut ? `<div class="nb-dprev">${esc(lineOf(last))}</div>` : `<div class="nb-dnotes">${ns.map(noteHtml).join('')}</div>`) + '</div>';
  }

  function render() {
    const list = shown();
    $('nb-count').textContent = data.notes.length ? T.nb_n.replace('{n}', data.notes.length).replace('{d}', Object.keys(data.papers).length) : '';
    groups = new Map();
    if (!data.notes.length || !list.length) {
      $('nb-list').innerHTML = `<p class="nb-empty">${esc(data.notes.length ? T.nb_none : T.nb_empty)}</p>`;
      return bar();
    }
    let html = '';
    if (order === 'doc') {
      // each text once, the one written in last first; its notes in the order they were made
      const by = new Map();
      for (const n of list) { if (!by.has(n.paper)) by.set(n.paper, []); by.get(n.paper).push(n); }
      for (const [pid, ns] of by) {
        const gk = `doc|${pid}`;
        groups.set(gk, { pid, notes: ns.slice().reverse() });
        html += boxHtml(groups.get(gk), gk);
      }
    } else {
      // the newest day first; in a day, the text written in last first, its notes the newest first
      const days = new Map();
      for (const n of list) {
        const d = dayOf(n);
        if (!days.has(d)) days.set(d, new Map());
        const g = days.get(d);
        if (!g.has(n.paper)) g.set(n.paper, []);
        g.get(n.paper).push(n);
      }
      for (const [d, g] of days) {
        html += `<section class="nb-day"><h2>${esc(dayName(d))}</h2>`;
        for (const [pid, ns] of g) {
          const gk = `day|${d}|${pid}`;
          groups.set(gk, { pid, notes: ns });
          html += boxHtml(groups.get(gk), gk);
        }
        html += '</section>';
      }
    }
    $('nb-list').innerHTML = html;
    document.querySelectorAll('.nb-dcheck[data-some]').forEach((c) => { c.indeterminate = true; });
    for (const k of open) { const el = document.querySelector(`.nb-note[data-key="${CSS.escape(k)}"] .nb-ctx`); if (el) context(k, el); }
    bar();
  }

  const byKey = (k) => data.notes.find((n) => key(n) === k);
  function bar() {
    const docsPicked = new Set([...picked].map((k) => k.split('|')[0]));
    $('nb-bar').hidden = !picked.size;
    $('nb-picked').textContent = T.nb_picked.replace('{n}', picked.size).replace('{d}', docsPicked.size);
    const all = shown();
    $('nb-all').textContent = all.length && all.every((n) => picked.has(key(n))) ? T.nb_none_all : T.nb_all;
  }

  // the paragraph a note is on, as the text reads now, and its section's line; the passage marked in it
  function docOf(pid, lang) {
    const k = `${pid}|${lang || ''}`;
    if (!docs[k]) docs[k] = fetch(`/api/doc/${encodeURIComponent(pid)}${lang ? `?lang=${encodeURIComponent(lang)}` : ''}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    return docs[k];
  }
  async function context(k, el) {
    const n = byKey(k);
    if (!n) return;
    const a = n.anchor || {};
    el.hidden = false;
    if (el.dataset.done) return;
    el.textContent = T.nb_loading;
    const doc = await docOf(n.paper, a.lang);
    const sec = doc && doc.sections.find((s) => s.units.some((u) => u.id === a.unit));
    const u = sec && sec.units.find((x) => x.id === a.unit);
    if (!u) { el.textContent = T.nb_gone; el.dataset.done = '1'; return; }
    const exact = quoteOf(n), full = u.full || '', i = exact ? full.indexOf(exact) : -1;
    const para = i < 0 ? esc(full) : `${esc(full.slice(0, i))}<mark>${esc(exact)}</mark>${esc(full.slice(i + exact.length))}`;
    el.innerHTML = `<div class="nb-sec">${esc(sec.title || '')}${sec.takeaway ? ` <span>· ${esc(sec.takeaway)}</span>` : ''}</div><p class="nb-para">${para}</p>`;
    el.dataset.done = '1';
  }

  $('nb-list').addEventListener('click', (e) => {
    const box = e.target.closest('.nb-doc'), note = e.target.closest('.nb-note');
    if (box && e.target.matches('.nb-dcheck')) {
      for (const n of groups.get(box.dataset.g).notes) { if (e.target.checked) picked.add(key(n)); else picked.delete(key(n)); }
      return render();
    }
    if (box && (e.target.closest('.nb-dtitle') || e.target.closest('.nb-dprev'))) {
      const gk = box.dataset.g;
      if (flipped.has(gk)) flipped.delete(gk); else flipped.add(gk);
      return render();
    }
    if (note && e.target.matches('.nb-check')) {
      if (e.target.checked) picked.add(note.dataset.key); else picked.delete(note.dataset.key);
      return render();
    }
    if (note && e.target.closest('.nb-unfold')) {
      const k = note.dataset.key, el = note.querySelector('.nb-ctx'), b = e.target.closest('.nb-unfold');
      if (open.has(k)) { open.delete(k); el.hidden = true; } else { open.add(k); context(k, el); }
      b.textContent = open.has(k) ? T.nb_fold : T.nb_unfold;
      b.setAttribute('aria-expanded', open.has(k));
    }
  });
  $('nb-q').addEventListener('input', (e) => { query = e.target.value; render(); });
  $('nb-all').onclick = () => {
    const all = shown(), every = all.every((n) => picked.has(key(n)));
    for (const n of all) { if (every) picked.delete(key(n)); else picked.add(key(n)); }
    render();
  };
  $('nb-clear').onclick = () => { picked.clear(); $('nb-said').textContent = ''; render(); };
  $('nb-go').onclick = async () => {
    const items = data.notes.filter((n) => picked.has(key(n))).map((n) => ({ paper: n.paper, note: n.id }));
    const go = $('nb-go'), said = $('nb-said');
    go.disabled = true; said.className = 'nb-said'; said.textContent = T.nb_busy;
    try {
      const r = await fetch('/api/summary', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items, ui }) });
      const got = await r.json();
      if (!r.ok) throw new Error(got.error || r.status);
      location.href = `/p/${got.paper}?lang=${encodeURIComponent(got.lang)}`;
    } catch (x) {
      said.className = 'nb-said bad'; said.textContent = T.nb_failed.replace('{e}', x.message); go.disabled = false;
    }
  };

  document.title = `${T.nb_title} · TextFold`;
  $('nb-title').textContent = T.nb_title;
  $('nb-q').placeholder = T.nb_search; $('nb-q').setAttribute('aria-label', T.nb_search);
  const radios = (el, items, now, on) => {
    el.innerHTML = items.map(([k, name]) => `<button type="button" role="radio" data-k="${k}" aria-checked="${k === now}">${esc(name)}</button>`).join('');
    el.onclick = (e) => {
      const b = e.target.closest('button[data-k]');
      if (!b) return;
      el.querySelectorAll('button').forEach((x) => x.setAttribute('aria-checked', x === b));
      on(b.dataset.k);
      render();
    };
  };
  radios($('nb-order'), [['doc', T.nb_by_doc], ['day', T.nb_by_day]], order, (k) => { order = k; flipped.clear(); store.set(ORDER, k); });
  radios($('nb-kinds'), ['all', 'hl', 'note', 'ask'].map((k) => [k, T[`nb_f_${k}`]]), kind, (k) => { kind = k; });
  $('nb-clear').textContent = T.nb_clear; $('nb-go').textContent = T.nb_go;
  fetch('/api/models').then((r) => r.json()).then((m) => {
    const name = m.askName || m.selectedName;
    $('nb-model').textContent = name ? T.nb_model.replace('{m}', name) : T.nb_no_model;
  }).catch(() => {});
  fetch('/api/notes').then((r) => r.json()).then((d) => { data = d; render(); })
    .catch(() => { $('nb-list').innerHTML = `<p class="nb-empty">${esc(T.nb_none)}</p>`; });
})();
