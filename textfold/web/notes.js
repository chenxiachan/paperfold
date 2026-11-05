// The notes page (/notes): every highlight, note and question of the library in rows, a text a row as in the sidebar,
// the one written in last first, folded; open, a note a row in the order they were made; a note open, all of it, its
// passage unfolding to the paragraph it is on as the text reads now (/api/doc). As the calendar, beside the rows (four
// to six), the months one under another, scrolled on their own, the deeper a day the more notes on it; zoomed out (−,
// ⌘ or Ctrl and the wheel, a pinch), each month a small square map, side by side. Days are picked by a click, a drag
// across them, a month's name for the month; ⌘ or Ctrl adds to what is picked, shift runs on from the last day picked;
// the rows then list their notes alone; Today picks today. A note opens there (#n=), goes (with an undo), shows the
// records it went into. What is ticked gathers on the right, whatever days are in view; from there it is deleted, made
// a reading record (/api/record: what I read, was curious about, got, attended to), a document of the library which
// opens, or the same as Markdown for Obsidian (/api/record/obsidian). Each icon says what it is in a tip.
(() => {
  const I18N = window.DR_I18N;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } },
  };
  // the interface's language, the app's (app.js: its menu at the top, the sidebar's): changed there, it changes here
  let ui, T, LOC;
  function setLang() {
    const v = store.get('pf-ui-lang');
    ui = I18N.uiFor(v || I18N.guess());
    T = I18N.t(ui); LOC = I18N.htmlLang(ui);
    document.documentElement.lang = LOC;
  }
  setLang();
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const $ = (id) => document.getElementById(id);
  const fold = (s) => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  const LEVELS = ['Topic', 'Takeaway', 'Key', 'Brief', 'Full'];
  const svg = (d, cls = '') => `<svg${cls ? ` class="${cls}"` : ''} viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const I = {
    chev: svg('<path d="M8 5l5 5-5 5"/>', 'nb-chev'), x: svg('<path d="M6 6l8 8M14 6l-8 8"/>'),
    out: svg('<path d="M8 4h8v8"/><path d="M16 4l-9 9"/><path d="M13 16H4V7"/>'), trash: svg('<path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10"/>'),
    sum: svg('<path d="M5 3.5h10v13H5z"/><path d="M7.5 7h5M7.5 10h5M7.5 13h3"/>'),
    list: svg('<path d="M4 5h12M4 10h12M4 15h12"/>'), cal: svg('<rect x="3.5" y="4.5" width="13" height="12" rx="2"/><path d="M3.5 8.5h13M7 3v3M13 3v3"/>'),
    minus: svg('<path d="M5 10h10"/>'), plus: svg('<path d="M5 10h10M10 5v10"/>'),
  };
  const tipped = (tip) => `data-tip="${esc(tip)}" aria-label="${esc(tip)}"`;
  const VIEW = 'textfold.notes.view';
  const pref = (() => { try { return JSON.parse(store.get(VIEW) || 'null') || {}; } catch { return {}; } })();
  let view = pref.view === 'cal' ? 'cal' : 'list', zoom = pref.zoom === 'year' ? 'year' : 'month';
  const keep = () => store.set(VIEW, JSON.stringify({ view, zoom }));

  let data = { papers: {}, notes: [], summaries: {}, used: {} }, kind = 'all', query = '', loaded = 0;
  const picked = new Set(), openT = new Set(), openN = new Set(), openC = new Set(), docs = {};
  let days = new Set(), anchor = null, drag = null, calSig = '', toastTimer = null;
  const key = (n) => `${n.paper}|${n.id}`;
  const kindOf = (n) => (n.kind === 'ask' ? 'ask' : (n.text || '').trim() ? 'note' : 'hl');   // (notes.py, kind)
  const turns = (n) => (Array.isArray(n.thread) ? n.thread : []).filter((t) => t && t.q);
  const titleOf = (pid) => { const p = data.papers[pid] || {}; return p.name || p.title || pid; };
  const quoteOf = (n) => (n.anchor && n.anchor.quote && n.anchor.quote.exact) || '';
  const hay = (n) => fold([n.text, quoteOf(n), ...turns(n).flatMap((t) => [t.q, t.takeaway]), titleOf(n.paper)].join(' '));
  // a note's row says what the reader wrote, else asked, else the passage marked
  const lineKind = (n) => ((n.text || '').trim() ? 'note' : turns(n).length ? 'ask' : 'hl');
  const lineOf = (n) => (n.text || '').trim() || (turns(n)[0] || {}).q || quoteOf(n) || T.nb_whole;
  const midnight = (t) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const dayOf = (n) => midnight(n.created || 0);
  const plusDays = (t, k) => { const d = new Date(t); d.setDate(d.getDate() + k); return d.getTime(); };
  const between = (a, b) => { const out = []; for (let d = Math.min(a, b); d <= Math.max(a, b); d = plusDays(d, 1)) out.push(d); return out; };
  const fmt = (o) => new Intl.DateTimeFormat(LOC, o);
  const short = (t) => fmt({ month: 'numeric', day: 'numeric' }).format(t);
  const clock = (t) => fmt({ hour: '2-digit', minute: '2-digit' }).format(t);
  const span = (a, b) => (a === b ? short(a) : `${short(a)} – ${short(b)}`);
  const placeOf = (n) => {
    const a = n.anchor || {}, lang = a.lang ? `?lang=${encodeURIComponent(a.lang)}` : '';
    return `/p/${n.paper}${lang}#n=${n.id}${a.unit ? `&u=${encodeURIComponent(a.unit)}` : ''}`;
  };
  const docLink = (pid) => { const p = data.papers[pid] || {}; return `/p/${pid}${p.lang ? `?lang=${p.lang}` : ''}`; };

  // the notes the search and the kind let through; of those, the days picked on the calendar
  function filtered() {
    const q = fold(query.trim());
    return data.notes.filter((n) => (kind === 'all' || (kind === 'new' ? !data.used[key(n)] : kindOf(n) === kind)) && (!q || hay(n).includes(q)));
  }
  const listed = () => (view === 'cal' && days.size ? filtered().filter((n) => days.has(dayOf(n))) : filtered());

  // ── rows ──
  function detailHtml(n) {
    const a = n.anchor || {}, k = key(n), lk = lineKind(n), quote = quoteOf(n), said = a.shown && a.shown.exact;
    const ts = turns(n), out = [];
    if (lk === 'note' || lk === 'hl') ts.forEach((t) => out.push(`<p class="nb-q">${esc(t.q)}</p>`, t.takeaway ? `<p class="nb-a">${esc(t.takeaway)}</p>` : ''));
    else ts.forEach((t, i) => out.push(i ? `<p class="nb-q">${esc(t.q)}</p>` : '', t.takeaway ? `<p class="nb-a">${esc(t.takeaway)}</p>` : ''));
    const ctx = openC.has(k), role = a.unit ? ` role="button" tabindex="0" aria-expanded="${ctx}" ${tipped(T.nb_ctx)}` : '';
    if (said) out.push(`<blockquote class="nb-quote"${role}>${esc(said)}<span class="nb-written">${esc(T.nb_written.replace('{lvl}', LEVELS[a.level] || ''))}</span></blockquote>`);
    else if (quote && lk !== 'hl') out.push(`<blockquote class="nb-quote"${role}>${esc(quote)}</blockquote>`);
    out.push(`<div class="nb-ctx"${ctx ? '' : ' hidden'}></div>`);
    return out.join('');
  }
  function noteHtml(n, oneDay) {
    const k = key(n), open = openN.has(k), t = new Date(n.created || 0);
    const used = (data.used[k] || []).filter((s) => data.summaries[s]).map((s) =>
      `<a class="nb-ico nb-used" href="${esc(docLink(s))}" ${tipped(T.nb_used.replace('{t}', data.summaries[s].title))}>${I.sum}</a>`).join('');
    return `<div class="nb-n${open ? ' open' : ''}${picked.has(k) ? ' picked' : ''}" data-key="${esc(k)}"><div class="nb-nrow">` +
      `<input type="checkbox" class="nb-check" aria-label="${esc(T.nb_pick)}"${picked.has(k) ? ' checked' : ''}>` +
      `<button type="button" class="nb-nline k-${lineKind(n)}" aria-expanded="${open}"><time>${esc(oneDay ? clock(t) : `${short(t)} ${clock(t)}`)}</time>` +
      `<span class="nb-ntext">${esc(lineOf(n))}</span></button><span class="nb-icons">${used}` +
      `<a class="nb-ico" href="${esc(placeOf(n))}" ${tipped(T.nb_there)}>${I.out}</a>` +
      `<button type="button" class="nb-ico nb-trash" ${tipped(T.nb_delete)}>${I.trash}</button></span></div>` +
      (open ? `<div class="nb-ndetail">${detailHtml(n)}</div>` : '') + '</div>';
  }
  function textHtml(pid, ns, oneDay) {
    const open = openT.has(pid), all = ns.every((n) => picked.has(key(n))), some = ns.some((n) => picked.has(key(n)));
    const ds = ns.map(dayOf), sum = (data.papers[pid] || {}).summary;
    return `<div class="nb-t${open ? ' open' : ''}" data-pid="${esc(pid)}"><div class="nb-trow">` +
      `<input type="checkbox" class="nb-check nb-tcheck" ${tipped(T.nb_pick_doc)}${all ? ' checked' : ''}${!all && some ? ' data-some="1"' : ''}>` +
      `<button type="button" class="nb-ttitle" aria-expanded="${open}">${I.chev}${sum ? `<i class="nb-sumico">${I.sum}</i>` : ''}<span>${esc(titleOf(pid))}</span></button>` +
      `<b class="nb-cnt">${ns.length}</b><span class="nb-tdate">${esc(span(Math.min(...ds), Math.max(...ds)))}</span>` +
      `<span class="nb-icons"><a class="nb-ico" href="${esc(docLink(pid))}" ${tipped(T.nb_open)}>${I.out}</a></span></div>` +
      (open ? `<div class="nb-ns">${ns.map((n) => noteHtml(n, oneDay)).join('')}</div>` : '') + '</div>';
  }
  function daysSaid() {
    const ds = [...days].sort((a, b) => a - b);
    if (!ds.length) return '';
    const f = new Date(ds[0]), month = between(ds[0], ds[ds.length - 1]);
    const whole = f.getDate() === 1 && new Date(plusDays(ds[ds.length - 1], 1)).getDate() === 1 && f.getMonth() === new Date(ds[ds.length - 1]).getMonth();
    if (whole && month.length === ds.length) return fmt({ year: 'numeric', month: 'long' }).format(f);
    if (month.length === ds.length) return span(ds[0], ds[ds.length - 1]);
    return ds.length <= 4 ? ds.map(short).join(', ') : `${ds.slice(0, 3).map(short).join(', ')} …`;
  }
  function renderList() {
    const list = listed(), oneDay = view === 'cal' && days.size === 1;
    const by = new Map();   // each text once, the one written in last first; its notes in the order they were made
    for (const n of list) { if (!by.has(n.paper)) by.set(n.paper, []); by.get(n.paper).unshift(n); }
    const every = list.length && list.every((n) => picked.has(key(n))), any = list.some((n) => picked.has(key(n)));
    const said = view === 'cal' ? daysSaid() : '';
    $('nb-listhead').innerHTML = list.length || said ? `<input type="checkbox" class="nb-check nb-master" ${tipped(T.nb_pick_all)}${every ? ' checked' : ''}>` +
      `<b class="nb-cnt">${list.length}</b>${said ? `<span>${esc(said)}</span><button type="button" class="nb-ico nb-undays" ${tipped(T.nb_clear_days)}>${I.x}</button>` : ''}` : '';
    const master = $('nb-listhead').querySelector('.nb-master');
    if (master) master.indeterminate = !every && any;
    $('nb-list').innerHTML = !data.notes.length ? `<p class="nb-empty">${esc(T.nb_empty)}</p>`
      : !list.length ? `<p class="nb-empty">${esc(T.nb_none)}</p>` : [...by].map(([pid, ns]) => textHtml(pid, ns, oneDay)).join('');
    if (!list.length) $('nb-list').classList.add('nb-bare'); else $('nb-list').classList.remove('nb-bare');
    document.querySelectorAll('.nb-tcheck[data-some]').forEach((c) => { c.indeterminate = true; });
    for (const k of openC) { const el = document.querySelector(`.nb-n[data-key="${CSS.escape(k)}"] .nb-ctx`); if (el) context(k, el); }
    renderTray();
  }

  // ── what is picked, gathered on the right whatever days are in view: a text a group, a note a line; the record of
  // the four questions, the same for Obsidian, and deletion made from it ──
  function renderTray() {
    const ns = data.notes.filter((n) => picked.has(key(n))), tray = $('nb-tray');
    const said = tray.querySelector('.nb-said'), keepSaid = said ? [said.className, said.textContent] : null;
    if (!ns.length) {
      tray.innerHTML = `<div class="nb-trayhead"><span>${esc(T.nb_tray)}</span></div><p class="nb-trayempty">${esc(T.nb_tray_empty)}</p>`;
      return;
    }
    const by = new Map();
    for (const n of ns) { if (!by.has(n.paper)) by.set(n.paper, []); by.get(n.paper).unshift(n); }
    tray.innerHTML = `<div class="nb-trayhead"><span>${esc(T.nb_tray)}</span><b class="nb-cnt">${ns.length}</b>` +
      `<button type="button" class="nb-ico nb-trayclear" ${tipped(T.nb_clear)}>${I.x}</button></div><div class="nb-traybody">` +
      [...by].map(([pid, g]) => `<div class="nb-tg"><div class="nb-tgh"><span>${esc(titleOf(pid))}</span><b class="nb-cnt">${g.length}</b>` +
        `<button type="button" class="nb-ico nb-tgx" data-pid="${esc(pid)}" ${tipped(T.nb_unpick)}>${I.x}</button></div>` +
        g.map((n) => `<div class="nb-ti k-${lineKind(n)}" data-key="${esc(key(n))}"><span>${esc(lineOf(n))}</span>` +
          `<button type="button" class="nb-ico nb-tix" ${tipped(T.nb_unpick)}>${I.x}</button></div>`).join('') + '</div>').join('') +
      `</div><div class="nb-trayacts"><button type="button" class="nb-go nb-record" ${tipped(T.nb_record_tip)}>${esc(T.nb_record)}</button>` +
      `<button type="button" class="nb-btn nb-obs">${esc(T.nb_obsidian)}</button>` +
      `<button type="button" class="nb-btn nb-del">${esc(T.nb_delete)}</button></div><div class="nb-said" role="status"></div>`;
    if (keepSaid) { const s2 = tray.querySelector('.nb-said'); [s2.className, s2.textContent] = keepSaid; }
  }
  const items = () => data.notes.filter((n) => picked.has(key(n))).map((n) => ({ paper: n.paper, note: n.id }));
  const say = (text, bad) => { const s2 = $('nb-tray').querySelector('.nb-said'); if (s2) { s2.className = `nb-said${bad ? ' bad' : ''}`; s2.textContent = text; } };
  const postJson = async (path, body) => {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const got = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(got.error || r.status);
    return got;
  };
  // a file saved where the reader says (the app's own dialog, the browser's, else a download), as the reader saves
  async function saveFile(name, text) {
    if (window.desktop && window.desktop.saveFile) return window.desktop.saveFile(name, text);
    if (window.showSaveFilePicker) {
      try {
        const h = await window.showSaveFilePicker({ suggestedName: name, types: [{ description: 'Markdown', accept: { 'text/markdown': ['.md'] } }] });
        const w = await h.createWritable(); await w.write(new Blob([text], { type: 'text/markdown;charset=utf-8' })); await w.close();
        return h.name;
      } catch (x) { if (x.name === 'AbortError') return null; }
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
    a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    return name;
  }
  $('nb-tray').addEventListener('click', async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.matches('.nb-trayclear')) { picked.clear(); return renderList(); }
    if (b.matches('.nb-tgx')) { for (const k of [...picked]) if (k.startsWith(`${b.dataset.pid}|`)) picked.delete(k); return renderList(); }
    if (b.matches('.nb-tix')) { picked.delete(b.closest('.nb-ti').dataset.key); return renderList(); }
    if (b.matches('.nb-del')) return remove([...picked]);
    if (b.matches('.nb-record')) {
      b.disabled = true; say(T.nb_making);
      try { const got = await postJson('/api/record', { items: items(), ui }); location.href = `/p/${got.paper}?lang=${encodeURIComponent(got.lang)}`; }
      catch (x) { say(T.nb_failed.replace('{e}', x.message), true); b.disabled = false; }
      return;
    }
    if (b.matches('.nb-obs')) {
      b.disabled = true;
      try {
        const got = await postJson('/api/record/obsidian', { items: items(), ui });
        const where = await saveFile(got.name, got.text);
        if (where) say(T.nb_saved.replace('{name}', typeof where === 'string' ? where : got.name));
      } catch (x) { say(T.nb_failed.replace('{e}', x.message), true); }
      b.disabled = false;
    }
  });

  // ── the calendar ──
  function perDay() {
    const per = new Map();
    for (const n of filtered()) { const d = dayOf(n); per.set(d, (per.get(d) || 0) + 1); }
    return per;
  }
  function months() {   // from the first month with a note (or five months back) to this one
    const now = new Date(), first = data.notes.reduce((m, n) => Math.min(m, dayOf(n)), Infinity);
    let y = now.getFullYear(), m = now.getMonth() - 5;
    if (first < new Date(y, m, 1).getTime()) { const f = new Date(first); y = f.getFullYear(); m = f.getMonth(); }
    const out = [];
    for (let d = new Date(y, m, 1); d <= now; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) out.push([d.getFullYear(), d.getMonth()]);
    return out;
  }
  const monthDays = (y, m) => between(new Date(y, m, 1).getTime(), plusDays(new Date(y, m + 1, 1).getTime(), -1));
  function calHtml() {
    const per = perDay(), today = midnight(Date.now());
    const lv = (c) => (!c ? 0 : c === 1 ? 1 : c <= 3 ? 2 : c <= 6 ? 3 : 4);
    const long = fmt({ year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });
    const wds = zoom === 'month' ? `<div class="nb-wds">${[...Array(7)].map((_, i) => `<span>${esc(fmt({ weekday: 'narrow' }).format(new Date(2024, 0, 1 + i)))}</span>`).join('')}</div>` : '';
    const blocks = months().map(([y, m]) => {
      const ds = monthDays(y, m), lead = (new Date(y, m, 1).getDay() + 6) % 7;
      const n = ds.reduce((s, d) => s + (per.get(d) || 0), 0);
      const cells = '<span class="nb-d out"></span>'.repeat(lead) + ds.map((d) => {
        const c = per.get(d) || 0, tip = `${long.format(d)}${c ? ` · ${c}` : ''}`;
        return `<button type="button" class="nb-d lv${lv(c)}${d === today ? ' today' : ''}" data-day="${d}" ${tipped(tip)}>${zoom === 'month' ? new Date(d).getDate() : ''}</button>`;
      }).join('');
      const mo = fmt({ month: zoom === 'month' && !/^(zh|ja|ko)/.test(LOC) ? 'long' : 'short' }).format(new Date(y, m, 1));   // (十月 reads as 10月)
      return `<section class="nb-m" data-m="${y}-${m}"><button type="button" class="nb-mname" data-y="${y}" data-mo="${m}" ${tipped(`${T.nb_month_pick}${n ? ` · ${n}` : ''}`)}><b>${esc(mo)}</b><span>${y}</span></button>` +
        `${wds}<div class="nb-mgrid">${cells}</div></section>`;
    }).join('');
    return `<div class="nb-calbar"><button type="button" class="nb-today" ${tipped(T.nb_today_tip)}>${esc(T.nb_today_btn)}</button><span class="nb-zoom">` +
      `<button type="button" class="nb-ico" data-zoom="year" ${tipped(T.nb_zoom_out)}${zoom === 'year' ? ' disabled' : ''}>${I.minus}</button>` +
      `<button type="button" class="nb-ico" data-zoom="month" ${tipped(T.nb_zoom_in)}${zoom === 'month' ? ' disabled' : ''}>${I.plus}</button></span></div>` +
      `<div class="nb-months" data-zoom="${zoom}">${blocks}</div>`;
  }
  function buildCal(at) {   // at: the month to bring to the top (a zoom); else where it was, or this month at first
    const cal = $('nb-cal'), old = cal.querySelector('.nb-months'), was = old ? old.scrollTop : null;
    cal.innerHTML = calHtml();
    const box = cal.querySelector('.nb-months');
    if (at) { const sec = box.querySelector(`.nb-m[data-m="${at}"]`); if (sec) box.scrollTop = sec.offsetTop - box.offsetTop; }
    else box.scrollTop = was === null ? box.scrollHeight : was;
    paintCal();
  }
  function paintCal() {
    const box = $('nb-cal').querySelector('.nb-months');
    if (box) box.classList.toggle('picking', days.size > 0);
    $('nb-cal').querySelectorAll('.nb-d[data-day]').forEach((b) => b.classList.toggle('nb-on', days.has(+b.dataset.day)));
    $('nb-cal').querySelectorAll('.nb-mname').forEach((b) => b.classList.toggle('nb-on', monthDays(+b.dataset.y, +b.dataset.mo).every((d) => days.has(d))));
  }
  const topMonth = () => {
    const box = $('nb-cal').querySelector('.nb-months');
    if (!box) return null;
    const sec = [...box.querySelectorAll('.nb-m')].find((s) => s.offsetTop - box.offsetTop + s.offsetHeight > box.scrollTop + 4);
    return sec && sec.dataset.m;
  };
  function picks() { paintCal(); renderList(); }

  function render() {
    $('nb-views').querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', b.dataset.k === view));
    $('nb-main').classList.toggle('nb-split', view === 'cal');
    $('nb-cal').hidden = view !== 'cal';
    if (view === 'cal') {
      const sig = `${zoom}|${kind}|${query}|${loaded}`;
      if (sig !== calSig) { const at = calSig && calSig.split('|')[0] !== zoom ? topMonth() : null; calSig = sig; buildCal(at); } else paintCal();
    }
    renderList();
  }

  // ── a note's paragraph, as the text reads now, and its section's line; the passage marked in it ──
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

  async function load() {
    data = await fetch('/api/notes').then((r) => r.json());
    loaded += 1;
    for (const k of [...picked]) if (!byKey(k)) picked.delete(k);
    render();
  }
  const post = (pid, body) => fetch(`/api/notes/${encodeURIComponent(pid)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  // notes deleted (the same ones as in the reader), and an undo that puts them back as they were
  async function remove(keys) {
    const gone = keys.map(byKey).filter(Boolean);
    for (const n of gone) await post(n.paper, { op: 'delete', id: n.id });
    for (const n of gone) { picked.delete(key(n)); openN.delete(key(n)); openC.delete(key(n)); }
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

  // ── what a click does ──
  const toggle = (set, k) => { if (set.has(k)) set.delete(k); else set.add(k); };
  $('nb-list').addEventListener('click', (e) => {
    const t = e.target.closest('.nb-t'), n = e.target.closest('.nb-n');
    if (t && e.target.matches('.nb-tcheck')) {
      for (const x of listed().filter((x) => x.paper === t.dataset.pid)) { if (e.target.checked) picked.add(key(x)); else picked.delete(key(x)); }
      return renderList();
    }
    if (t && !n && e.target.closest('.nb-ttitle')) { toggle(openT, t.dataset.pid); return renderList(); }
    if (!n) return;
    const k = n.dataset.key;
    if (e.target.matches('.nb-check')) { toggle(picked, k); return renderList(); }
    if (e.target.closest('.nb-trash')) return remove([k]);
    if (e.target.closest('.nb-nline')) {
      toggle(openN, k);
      const x = byKey(k);   // (a highlight alone: open, its paragraph at once)
      if (x && lineKind(x) === 'hl' && (x.anchor || {}).unit) { if (openN.has(k)) openC.add(k); else openC.delete(k); }
      return renderList();
    }
    if (e.target.closest('.nb-quote[role]')) { toggle(openC, k); return renderList(); }
  });
  $('nb-list').addEventListener('keydown', (e) => {
    const q = e.target.closest('.nb-quote[role]');
    if (q && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggle(openC, q.closest('.nb-n').dataset.key); renderList(); }
  });
  $('nb-listhead').addEventListener('click', (e) => {
    if (e.target.matches('.nb-master')) {
      for (const n of listed()) { if (e.target.checked) picked.add(key(n)); else picked.delete(key(n)); }
      return renderList();
    }
    if (e.target.closest('.nb-undays')) { days = new Set(); anchor = null; picks(); }
  });

  // the calendar: a click picks a day (again, alone: none); a drag, the days across; shift, from the last day picked;
  // ⌘ or Ctrl, added to (or, a day already picked, taken from) what is picked; a month's name, the month
  const calEl = $('nb-cal');
  calEl.addEventListener('pointerdown', (e) => {
    const b = e.target.closest('.nb-d[data-day]');
    if (!b || e.button !== 0) return;
    e.preventDefault();
    const t = +b.dataset.day, add = e.metaKey || e.ctrlKey;
    if (e.shiftKey && anchor !== null) {
      days = new Set([...(add ? days : []), ...between(anchor, t)]);
      return picks();
    }
    if (!add && days.size === 1 && days.has(t)) { days = new Set(); anchor = null; drag = null; return picks(); }
    if (add && days.has(t)) { days.delete(t); drag = null; return picks(); }
    const base = add ? new Set(days) : new Set();
    days = new Set([...base, t]);
    anchor = t;
    drag = { base, from: t };
    picks();
  });
  calEl.addEventListener('pointerover', (e) => {
    if (drag && !(e.buttons & 1)) drag = null;   // (the button let go where no pointerup reached: the drag is over)
    const b = drag && e.target.closest('.nb-d[data-day]');
    if (!b) return;
    days = new Set([...drag.base, ...between(drag.from, +b.dataset.day)]);
    picks();
  });
  addEventListener('pointerup', () => { drag = null; });
  calEl.addEventListener('click', (e) => {
    if (e.target.closest('.nb-today')) {
      const t = midnight(Date.now()), d = new Date(t);
      days = new Set([t]); anchor = t; picks();
      const box = calEl.querySelector('.nb-months'), sec = box && box.querySelector(`.nb-m[data-m="${d.getFullYear()}-${d.getMonth()}"]`);
      if (sec) box.scrollTop = sec.offsetTop - box.offsetTop;
      return;
    }
    const z = e.target.closest('button[data-zoom]'), mn = e.target.closest('.nb-mname');
    if (z) return setZoom(z.dataset.zoom);
    if (!mn) return;
    const md = monthDays(+mn.dataset.y, +mn.dataset.mo), all = md.every((d) => days.has(d));
    if (e.metaKey || e.ctrlKey) { for (const d of md) { if (all) days.delete(d); else days.add(d); } } else days = all && days.size === md.length ? new Set() : new Set(md);
    anchor = md[md.length - 1];
    picks();
  });
  function setZoom(z) {
    if (z === zoom) return;
    zoom = z; keep(); render();
  }
  let wheelAt = 0;
  calEl.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    if (Date.now() - wheelAt < 350 || Math.abs(e.deltaY) < 2) return;
    wheelAt = Date.now();
    setZoom(e.deltaY > 0 ? 'year' : 'month');
  }, { passive: false });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && view === 'cal' && days.size && !e.target.closest('input')) { days = new Set(); anchor = null; picks(); } });

  // a tip names what the pointer rests on (or what has the keyboard), at once, beside it
  const tip = $('nb-tip');
  let tipFor = null, tipTimer = null;
  const hideTip = () => { clearTimeout(tipTimer); tipFor = null; tip.hidden = true; };
  function showTip(el) {
    if (!el.isConnected) return;
    tip.textContent = el.dataset.tip;
    tip.hidden = false;
    const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    const x = Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2));
    const y = r.bottom + 6 + h > innerHeight - 6 ? r.top - h - 6 : r.bottom + 6;
    tip.style.left = `${x}px`; tip.style.top = `${y}px`;
  }
  document.addEventListener('pointerover', (e) => {
    const el = e.target.closest && e.target.closest('[data-tip]');
    if (el === tipFor) return;
    hideTip();
    if (!el) return;
    tipFor = el;
    tipTimer = setTimeout(() => showTip(el), drag ? 0 : 250);
  });
  document.addEventListener('focusin', (e) => { if (e.target.matches('[data-tip]:focus-visible')) { tipFor = e.target; showTip(e.target); } });
  document.addEventListener('focusout', hideTip);
  addEventListener('scroll', hideTip, true);
  document.addEventListener('pointerdown', (e) => { if (!e.target.closest('.nb-d')) hideTip(); }, true);

  $('nb-q').addEventListener('input', (e) => { query = e.target.value; render(); });
  // the words on the page, in the interface's language (again when it changes)
  function labels() {
    document.title = `${T.nb_title} · TextFold`;
    $('nb-title').textContent = T.nb_title;
    $('nb-q').placeholder = T.nb_search; $('nb-q').setAttribute('aria-label', T.nb_search);
    $('nb-kinds').innerHTML = [['all', T.nb_f_all], ['hl', T.nb_f_hl], ['note', T.nb_f_note], ['ask', T.nb_f_ask], ['new', T.nb_f_new]]
      .map(([k, name]) => `<button type="button" role="radio" data-k="${k}" aria-checked="${k === kind}"${k === 'new' ? ` class="nb-gap" ${tipped(T.nb_f_new_tip)}` : ''}>${esc(name)}</button>`).join('');
    $('nb-kinds').onclick = (e) => {
      const b = e.target.closest('button[data-k]');
      if (!b) return;
      kind = b.dataset.k;
      $('nb-kinds').querySelectorAll('button').forEach((x) => x.setAttribute('aria-checked', x === b));
      render();
    };
    $('nb-views').innerHTML = [['list', I.list, T.nb_list], ['cal', I.cal, T.nb_cal]]
      .map(([k, ico, name]) => `<button type="button" role="radio" data-k="${k}" aria-checked="${k === view}" ${tipped(name)}>${ico}</button>`).join('');
    $('nb-views').onclick = (e) => {
      const b = e.target.closest('button[data-k]');
      if (!b || b.dataset.k === view) return;
      view = b.dataset.k; keep(); render();
    };
  }
  labels();
  document.addEventListener('tf-lang', () => { setLang(); labels(); calSig = ''; render(); });
  load().catch(() => { $('nb-list').innerHTML = `<p class="nb-empty">${esc(T.nb_none)}</p>`; });
})();
