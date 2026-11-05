// The notes page (/notes): every highlight, note and question of the library, as a list of texts or on a calendar.
// The list: each text once, the one written in last first, folded to its title and its latest note; open, its notes in
// the order they were made. The calendar: a month of days, or zoomed out (− or ⌘ and the wheel, a pinch), a year of
// squares, the deeper the more notes that day; the days picked (a click, a drag, shift and a click) list their texts
// below, as do the month or year in view when none is. A note's passage unfolds in place to its paragraph as the text
// reads now (/api/doc); it opens there (#n=), goes (with an undo), and shows the summaries it went into. The notes
// ticked are deleted, or summarized (/api/summary) into a document of the library, which opens.
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
  const T = I18N.t(ui), LOC = I18N.htmlLang(ui);
  document.documentElement.lang = LOC;
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const $ = (id) => document.getElementById(id);
  const fold = (s) => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  const LEVELS = ['Topic', 'Takeaway', 'Key', 'Brief', 'Full'];
  const svg = (d, w = 1.6) => `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const I = {
    chev: svg('<path d="M8 5l5 5-5 5"/>'), left: svg('<path d="M12 5l-5 5 5 5"/>'), right: svg('<path d="M8 5l5 5-5 5"/>'),
    out: svg('<path d="M8 4h8v8"/><path d="M16 4l-9 9"/><path d="M13 16H4V7"/>'), trash: svg('<path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10"/>'),
    sum: svg('<path d="M5 3.5h10v13H5z"/><path d="M7.5 7h5M7.5 10h5M7.5 13h3"/>'),
    list: svg('<path d="M4 5h12M4 10h12M4 15h12"/>'), cal: svg('<rect x="3.5" y="4.5" width="13" height="12" rx="2"/><path d="M3.5 8.5h13M7 3v3M13 3v3"/>'),
    minus: svg('<path d="M5 10h10"/>'), plus: svg('<path d="M5 10h10M10 5v10"/>'),
  };
  const VIEW = 'textfold.notes.view';
  const pref = (() => { try { return JSON.parse(store.get(VIEW) || 'null') || {}; } catch { return {}; } })();
  let view = pref.view === 'cal' ? 'cal' : 'list', zoom = pref.zoom === 'year' ? 'year' : 'month';
  const keep = () => store.set(VIEW, JSON.stringify({ view, zoom }));

  let data = { papers: {}, notes: [], summaries: {}, used: {} }, kind = 'all', query = '';
  const picked = new Set(), open = new Set(), docs = {}, unfolded = new Set();
  let groups = new Map(), range = null, toastTimer = null;
  const now = new Date();
  let cursor = { y: now.getFullYear(), m: now.getMonth() };   // the month (or year) the calendar shows
  const key = (n) => `${n.paper}|${n.id}`;
  const kindOf = (n) => (n.kind === 'ask' ? 'ask' : (n.text || '').trim() ? 'note' : 'hl');   // (notes.py, kind)
  const turns = (n) => (Array.isArray(n.thread) ? n.thread : []).filter((t) => t && t.q);
  const titleOf = (pid) => { const p = data.papers[pid] || {}; return p.name || p.title || pid; };
  const quoteOf = (n) => (n.anchor && n.anchor.quote && n.anchor.quote.exact) || '';
  const hay = (n) => fold([n.text, quoteOf(n), ...turns(n).flatMap((t) => [t.q, t.takeaway]), titleOf(n.paper)].join(' '));
  const lineOf = (n) => (n.text || '').trim() || (turns(n)[0] || {}).q || quoteOf(n);   // a note in a line, folded
  const midnight = (t) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const dayOf = (n) => midnight(n.created || 0);
  const plusDays = (t, k) => { const d = new Date(t); d.setDate(d.getDate() + k); return d.getTime(); };
  const fmt = (o) => new Intl.DateTimeFormat(LOC, o);
  const short = (t) => fmt({ month: 'numeric', day: 'numeric' }).format(t);
  const clock = (t) => fmt({ hour: '2-digit', minute: '2-digit' }).format(t);
  const span = (a, b) => (a === b ? short(a) : `${short(a)} – ${short(b)}`);
  const placeOf = (n) => {
    const a = n.anchor || {}, lang = a.lang ? `?lang=${encodeURIComponent(a.lang)}` : '';
    return `/p/${n.paper}${lang}#n=${n.id}${a.unit ? `&u=${encodeURIComponent(a.unit)}` : ''}`;
  };
  const docLink = (pid) => { const p = data.papers[pid] || data.summaries[pid] || {}; return `/p/${pid}${p.lang ? `?lang=${p.lang}` : ''}`; };

  // the notes the search and the kind let through; then those of the days in view
  function filtered() {
    const q = fold(query.trim());
    return data.notes.filter((n) => (kind === 'all' || (kind === 'new' ? !data.used[key(n)] : kindOf(n) === kind)) && (!q || hay(n).includes(q)));
  }
  function period() {
    if (range) return range;
    if (zoom === 'month') return [new Date(cursor.y, cursor.m, 1).getTime(), plusDays(new Date(cursor.y, cursor.m + 1, 1).getTime(), -1)];
    return [new Date(cursor.y, 0, 1).getTime(), new Date(cursor.y, 11, 31).getTime()];
  }
  function listed() {
    const all = filtered();
    if (view === 'list') return all;
    const [a, b] = period();
    return all.filter((n) => { const d = dayOf(n); return d >= a && d <= b; });
  }

  function noteHtml(n) {
    const a = n.anchor || {}, quote = quoteOf(n), t = new Date(n.created || 0);
    const said = a.shown && a.shown.exact;   // made on a line the model wrote (Key, Takeaway): its words, said so
    const ctx = open.has(key(n));
    const fold_ = a.unit ? ` role="button" tabindex="0" aria-expanded="${ctx}" title="${esc(T.nb_ctx)}"` : '';
    const passage = said ? `<blockquote class="nb-quote"${fold_}>${esc(said)}<span class="nb-written">${esc(T.nb_written.replace('{lvl}', LEVELS[a.level] || ''))}</span></blockquote>`
      : quote ? `<blockquote class="nb-quote"${fold_}>${esc(quote)}</blockquote>` : a.on === 'paper' ? `<blockquote class="nb-quote">${esc(T.nb_whole)}</blockquote>` : '';
    const one = view === 'cal' && range && range[0] === range[1];   // (a day picked: its hours alone)
    const used = (data.used[key(n)] || []).filter((s) => data.summaries[s]).map((s) =>
      `<a class="nb-ico nb-used" href="${esc(docLink(s))}" title="${esc(T.nb_used.replace('{t}', data.summaries[s].title))}">${I.sum}</a>`).join('');
    return `<article class="nb-note${picked.has(key(n)) ? ' picked' : ''}" data-key="${esc(key(n))}">` +
      `<input type="checkbox" class="nb-check" aria-label="${esc(T.nb_pick)}"${picked.has(key(n)) ? ' checked' : ''}>` +
      `<div class="nb-nbody"><div class="nb-meta"><time>${esc(one ? clock(t) : `${short(t)} ${clock(t)}`)}</time><span class="nb-icons">${used}` +
      `<a class="nb-ico" href="${esc(placeOf(n))}" title="${esc(T.nb_there)}" aria-label="${esc(T.nb_there)}">${I.out}</a>` +
      `<button type="button" class="nb-ico nb-trash" title="${esc(T.nb_delete)}" aria-label="${esc(T.nb_delete)}">${I.trash}</button></span></div>` +
      ((n.text || '').trim() ? `<p class="nb-text">${esc(n.text.trim())}</p>` : '') +
      turns(n).map((x) => `<p class="nb-q">${esc(x.q)}</p>${x.takeaway ? `<p class="nb-a">${esc(x.takeaway)}</p>` : ''}`).join('') + passage +
      `<div class="nb-ctx"${ctx ? '' : ' hidden'}></div></div></article>`;
  }

  // a text's box, folded to its title, how many notes over which days, and its latest note (or, searching, the first
  // that matches, of how many); open, its notes in the order they were made
  function boxHtml(gk, g) {
    const ns = g.notes, isOpen = unfolded.has(gk);
    const all = ns.every((n) => picked.has(key(n))), some = ns.some((n) => picked.has(key(n)));
    const days = ns.map(dayOf);
    const shown = query.trim() ? ns[0] : ns[ns.length - 1];
    return `<div class="nb-doc${isOpen ? ' open' : ''}" data-g="${esc(gk)}"><div class="nb-dhead">` +
      `<input type="checkbox" class="nb-check nb-dcheck" aria-label="${esc(T.nb_pick_doc)}"${all ? ' checked' : ''}${!all && some ? ' data-some="1"' : ''}>` +
      `<button type="button" class="nb-dtitle" aria-expanded="${isOpen}">${I.chev}${(data.papers[g.pid] || {}).summary ? `<i class="nb-sumico">${I.sum}</i>` : ''}<span>${esc(titleOf(g.pid))}</span></button>` +
      `<span class="nb-dn"><b class="nb-cnt">${ns.length}</b>${esc(span(Math.min(...days), Math.max(...days)))}</span>` +
      `<a class="nb-dopen" href="${esc(docLink(g.pid))}" title="${esc(T.nb_open)}" aria-label="${esc(T.nb_open)}">${I.out}</a></div>` +
      (isOpen ? `<div class="nb-dnotes">${ns.map(noteHtml).join('')}</div>` : `<div class="nb-dprev">${esc(lineOf(shown))}</div>`) + '</div>';
  }

  // the calendar: the notes of each day (as the search and the kind let through), as a month or a year
  function calHtml() {
    const per = new Map();
    for (const n of filtered()) { const d = dayOf(n); per.set(d, (per.get(d) || 0) + 1); }
    const lv = (c) => (!c ? 0 : c === 1 ? 1 : c <= 3 ? 2 : c <= 6 ? 3 : 4);
    const today = midnight(Date.now());
    const cell = (d, out) => {
      const c = per.get(d) || 0, sel = range && d >= range[0] && d <= range[1];
      const tip = `${fmt({ year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' }).format(d)}${c ? ` · ${c}` : ''}`;
      return `<button type="button" class="nb-d lv${lv(c)}${out ? ' out' : ''}${d === today ? ' today' : ''}${sel ? ' sel' : ''}" data-day="${d}" title="${esc(tip)}" aria-label="${esc(tip)}"${out ? ' tabindex="-1"' : ''}>` +
        `${zoom === 'month' ? new Date(d).getDate() : ''}</button>`;
    };
    const monday = (t) => plusDays(t, -((new Date(t).getDay() + 6) % 7));
    let body, title;
    if (zoom === 'month') {
      title = fmt({ year: 'numeric', month: 'long' }).format(new Date(cursor.y, cursor.m, 1));
      const first = new Date(cursor.y, cursor.m, 1).getTime(), last = plusDays(new Date(cursor.y, cursor.m + 1, 1).getTime(), -1);
      const wd = [...Array(7)].map((_, i) => `<span class="nb-wd">${esc(fmt({ weekday: 'narrow' }).format(new Date(2024, 0, 1 + i)))}</span>`).join('');
      let cells = '';
      for (let d = monday(first); d <= last || new Date(d).getDay() !== 1; d = plusDays(d, 1)) cells += cell(d, d < first || d > last);
      body = `<div class="nb-month">${wd}${cells}</div>`;
    } else {
      title = String(cursor.y);
      const first = new Date(cursor.y, 0, 1).getTime(), last = new Date(cursor.y, 11, 31).getTime();
      let cells = '', months = '', col = 0, seen = -1;
      for (let d = monday(first); d <= last || new Date(d).getDay() !== 1; d = plusDays(d, 1)) {
        if (new Date(d).getDay() === 1) col += 1;
        const dt = new Date(d);
        if (d >= first && d <= last && dt.getDate() <= 7 && dt.getMonth() !== seen && new Date(d).getDay() === 1) {
          seen = dt.getMonth();
          months += `<button type="button" data-month="${seen}" style="grid-column:${col} / span 4">${esc(fmt({ month: 'short' }).format(dt))}</button>`;
        }
        cells += cell(d, d < first || d > last);
      }
      body = `<div class="nb-year"><div class="nb-ymonths">${months}</div><div class="nb-ygrid">${cells}</div></div>`;
    }
    return `<div class="nb-calhead"><button type="button" class="nb-ico" data-step="-1" title="${esc(T.nb_prev)}" aria-label="${esc(T.nb_prev)}">${I.left}</button>` +
      `<span class="nb-caltitle">${esc(title)}</span><button type="button" class="nb-ico" data-step="1" title="${esc(T.nb_next)}" aria-label="${esc(T.nb_next)}">${I.right}</button>` +
      `<span class="nb-zoom"><button type="button" class="nb-ico" data-zoom="year" title="${esc(T.nb_zoom_out)}" aria-label="${esc(T.nb_zoom_out)}"${zoom === 'year' ? ' disabled' : ''}>${I.minus}</button>` +
      `<button type="button" class="nb-ico" data-zoom="month" title="${esc(T.nb_zoom_in)}" aria-label="${esc(T.nb_zoom_in)}"${zoom === 'month' ? ' disabled' : ''}>${I.plus}</button></span></div>${body}`;
  }

  function render() {
    $('nb-views').querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', b.dataset.k === view));
    const cal = $('nb-cal');
    cal.hidden = view !== 'cal';
    document.querySelector('.nb-main').classList.toggle('nb-side', view === 'cal' && zoom === 'month');   // (a month beside its notes)
    if (view === 'cal') cal.innerHTML = calHtml();
    const list = listed();
    groups = new Map();
    for (const n of list) {   // each text once, the one written in last first; its notes in the order they were made
      const gk = n.paper;
      if (!groups.has(gk)) groups.set(gk, { pid: n.paper, notes: [] });
      groups.get(gk).notes.unshift(n);
    }
    const every = list.length && list.every((n) => picked.has(key(n))), any = list.some((n) => picked.has(key(n)));
    $('nb-listhead').innerHTML = list.length ? `<input type="checkbox" class="nb-check nb-master" aria-label="${esc(T.nb_pick_all)}"${every ? ' checked' : ''}>` +
      `${view === 'cal' ? `<span>${esc(range ? span(range[0], range[1]) : cal.querySelector('.nb-caltitle').textContent)}</span>` : ''}<b class="nb-cnt">${list.length}</b>` : '';
    const master = $('nb-listhead').querySelector('.nb-master');
    if (master) master.indeterminate = !every && any;
    $('nb-list').innerHTML = !data.notes.length ? `<p class="nb-empty">${esc(T.nb_empty)}</p>`
      : !list.length ? `<p class="nb-empty">${esc(T.nb_none)}</p>` : [...groups].map(([gk, g]) => boxHtml(gk, g)).join('');
    document.querySelectorAll('.nb-dcheck[data-some]').forEach((c) => { c.indeterminate = true; });
    for (const k of open) { const el = document.querySelector(`.nb-note[data-key="${CSS.escape(k)}"] .nb-ctx`); if (el) context(k, el); }
    bar();
  }

  function bar() {
    $('nb-bar').hidden = !picked.size;
    $('nb-picked').textContent = T.nb_picked.replace('{n}', picked.size);
  }

  // the paragraph a note is on, as the text reads now, and its section's line; the passage marked in it
  function docOf(pid, lang) {
    const k = `${pid}|${lang || ''}`;
    if (!docs[k]) docs[k] = fetch(`/api/doc/${encodeURIComponent(pid)}${lang ? `?lang=${encodeURIComponent(lang)}` : ''}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    return docs[k];
  }
  const byKey = (k) => data.notes.find((n) => key(n) === k);
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
  function toggleContext(note) {
    const k = note.dataset.key, el = note.querySelector('.nb-ctx'), q = note.querySelector('.nb-quote[role]');
    if (open.has(k)) { open.delete(k); el.hidden = true; } else { open.add(k); context(k, el); }
    if (q) q.setAttribute('aria-expanded', open.has(k));
  }

  async function load() {
    data = await fetch('/api/notes').then((r) => r.json());
    for (const k of [...picked]) if (!byKey(k)) picked.delete(k);
    render();
  }
  const post = (pid, body) => fetch(`/api/notes/${encodeURIComponent(pid)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  // notes deleted (the same ones as in the reader), and an undo that puts them back as they were
  async function remove(keys) {
    const gone = keys.map(byKey).filter(Boolean);
    for (const n of gone) await post(n.paper, { op: 'delete', id: n.id });
    for (const n of gone) { picked.delete(key(n)); open.delete(key(n)); }
    await load();
    const t = $('nb-toast');
    t.innerHTML = `<span>${esc(T.nb_deleted.replace('{n}', gone.length))}</span><button type="button">${esc(T.nb_undo)}</button>`;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 9000);
    t.querySelector('button').onclick = async () => {
      t.hidden = true;
      for (const n of gone) { const { paper, ...note } = n; await post(paper, { op: 'put', note }); }
      await load();
    };
  }

  $('nb-list').addEventListener('click', (e) => {
    const box = e.target.closest('.nb-doc'), note = e.target.closest('.nb-note');
    if (box && e.target.matches('.nb-dcheck')) {
      for (const n of groups.get(box.dataset.g).notes) { if (e.target.checked) picked.add(key(n)); else picked.delete(key(n)); }
      return render();
    }
    if (box && (e.target.closest('.nb-dtitle') || e.target.closest('.nb-dprev'))) {
      const gk = box.dataset.g;
      if (unfolded.has(gk)) unfolded.delete(gk); else unfolded.add(gk);
      return render();
    }
    if (!note) return;
    if (e.target.matches('.nb-check')) {
      if (e.target.checked) picked.add(note.dataset.key); else picked.delete(note.dataset.key);
      return render();
    }
    if (e.target.closest('.nb-trash')) return remove([note.dataset.key]);
    if (e.target.closest('.nb-quote[role]')) toggleContext(note);
  });
  $('nb-list').addEventListener('keydown', (e) => {
    const q = e.target.closest('.nb-quote[role]');
    if (q && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleContext(q.closest('.nb-note')); }
  });
  $('nb-listhead').addEventListener('click', (e) => {
    if (!e.target.matches('.nb-master')) return;
    for (const n of listed()) { if (e.target.checked) picked.add(key(n)); else picked.delete(key(n)); }
    render();
  });

  // the calendar: a click picks a day (again: none), shift and a click or a drag a run of days; the arrows step a
  // month or a year; − and +, ⌘ and the wheel or a pinch, zoom between them; a month's name opens that month
  const calEl = $('nb-cal');
  let drag = null;
  const setZoom = (z, month) => {
    if (z === zoom && month === undefined) return;
    zoom = z;
    if (month !== undefined) cursor.m = month;
    else if (z === 'month' && range) { const d = new Date(range[1]); cursor = { y: d.getFullYear(), m: d.getMonth() }; }
    keep(); render();
  };
  calEl.addEventListener('pointerdown', (e) => {
    const d = e.target.closest('.nb-d[data-day]');
    if (!d || d.classList.contains('out') || e.button !== 0) return;
    const t = +d.dataset.day;
    if (e.shiftKey && range) range = [Math.min(range[0], t), Math.max(range[1], t)];
    else if (range && range[0] === t && range[1] === t) range = null;
    else range = [t, t];
    drag = { from: t, moved: false };
    render();
  });
  calEl.addEventListener('pointerover', (e) => {
    if (drag && !(e.buttons & 1)) drag = null;   // (the button let go where no pointerup reached: the drag is over)
    const d = drag && e.target.closest('.nb-d[data-day]');
    if (!d || d.classList.contains('out')) return;
    const t = +d.dataset.day;
    if (t === drag.from && !drag.moved) return;
    drag.moved = true;
    range = [Math.min(drag.from, t), Math.max(drag.from, t)];
    render();
  });
  addEventListener('pointerup', () => { drag = null; });
  calEl.addEventListener('click', (e) => {
    const step = e.target.closest('[data-step]'), z = e.target.closest('[data-zoom]'), m = e.target.closest('[data-month]');
    if (step) {
      const k = +step.dataset.step;
      if (zoom === 'month') { const d = new Date(cursor.y, cursor.m + k, 1); cursor = { y: d.getFullYear(), m: d.getMonth() }; } else cursor.y += k;
      return render();
    }
    if (z) return setZoom(z.dataset.zoom);
    if (m) return setZoom('month', +m.dataset.month);
  });
  let wheelAt = 0;
  calEl.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    if (Date.now() - wheelAt < 350 || Math.abs(e.deltaY) < 2) return;
    wheelAt = Date.now();
    setZoom(e.deltaY > 0 ? 'year' : 'month');
  }, { passive: false });

  $('nb-q').addEventListener('input', (e) => { query = e.target.value; render(); });
  $('nb-clear').onclick = () => { picked.clear(); $('nb-said').textContent = ''; render(); };
  $('nb-del').onclick = () => remove([...picked]);
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
  $('nb-kinds').innerHTML = [['all', T.nb_f_all], ['hl', T.nb_f_hl], ['note', T.nb_f_note], ['ask', T.nb_f_ask], ['new', T.nb_f_new]]
    .map(([k, name]) => `<button type="button" role="radio" data-k="${k}" aria-checked="${k === kind}"${k === 'new' ? ' class="nb-gap"' : ''}>${esc(name)}</button>`).join('');
  $('nb-kinds').onclick = (e) => {
    const b = e.target.closest('button[data-k]');
    if (!b) return;
    kind = b.dataset.k;
    $('nb-kinds').querySelectorAll('button').forEach((x) => x.setAttribute('aria-checked', x === b));
    render();
  };
  $('nb-views').innerHTML = [['list', I.list, T.nb_list], ['cal', I.cal, T.nb_cal]]
    .map(([k, ico, name]) => `<button type="button" role="radio" data-k="${k}" aria-checked="${k === view}" title="${esc(name)}" aria-label="${esc(name)}">${ico}</button>`).join('');
  $('nb-views').onclick = (e) => {
    const b = e.target.closest('button[data-k]');
    if (!b || b.dataset.k === view) return;
    view = b.dataset.k; keep(); render();
  };
  $('nb-del').textContent = T.nb_delete;
  $('nb-clear').textContent = T.nb_clear;
  $('nb-go').textContent = T.nb_go;
  fetch('/api/models').then((r) => r.json()).then((m) => {
    const name = m.askName || m.selectedName;
    $('nb-go').title = name ? T.nb_model.replace('{m}', name) : T.nb_no_model;
  }).catch(() => {});
  load().catch(() => { $('nb-list').innerHTML = `<p class="nb-empty">${esc(T.nb_none)}</p>`; });
})();
