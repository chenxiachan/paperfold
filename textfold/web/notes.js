// The notes page (/notes): every highlight, note and question of the library, newest first, by day and by text.
// A note unfolds in place to the paragraph it is on and the line of its section (the text as it is now, /api/doc), or
// opens there (#n=). The notes ticked are summarized (/api/summary) into a document of the library, which opens.
(() => {
  const I18N = window.DR_I18N;
  const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } } };
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

  let data = { papers: {}, notes: [] }, kind = 'all', query = '';
  const picked = new Set(), open = new Set(), docs = {};
  const key = (n) => `${n.paper}|${n.id}`;
  // as the reader counts them (notes.py, kind): a question, a note with words, a highlight
  const kindOf = (n) => (n.kind === 'ask' ? 'ask' : (n.text || '').trim() ? 'note' : 'hl');
  const turns = (n) => (Array.isArray(n.thread) ? n.thread : []).filter((t) => t && t.q);
  const titleOf = (pid) => { const p = data.papers[pid] || {}; return p.name || p.title || pid; };
  const hay = (n) => fold([n.text, (n.anchor && n.anchor.quote && n.anchor.quote.exact) || '', ...turns(n).flatMap((t) => [t.q, t.takeaway]), titleOf(n.paper)].join(' '));
  const dayOf = (n) => { const d = new Date(n.created || 0); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const dayName = (t) => {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const s = new Intl.DateTimeFormat(I18N.htmlLang(ui), { month: 'long', day: 'numeric', weekday: 'short' }).format(t);
    return t === today.getTime() ? `${T.nb_today} · ${s}` : t === today.getTime() - 864e5 ? `${T.nb_yesterday} · ${s}` : s;
  };
  const clock = (n) => new Intl.DateTimeFormat(I18N.htmlLang(ui), { hour: '2-digit', minute: '2-digit' }).format(new Date(n.created || 0));
  const placeOf = (n) => {
    const a = n.anchor || {}, lang = a.lang ? `?lang=${encodeURIComponent(a.lang)}` : '';
    return `/p/${n.paper}${lang}#n=${n.id}${a.unit ? `&u=${encodeURIComponent(a.unit)}` : ''}`;
  };

  function shown() {
    const q = fold(query.trim());
    return data.notes.filter((n) => (kind === 'all' || kindOf(n) === kind) && (!q || hay(n).includes(q)));
  }

  function noteHtml(n) {
    const a = n.anchor || {}, k = kindOf(n), quote = (a.quote && a.quote.exact) || '';
    const said = a.shown && a.shown.exact;   // made on a line the model wrote (Key, Takeaway): its words, said so
    const qa = turns(n).map((t) => `<p><b>${esc(T.nb_asked)}</b>${esc(t.q)}</p>${t.takeaway ? `<p><b>${esc(T.nb_answer)}</b>${esc(t.takeaway)}</p>` : ''}`).join('');
    const passage = said ? `<blockquote class="nb-quote">${esc(said)}<span class="nb-written">${esc(T.nb_written.replace('{lvl}', LEVELS[a.level] || ''))}</span></blockquote>`
      : quote ? `<blockquote class="nb-quote">${esc(quote)}</blockquote>` : a.on === 'paper' ? `<blockquote class="nb-quote">${esc(T.nb_whole)}</blockquote>` : '';
    const ctx = open.has(key(n));
    return `<article class="nb-note${picked.has(key(n)) ? ' picked' : ''}" data-key="${esc(key(n))}">` +
      `<input type="checkbox" class="nb-check" aria-label="${esc(T.nb_pick)}"${picked.has(key(n)) ? ' checked' : ''}>` +
      `<div class="nb-nbody"><div class="nb-meta"><span class="nb-kind ${k}">${esc(T[`nb_k_${k}`])}</span><span>${esc(clock(n))}</span></div>` +
      ((n.text || '').trim() ? `<p class="nb-text">${esc(n.text.trim())}</p>` : '') + (qa ? `<div class="nb-qa">${qa}</div>` : '') + passage +
      `<div class="nb-acts">${a.unit ? `<button type="button" class="nb-unfold" aria-expanded="${ctx}">${esc(ctx ? T.nb_fold : T.nb_unfold)}</button>` : ''}` +
      `<a href="${esc(placeOf(n))}">${esc(T.nb_there)} ↗</a></div>` +
      `<div class="nb-ctx"${ctx ? '' : ' hidden'}></div></div></article>`;
  }

  function render() {
    const list = shown(), T_ = T;
    $('nb-count').textContent = data.notes.length ? T_.nb_n.replace('{n}', data.notes.length).replace('{d}', Object.keys(data.papers).length) : '';
    if (!data.notes.length) { $('nb-list').innerHTML = `<p class="nb-empty">${esc(T_.nb_empty)}</p>`; bar(); return; }
    if (!list.length) { $('nb-list').innerHTML = `<p class="nb-empty">${esc(T_.nb_none)}</p>`; bar(); return; }
    // by day, the newest first; in a day, by text, the one written in last first
    const days = new Map();
    for (const n of list) {
      const d = dayOf(n);
      if (!days.has(d)) days.set(d, new Map());
      const g = days.get(d);
      if (!g.has(n.paper)) g.set(n.paper, []);
      g.get(n.paper).push(n);
    }
    let html = '';
    for (const [d, g] of days) {
      html += `<section class="nb-day"><h2>${esc(dayName(d))}</h2>`;
      for (const [pid, ns] of g) {
        const all = ns.every((n) => picked.has(key(n))), some = ns.some((n) => picked.has(key(n)));
        const p = data.papers[pid] || {};
        html += `<div class="nb-doc" data-day="${d}" data-pid="${esc(pid)}"><div class="nb-dhead">` +
          `<input type="checkbox" class="nb-check nb-dcheck" aria-label="${esc(T_.nb_pick_doc)}"${all ? ' checked' : ''}${!all && some ? ' data-some="1"' : ''}>` +
          `<a href="/p/${esc(pid)}${p.lang ? `?lang=${esc(p.lang)}` : ''}">${esc(titleOf(pid))}${p.summary ? `<span class="nb-tag">${esc(T_.nb_summary_doc)}</span>` : ''}</a>` +
          `<span class="nb-dn">${esc(T_.nb_dn.replace('{n}', ns.length))}</span></div>${ns.map(noteHtml).join('')}</div>`;
      }
      html += '</section>';
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
    const exact = (a.quote && a.quote.exact) || '', full = u.full || '', at = exact ? full.indexOf(exact) : -1;
    const para = at < 0 ? esc(full) : `${esc(full.slice(0, at))}<mark>${esc(exact)}</mark>${esc(full.slice(at + exact.length))}`;
    el.innerHTML = `<div class="nb-sec">${esc(sec.title || '')}${sec.takeaway ? ` <span>· ${esc(sec.takeaway)}</span>` : ''}</div><p class="nb-para">${para}</p>`;
    el.dataset.done = '1';
  }

  $('nb-list').addEventListener('click', (e) => {
    const note = e.target.closest('.nb-note');
    if (e.target.matches('.nb-dcheck')) {
      const box = e.target.closest('.nb-doc'), ns = shown().filter((n) => n.paper === box.dataset.pid && String(dayOf(n)) === box.dataset.day);
      for (const n of ns) { if (e.target.checked) picked.add(key(n)); else picked.delete(key(n)); }
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
  $('nb-kinds').innerHTML = ['all', 'hl', 'note', 'ask'].map((k) => `<button type="button" role="radio" data-k="${k}" aria-checked="${k === kind}">${esc(T[`nb_f_${k}`])}</button>`).join('');
  $('nb-kinds').onclick = (e) => {
    const b = e.target.closest('button[data-k]');
    if (!b) return;
    kind = b.dataset.k;
    $('nb-kinds').querySelectorAll('button').forEach((x) => x.setAttribute('aria-checked', x === b));
    render();
  };
  $('nb-clear').textContent = T.nb_clear; $('nb-go').textContent = T.nb_go;
  fetch('/api/models').then((r) => r.json()).then((m) => {
    const name = m.askName || m.selectedName;
    $('nb-model').textContent = name ? T.nb_model.replace('{m}', name) : T.nb_no_model;
  }).catch(() => {});
  fetch('/api/notes').then((r) => r.json()).then((d) => { data = d; render(); })
    .catch(() => { $('nb-list').innerHTML = `<p class="nb-empty">${esc(T.nb_none)}</p>`; });
})();
