// The app around the reader: the sidebar of papers, the landing form, settings, and generation jobs.
// On a reader page it exposes window.DRApp so the reader's language menu can generate a language.
(() => {
  'use strict';
  const I18N = window.DR_I18N;
  const bootEl = document.getElementById('boot');
  const BOOT = bootEl ? JSON.parse(bootEl.textContent) : {};
  const readerEl = document.getElementById('paper-data');
  const PAPER = readerEl ? JSON.parse(readerEl.textContent).meta : null;   // the paper open in the reader, if any
  const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } } };
  const SHORT = { en: 'EN', zh: '中', 'zh-Hant': '繁', ja: '日', ko: '한', es: 'ES', fr: 'FR', de: 'DE', pt: 'PT', it: 'IT', ru: 'RU', hi: 'हि' };
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const h = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const api = (path, body) => fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || r.statusText); return d; });

  // the interface's language, the reader's own (settings; else the browser's), apart from the language a paper is read in
  const UI_KEY = 'pf-ui-lang';
  let uiLang = [store.get(UI_KEY), I18N.guess()].find((l) => l && I18N.NATIVE[l]) || 'en';
  function setUiLang(code) {
    if (!I18N.NATIVE[code]) return;
    uiLang = code;
    store.set(UI_KEY, code);
    renderSidebar();
    if (landing) renderLanding();
    if (window.__reader && window.__reader.setUi) window.__reader.setUi(code);
  }
  let papers = BOOT.papers || [];
  let jobs = BOOT.jobs || [];
  let modelName = BOOT.model || '';       // the model generations use, as the settings name it
  const t = () => I18N.t(uiLang);

  // ── sidebar ──────────────────────────────────────────────────────────
  const side = document.getElementById('sidebar');
  const MARK = '<svg viewBox="0 0 20 20" aria-hidden="true"><rect class="m1" x="2" y="3" width="16" height="2.4" rx="1.2"/><rect class="m2" x="2" y="8.8" width="11" height="2.4" rx="1.2"/><rect class="m3" x="2" y="14.6" width="5" height="2.4" rx="1.2"/></svg>';
  const LIST = '<svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="3.5" width="15" height="13" rx="2.5"/><path d="M7.5 3.5v13"/></svg>';
  // a paper opens in the language last read in, else the interface's, else its first
  const pick = (p) => [store.get('dr-lang'), uiLang].find((l) => l && p.langs.includes(l)) || p.langs[0] || 'en';
  const modelLabel = () => modelName;
  const live = (j) => j.status === 'queued' || j.status === 'running';
  function jobFor(pid) { return jobs.find((j) => j.pid === pid && live(j)); }
  function pct(j) { return j.total ? Math.round((100 * j.done) / j.total) : (j.stage === 'done' ? 100 : 6); }
  // where a job is: its stage and count, or that it is stopping
  const stageOf = (j, T) => (j.stopping ? T.stopping : `${T.stages[j.stage] || j.stage}${j.total ? ` ${j.done}/${j.total}` : ''}`);
  const stopBtn = (j, T) => `<button type="button" class="sb-stop" data-stop="${j.id}" title="${esc(T.stop)}" aria-label="${esc(T.stop)}"${j.stopping ? ' disabled' : ''}><i></i></button>`;
  const progress = (j, T) => `<span class="sb-prog"><i style="width:${pct(j)}%"></i></span><span class="sb-stage">${esc(stageOf(j, T))} · ${esc(I18N.NATIVE[j.lang])}</span>`;
  function renderSidebar() {
    const T = t();
    const listed = new Set(papers.map((p) => p.id));
    const pending = jobs.filter((j) => !listed.has(j.pid) && live(j));
    const item = (p) => {
      const j = jobFor(p.id);
      const title = (p.titles && p.titles[uiLang]) || p.title;
      const langs = p.langs.map((l) => `<span${l === uiLang ? ' class="on"' : ''}>${SHORT[l] || l}</span>`).join('');
      const active = PAPER && PAPER.id === p.id;
      const unfinished = !j && !p.langs.length;   // stopped (or failed) before its first language: a click goes on with it
      return `<div class="sb-row"><a class="sb-item${active ? ' active' : ''}${unfinished ? ' unfinished' : ''}" href="${unfinished ? '#' : `/p/${p.id}?lang=${pick(p)}`}"${unfinished ? ` data-resume="${p.id}"` : ''} title="${esc(p.title)}">
        <span class="sb-t">${esc(title)}</span><span class="sb-m"><span class="sb-id">${p.id}</span><span class="sb-langs">${langs}</span></span>
        ${j ? progress(j, T) : unfinished ? `<span class="sb-stage">${esc(T.unfinished)}</span>` : ''}</a>` +
        (j ? stopBtn(j, T) : `<button type="button" class="sb-del" data-del="${p.id}" title="${esc(T.del_paper)}" aria-label="${esc(T.del_paper)}">×</button>`) + '</div>';
    };
    const pend = (j) => `<div class="sb-row"><div class="sb-item pending"><span class="sb-t">${esc(j.title || j.pid)}</span>` +
      `<span class="sb-m"><span class="sb-id">${j.pid}</span></span>${progress(j, T)}</div>${stopBtn(j, T)}</div>`;
    side.innerHTML = `
      <div class="sb-head"><a class="sb-brand" href="/">${MARK}<span>PaperFold</span></a>
        <button type="button" class="sb-toggle" aria-label="${esc(T.collapse)}" title="${esc(T.collapse)}">‹</button></div>
      <div class="sb-rail">
        <a class="rail-btn rail-home" href="/" title="${esc(T.home)}">${MARK}</a>
        <button type="button" class="rail-btn rail-open" title="${esc(T.expand)}">${LIST}</button>
        <a class="rail-btn" href="/" title="${esc(T.new_paper)}">＋</a>
        <button type="button" class="rail-btn rail-settings" title="${esc(T.settings)}">⚙</button>
      </div>
      <a class="sb-new" href="/">＋ ${esc(T.new_paper)}</a>
      <div class="sb-label">${esc(T.papers)}</div>
      <nav class="sb-list">${pending.map(pend).join('')}${papers.map(item).join('') || (pending.length ? '' : `<div class="sb-empty">${esc(T.empty)}</div>`)}</nav>
      <div class="sb-foot"><button type="button" class="sb-settings">⚙ ${esc(T.settings)}</button><div class="sb-model">${esc(modelLabel())}</div></div>`;
    side.querySelector('.sb-toggle').onclick = () => setCollapsed(true);
    side.querySelector('.rail-open').onclick = () => setCollapsed(false);
    side.querySelectorAll('.sb-settings, .rail-settings').forEach((b) => { b.onclick = openSettings; });
    side.querySelectorAll('.sb-del').forEach((b) => { b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); deletePaper(b.dataset.del); }; });
    side.querySelectorAll('.sb-stop').forEach((b) => { b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); stopJob(b.dataset.stop); }; });
    side.querySelectorAll('[data-resume]').forEach((a) => { a.onclick = (e) => { e.preventDefault(); resume(a.dataset.resume); }; });
    // folded to a rail (over a paper): a dot on the list button while something generates
    side.querySelector('.rail-open').classList.toggle('busy', jobs.some(live));
  }
  // a job stopped from anywhere (the sidebar, the landing's card, the toast over a paper): what is written stays cached
  async function stopJob(id) {
    try {
      const j = await api('/api/jobs/stop', { id });
      jobs = [...jobs.filter((x) => x.id !== id), j];
      const cb = watchers.get(id);
      if (cb) cb(j);
    } catch { /* finished meanwhile */ }
    renderSidebar(); startPolling();
  }
  // an unfinished paper goes on in the language it was last asked for (else the reader's), in the background
  function resume(pid) {
    const last = [...jobs].reverse().find((j) => j.pid === pid);
    const lang = (last && last.lang) || [store.get('dr-lang'), uiLang].find((l) => l && I18N.NATIVE[l]) || 'en';
    submit(pid, lang, false, () => {}).catch(() => {});
  }
  // a paper off the list, after a prompt that says what goes with it; the server moves its folder to papers/.trash
  async function deletePaper(pid) {
    const T = t(), p = papers.find((x) => x.id === pid);
    if (!p) return;
    const title = (p.titles && p.titles[uiLang]) || p.title;
    if (!confirm(T.del_confirm.replace('{title}', title).replace('{n}', p.notes || 0))) return;
    try { papers = await api('/api/papers/delete', { paper: pid }); }
    catch (err) { alert(err.message === 'busy' ? T.del_busy : err.message); return; }
    if (PAPER && PAPER.id === pid) { location.href = '/'; return; }
    renderSidebar();
  }
  function setCollapsed(c) {
    side.classList.toggle('collapsed', c);
    document.documentElement.classList.toggle('sb-open', !c);
    if (!PAPER) store.set('dr-sidebar', c ? '1' : '0');
  }
  // over a paper the sidebar folds to a rail and opens over the page; on the landing it stays open beside the form
  if (PAPER) {
    side.classList.add('collapsed');
    document.addEventListener('click', (e) => { if (!side.classList.contains('collapsed') && !side.contains(e.target)) setCollapsed(true); });
  } else if (store.get('dr-sidebar') === '1' || innerWidth < 720) setCollapsed(true);
  else document.documentElement.classList.add('sb-open');

  // ── jobs ─────────────────────────────────────────────────────────────
  const watchers = new Map();   // job id -> callback(job)
  let polling = null;
  async function poll() {
    polling = null;
    try {
      const before = new Map(jobs.map((j) => [j.id, j.status]));
      jobs = await api('/api/jobs');
      let finished = false;
      for (const j of jobs) {
        const cb = watchers.get(j.id);
        if (cb) cb(j);
        if (before.get(j.id) !== j.status && (j.status === 'done' || j.status === 'error' || j.status === 'stopped')) finished = true;
      }
      if (finished) papers = await api('/api/papers');
      renderSidebar();
    } catch { /* the server restarted; try again */ }
    if (jobs.some(live) || watchers.size) polling = setTimeout(poll, 1200);
  }
  function startPolling() { if (!polling) polling = setTimeout(poll, 400); }
  async function submit(paper, lang, force, onUpdate) {
    const job = await api('/api/generate', { paper, lang, force: !!force });
    watchers.set(job.id, (j) => { onUpdate(j); if (j.status === 'done' || j.status === 'error' || j.status === 'stopped') watchers.delete(j.id); });
    jobs = [...jobs.filter((j) => j.id !== job.id), job];
    renderSidebar(); onUpdate(job); startPolling();
    return job;
  }
  // OpenRouter's consent page. In the browser: this tab goes there and comes back with the key. Inside the app: the
  // system browser (where the reader is signed in) goes there, and the app waits for the key, then offers the models.
  async function connectOpenRouter(back) {
    const desktop = !!window.desktop;
    const r = await api('/api/openrouter/start', { back, desktop });
    if (!desktop) { location.href = r.url; return; }
    window.desktop.openExternal(r.url);
    for (let k = 0; k < 150; k++) {   // five minutes for a person in another window
      await new Promise((res) => setTimeout(res, 2000));
      if ((await api('/api/openrouter/minted')).minted) { openSettings({ minted: true }); return; }
    }
  }
  const errText = (msg) => (msg === 'no-html' ? t().no_html : msg === 'bad-ref' ? t().bad_ref : msg === 'no-model' ? t().no_model
    : msg === 'not-markdown' || msg === 'empty' ? t().md_only : msg === 'no-fulltext' ? t().no_fulltext : msg);

  // ── on a reader page: generate a language, or regenerate the current one ──
  if (PAPER) {
    const toast = h('div', 'gen-toast'); toast.hidden = true; document.body.append(toast);
    // a Markdown file dropped on a paper's page: stored, then generated from the landing (?start=)
    let over = 0;
    const hasFile = (e) => [...((e.dataTransfer && e.dataTransfer.types) || [])].includes('Files');
    const say = (msg, ms) => { toast.hidden = false; toast.textContent = msg; if (ms) setTimeout(() => { toast.hidden = true; }, ms); };
    document.addEventListener('dragenter', (e) => { if (hasFile(e)) { over++; say(t().drop_md); } });
    document.addEventListener('dragleave', () => { if (--over <= 0) { over = 0; if (toast.textContent === t().drop_md) toast.hidden = true; } });
    document.addEventListener('dragover', (e) => { if (hasFile(e)) e.preventDefault(); });
    document.addEventListener('drop', async (e) => {
      if (!e.dataTransfer.files.length) return;
      e.preventDefault(); over = 0;
      const file = e.dataTransfer.files[0];
      if (!/\.(md|markdown|mdown|txt)$/i.test(file.name)) { say(t().md_only, 3000); return; }
      try {
        const r = await api('/api/import', { name: file.name, text: await file.text() });
        location.href = `/?start=${encodeURIComponent(r.paper)}&t=${encodeURIComponent(r.title)}`;
      } catch (x) { say(errText(x.message), 4000); }
    });
    // a generation of this paper in the toast: its stage and a stop button; done, the page again, at the paragraph being
    // read (the reader picks it up from sessionStorage). `note` says why the page is here before its levels are.
    function toastFor(lang, note) {
      const T = t(), name = I18N.NATIVE[lang];
      toast.hidden = false;
      toast.innerHTML = `<b>${esc(T.generating)} · ${esc(name)}</b><span class="g-stage">${esc(T.stages.queued)}</span>` +
        `<span class="sb-prog"><i style="width:4%"></i></span>${note ? `<span class="g-note">${esc(note)}</span>` : ''}`;
      const closable = (head, line) => {
        toast.innerHTML = `<b>${esc(head)} · ${esc(name)}</b><span class="g-stage">${esc(line)}</span><button type="button" class="g-x" aria-label="${esc(t().close)}">×</button>`;
        toast.querySelector('.g-x').onclick = () => { toast.hidden = true; };
      };
      const update = (j) => {
        const T2 = t();
        if (j.status === 'error') { closable(T2.failed, errText(j.error)); return; }
        if (j.status === 'stopped') { closable(T2.stopped, ''); return; }
        if (!toast.querySelector('.g-stop')) {
          toast.insertAdjacentHTML('beforeend', `<button type="button" class="g-stop">${esc(T2.stop)}</button>`);
          toast.querySelector('.g-stop').onclick = () => stopJob(j.id);
        }
        toast.querySelector('.g-stage').textContent = stageOf(j, T2);
        toast.querySelector('.g-stop').disabled = !!j.stopping;
        toast.querySelector('.sb-prog i').style.width = `${pct(j)}%`;
        if (j.status === 'done') reopen(j.lang);
      };
      update.fail = (e) => closable(t().failed, errText(e.message));
      return update;
    }
    function reopen(lang) {
      const r = document.getElementById('doc').getBoundingClientRect(), R = window.__reader;
      let u = null;
      for (const f of [0.3, 0.36, 0.42, 0.24]) {   // the reading line, or near it when it falls between paragraphs
        const at = document.elementFromPoint(r.left + Math.min(r.width / 2, 320), innerHeight * f);
        u = at && at.closest('.u[data-u]');
        if (u) break;
      }
      try { if (u) sessionStorage.setItem('pf-keep', JSON.stringify({ pid: PAPER.id, uid: u.dataset.u, top: u.getBoundingClientRect().top, level: R && R.level })); } catch { /* private window */ }
      location.href = `/p/${PAPER.id}?lang=${encodeURIComponent(lang)}`;
    }
    window.DRApp = {
      onLang() { renderSidebar(); },
      generate(lang, force) {
        const T = t(), name = I18N.NATIVE[lang];
        if (force && !confirm(`${T.regen} · ${name}?`)) return;
        const update = toastFor(lang);
        submit(PAPER.id, lang, force, update).catch(update.fail);
      },
    };
    api('/api/models').then((d) => { modelName = d.selectedName || ''; renderSidebar(); }).catch(() => {});
    api('/api/papers').then((p) => { papers = p; renderSidebar(); }).catch(() => {});
    api('/api/jobs').then((j) => {
      jobs = j;
      renderSidebar();
      // a generation of this paper under way (the landing opens a paper as soon as it can be read): followed here
      const mine = jobFor(PAPER.id);
      if (mine) {
        const update = toastFor(mine.lang, t().read_first);
        watchers.set(mine.id, (x) => { update(x); if (!live(x)) watchers.delete(x.id); });
        update(mine);
      }
      if (j.some(live)) startPolling();
    }).catch(() => {});
  }

  // ── the landing ──────────────────────────────────────────────────────
  const landing = document.getElementById('landing');
  function renderLanding() {
    const T = t();
    document.documentElement.lang = I18N.htmlLang(uiLang);
    document.getElementById('h-tagline').textContent = T.hero;
    document.getElementById('ref').placeholder = T.placeholder;
    document.getElementById('ref').setAttribute('aria-label', T.placeholder);
    document.getElementById('l-lang').textContent = T.read_in;
    const ui = document.getElementById('ui-lang');
    ui.value = uiLang;
    document.getElementById('ui-lang-box').title = T.ui_lang;
    ui.setAttribute('aria-label', T.ui_lang);
    document.getElementById('go-t').textContent = T.generate;
    document.getElementById('sources').textContent = T.sources;
    document.getElementById('dropzone-t').textContent = T.drop_zone;
    document.getElementById('open-settings').textContent = T.settings;
    document.getElementById('model-label').textContent = modelLabel();
    renderConnect();
  }
  // No model yet (no agent on this computer, no provider): the ways in, on the landing itself. OpenRouter's one-click
  // authorisation (free models); the ChatGPT plan through the local bridge, started from here; or the settings.
  let bridgeStarting = false;
  function renderConnect() {
    const box = document.getElementById('connect');
    if (!box) return;
    box.hidden = !!modelName;
    if (box.hidden) return;
    const T = t(), br = BOOT.bridge || {};
    box.innerHTML = `<div class="cn-t">${esc(T.cn_title)}</div><p>${esc(T.cn_sub)}</p><div class="cn-ways">` +
      `<button type="button" class="primary cn-or">${esc(T.cn_or)}</button>` +
      (br.node || br.running ? `<button type="button" class="cn-gpt"${bridgeStarting ? ' disabled' : ''}>${esc(bridgeStarting ? T.bridge_starting : T.cn_gpt)}</button>` : '') +
      `</div><button type="button" class="linkbtn cn-more">${esc(T.cn_more)}</button>`;
    box.querySelector('.cn-or').onclick = async (e) => { e.target.disabled = true; await connectOpenRouter('/'); e.target.disabled = false; };
    box.querySelector('.cn-more').onclick = () => openSettings({ add: true });
    const g = box.querySelector('.cn-gpt');
    if (g) g.onclick = async () => {
      bridgeStarting = true; renderConnect();
      try { await api('/api/bridge/start', {}); } catch (x) { bridgeStarting = false; renderConnect(); return; }
      for (let k = 0; k < 150 && bridgeStarting; k++) {   // up to 5 minutes: a ChatGPT sign-in may be under way
        await new Promise((r) => setTimeout(r, 2000));
        if ((await api('/api/bridge')).running) break;
      }
      bridgeStarting = false;
      const d = await api('/api/models');
      modelName = d.selectedName || '';
      renderSidebar(); renderLanding();
    };
  }
  if (landing) {
    const sel = document.getElementById('lang');
    for (const code of I18N.CODES) sel.append(Object.assign(h('option'), { value: code, textContent: I18N.NATIVE[code] }));
    sel.value = [store.get('dr-lang'), uiLang].find((l) => l && I18N.NATIVE[l]);
    sel.onchange = () => { store.set('dr-lang', sel.value); store.set('dr-lang-picked', '1'); };
    // the interface language, top right; until a reader picks the language to read in, that follows it
    const ui = document.getElementById('ui-lang');
    for (const code of I18N.CODES) ui.append(Object.assign(h('option'), { value: code, textContent: I18N.NATIVE[code] }));
    ui.value = uiLang;
    ui.onchange = () => {
      setUiLang(ui.value);
      if (!store.get('dr-lang-picked')) sel.value = ui.value;
    };
    document.getElementById('open-settings').onclick = openSettings;
    const form = document.getElementById('newform'), err = document.getElementById('err'), card = document.getElementById('jobcard');
    const fail = (msg) => { err.textContent = msg; err.hidden = false; };
    // a paper (an arXiv link, or a document just opened) into the job card, then into the reader
    let latest = null;   // the paper the card shows: started last. One started before keeps going in the sidebar.
    async function start(ref, label, langOf) {
      const lang = langOf || sel.value, mine = {};
      latest = mine;
      card.hidden = false;
      try {
        await submit(ref, lang, false, (j) => {
          if (latest !== mine) return;
          const T = t(), name = esc(label || j.title || j.pid);
          if (j.status === 'error') { card.innerHTML = `<div class="jc-t">${esc(T.failed)} · ${name}</div><div class="jc-e">${esc(errText(j.error))}</div>`; return; }
          if (j.status === 'stopped') {
            card.innerHTML = `<div class="jc-head"><div class="jc-t">${name} · ${esc(I18N.NATIVE[j.lang])}</div><button type="button" class="jc-go">${esc(T.resume)}</button></div>
              <div class="jc-s">${esc(T.stopped)}</div>`;
            card.querySelector('.jc-go').onclick = () => start(j.pid, label || j.title, j.lang);
            return;
          }
          card.innerHTML = `<div class="jc-head"><div class="jc-t">${name} · ${esc(I18N.NATIVE[j.lang])}</div>
              <button type="button" class="jc-stop"${j.stopping ? ' disabled' : ''}>${esc(T.stop)}</button></div>
            <div class="jc-s">${esc(stageOf(j, T))}</div>
            <span class="sb-prog"><i style="width:${pct(j)}%"></i></span>`;
          card.querySelector('.jc-stop').onclick = () => stopJob(j.id);
          // readable (parsed): the paper opens in its own words now, and its levels come in while it is read
          if (j.status === 'done' || (j.readable && j.status === 'running')) location.href = `/p/${j.pid}?lang=${encodeURIComponent(j.lang)}`;
        });
      } catch (x) { card.hidden = true; fail(errText(x.message)); }
    }
    form.onsubmit = async (e) => {
      e.preventDefault();
      err.hidden = true;
      const ref = document.getElementById('ref').value.trim();
      if (!/\d{4}\.\d{4,5}|PMC\d{4,}|PPR\d{4,}|10\.\d{4,9}\/\S|wikipedia\.org\//i.test(ref)) { fail(t().bad_ref); return; }   // arXiv, Europe PMC, a DOI, Wikipedia
      if (!modelName) { fail(t().no_model); return; }   // connect a model first (the card below)
      start(ref);
    };
    // a Markdown file, from the bar's mark or dropped anywhere on the page: stored by the server, then generated
    async function openFile(file) {
      err.hidden = true;
      if (!file) return;
      if (!/\.(md|markdown|mdown|txt)$/i.test(file.name)) { fail(t().md_only); return; }
      if (!modelName) { fail(t().no_model); return; }
      try {
        const r = await api('/api/import', { name: file.name, text: await file.text() });
        start(r.paper, r.title);
      } catch (x) { fail(errText(x.message)); }
    }
    const fileIn = document.getElementById('file'), zone = document.getElementById('dropzone');
    zone.onclick = () => fileIn.click();
    fileIn.onchange = () => { openFile(fileIn.files[0]); fileIn.value = ''; };
    let depth = 0;   // dragenter and dragleave fire for every child the file passes over
    const dropping = (on) => { zone.classList.toggle('dragging', on); document.getElementById('dropzone-t').textContent = on ? t().drop_md : t().drop_zone; };
    document.addEventListener('dragenter', (e) => { if ([...e.dataTransfer.types].includes('Files')) { depth++; dropping(true); } });
    document.addEventListener('dragleave', () => { if (--depth <= 0) { depth = 0; dropping(false); } });
    document.addEventListener('dragover', (e) => { if ([...e.dataTransfer.types].includes('Files')) e.preventDefault(); });
    document.addEventListener('drop', (e) => {
      if (!e.dataTransfer.files.length) return;
      e.preventDefault(); depth = 0; dropping(false);
      openFile(e.dataTransfer.files[0]);
    });
    renderLanding();
    // a file dropped on a paper's page comes here, stored already: generate it (?start=<id>&t=<title>)
    const started = new URLSearchParams(location.search);
    if (started.get('start')) {
      history.replaceState(null, '', '/');
      if (modelName) start(started.get('start'), started.get('t')); else fail(t().no_model);
    }
    if (jobs.some(live)) startPolling();
  }

  // ── settings: the model, the agents on this computer, the API providers (ThoughtDAG's model access) ──
  async function openSettings(opts) {
    let data = await api('/api/models');
    let form = null;          // the provider being added or edited: {key?, preset, name, base, api_key, found, picked}
    let test = null;          // the last connection test
    let bridgeStarting = false;
    const dlg = h('dialog', 'settings'); document.body.append(dlg);
    const T = () => t();
    const host = (u) => { try { return new URL(u).host; } catch { return u; } };
    const groupName = (g) => (data.agents.find((a) => a.runtime === g) || {}).label || (data.providers.find((p) => p.key === g) || {}).name || g;

    function modelSection() {
      const t = T();
      if (!data.models.length) return `<p class="st-note">${esc(t.st_none)}</p>`;
      const groups = [];
      for (const m of data.models) {
        let g = groups.find((x) => x.key === m.group);
        if (!g) groups.push(g = { key: m.group, agent: m.kind === 'agent', items: [] });
        g.items.push(m);
      }
      const opts = groups.map((g) => `<optgroup label="${esc(groupName(g.key))}${g.agent ? ' · agent' : ''}">${g.items.map((m) =>
        `<option value="${esc(m.id)}"${m.id === data.selected ? ' selected' : ''}>${esc(m.name)}</option>`).join('')}</optgroup>`).join('');
      const res = test ? `<div class="st-test ${test.ok ? 'ok' : 'bad'}">${test.ok ? `✓ ${esc(t.test_ok)} · ${test.seconds}s` : `✕ ${esc(test.error || '')}`}</div>` : '';
      return `<div class="st-row"><select name="model" class="st-model">${opts}</select><button type="button" class="st-testbtn">${esc(t.test)}</button></div>${res}`;
    }

    function agentSection() {
      const t = T();
      const found = data.agents.filter((a) => a.path);
      const missing = data.agents.filter((a) => !a.path && !a.error);
      const rows = found.map((a) => `<div class="st-agent ${a.runnable ? 'ok' : 'warn'}"><i></i><b>${esc(a.label)}</b><span>${esc(a.version || '')}</span>
        <em>${a.runnable ? esc(t.st_models.replace('{n}', a.models)) : esc(t.st_unsupported)}</em><code title="${esc(a.path)}">${esc(a.binary)}</code></div>`).join('');
      return `${rows}${missing.length ? `<p class="st-note">${esc(t.st_notfound)}: ${missing.map((a) => esc(a.label)).join(', ')}</p>` : ''}
        <div class="st-row end"><button type="button" class="st-scan"${data.scanning ? ' disabled' : ''}>${esc(data.scanning ? t.st_scanning : t.st_rescan)}</button></div>`;
    }

    function providerSection() {
      const t = T();
      const src = (p) => p.source === 'thoughtdag' ? t.st_from_td : p.source === 'env' ? t.st_from_env : p.source === 'bridge' ? t.st_auto : t.st_added;
      const rows = data.providers.map((p) => `<div class="st-prov"><b>${esc(p.name)}</b><span class="st-src ${p.source}">${esc(src(p))}</span>
        <span class="st-host">${esc(host(p.base))}</span><em>${esc(t.st_models.replace('{n}', p.models.length))}</em>
        ${p.source === 'ui' ? `<button type="button" class="linkbtn st-edit" data-key="${esc(p.key)}">${esc(t.st_edit)}</button><button type="button" class="linkbtn st-del" data-key="${esc(p.key)}">${esc(t.st_remove)}</button>` : ''}</div>`).join('');
      const td = '';   // (ThoughtDAG's .env is no longer read: its providers were copied into these settings once, v0.8.3)
      const br = data.bridge || {};
      const bridgeRow = br.running || data.providers.some((p) => p.preset === 'chatgpt-bridge') ? '' : `<div class="st-prov st-bridgerow"><b>${esc(t.bridge_name)}</b>
        <span class="st-host">127.0.0.1:10531</span><em>${esc(bridgeStarting ? t.bridge_starting : t.bridge_off)}</em>
        ${br.node && !bridgeStarting ? `<button type="button" class="linkbtn st-bridgego">${esc(t.bridge_start)}</button>` : ''}</div>`;
      return `${rows}${bridgeRow}${td}${form ? providerForm() : `<div class="st-row end"><button type="button" class="st-add">＋ ${esc(t.st_add)}</button></div>`}`;
    }

    function providerForm() {
      const t = T();
      const preset = data.presets.find((p) => p.id === form.preset) || {};
      const opts = data.presets.map((p) => `<option value="${p.id}"${p.id === form.preset ? ' selected' : ''}>${esc(p.id === 'chatgpt-bridge' ? t.bridge_name : (p.name || 'Custom'))}${p.region ? ` (${p.region})` : ''}</option>`).join('');
      // the models found: the picked ones first (a long list, such as OpenRouter's, would bury them), then as listed;
      // a search box narrows the list as you type, without losing what is ticked
      const found = form.found ? [...form.found].sort((a, b) => form.picked.includes(b.id) - form.picked.includes(a.id)) : null;
      const list = found && !found.length ? `<p class="st-note warn">${esc(t.st_none)}</p>` : found ? `<div class="st-label">${esc(t.st_pick)} <span class="st-count"></span></div>` +
        (found.length > 12 ? `<input type="search" class="st-search" placeholder="${esc(t.st_search)}" autocomplete="off">` : '') +
        `<div class="st-pick">${found.map((m) =>
        `<label data-id="${esc(m.id.toLowerCase())}"><input type="checkbox" value="${esc(m.id)}"${form.picked.includes(m.id) ? ' checked' : ''}>${esc(m.id)}${m.free ? ` <em class="free">${esc(t.free)}</em>` : ''}${(preset.recommend || []).includes(m.id) ? ' <em>★</em>' : ''}</label>`).join('')}</div>` : '';
      // OpenRouter: a key made by one authorisation (OAuth PKCE) instead of pasting one
      const oauth = form.preset === 'openrouter' && !form.minted ? `<div class="st-oauth"><p>${esc(t.or_hint)}</p><button type="button" class="primary pf-oauth">${esc(t.or_button)}</button></div>` : '';
      const minted = form.minted ? `<p class="st-note ok">${esc(t.or_minted)}</p>` : '';
      // the ChatGPT plan through the local bridge: whether it runs, and starting it
      const b = form.bridge;
      const bridge = !preset.bridge ? '' : !b ? `<p class="st-note">…</p>` : b.running
        ? `<div class="st-bridge on"><i></i>${esc(t.bridge_on.replace('{n}', b.models.length))}</div><p class="st-note">${esc(t.bridge_hint)}</p>`
        : `<div class="st-bridge"><i></i><span>${esc(form.bridgeStarting ? t.bridge_starting : t.bridge_off)}</span>${b.node && !form.bridgeStarting ? `<button type="button" class="pf-bridge">${esc(t.bridge_start)}</button>` : ''}</div>
          <p class="st-note">${esc(t.bridge_hint)}</p>${b.node ? '' : `<p class="st-note warn">${esc(t.bridge_no_node)}</p>`}
          <div class="st-cmd"><code>npx openai-oauth</code><button type="button" class="linkbtn pf-copy">${esc(t.copy)}</button></div>`;
      return `<div class="st-form">
        <label>${esc(t.st_preset)}<select class="pf-preset">${opts}</select></label>${oauth}${minted}${bridge}
        ${form.preset === 'custom' ? `<label>${esc(t.st_name)}<input class="pf-name" value="${esc(form.name || '')}"></label>` : ''}
        <label>${esc(t.base_url)}<input class="pf-base" value="${esc(form.base || '')}" placeholder="https://…/v1"></label>
        ${preset.nokey || form.minted ? '' : `<label>${esc(t.api_key)}${preset.keyUrl ? ` · <a href="${preset.keyUrl}" target="_blank" rel="noopener">${esc(host(preset.keyUrl))}</a>` : ''}<input class="pf-key" type="password" placeholder="${esc(form.key ? t.st_key_kept : 'sk-…')}"></label>`}
        <div class="st-row"><button type="button" class="pf-fetch">${esc(t.st_fetch)}</button><span class="pf-err"></span></div>
        ${list}
        <div class="st-row end"><button type="button" class="pf-cancel">${esc(t.cancel)}</button><button type="button" class="primary pf-save"${form.found && form.found.length ? '' : ' disabled'}>${esc(t.st_save_provider)}</button></div></div>`;
    }

    function render() {
      const t = T();
      dlg.innerHTML = `<div class="st"><h2>${esc(t.settings)}</h2>
        <section class="st-uilang"><h3>${esc(t.ui_lang)}</h3><select class="st-ui">${I18N.CODES.map((c) => `<option value="${c}"${c === uiLang ? ' selected' : ''}>${esc(I18N.NATIVE[c])}</option>`).join('')}</select></section>
        <section><h3>${esc(t.st_model)}</h3>${modelSection()}</section>
        <section><h3>${esc(t.st_agents)}</h3>${agentSection()}</section>
        <section><h3>${esc(t.st_providers)}</h3>${providerSection()}</section>
        <p class="st-note">${esc(t.key_note)}</p>
        <div class="st-btns"><span></span><button type="button" class="primary st-close">${esc(t.st_close)}</button></div></div>`;
      wire();
    }
    const q = (sel) => dlg.querySelector(sel);
    const update = (d) => { data = d; modelName = d.models.length ? (d.selectedName || '') : ''; renderSidebar(); if (landing) renderLanding(); render(); };

    function wire() {
      q('.st-close').onclick = () => dlg.close();
      q('.st-ui').onchange = (e) => { setUiLang(e.target.value); render(); };
      const sel = q('.st-model');
      if (sel) sel.onchange = async () => { test = null; update(await api('/api/models/select', { model: sel.value })); };
      const tb = q('.st-testbtn');
      if (tb) tb.onclick = async () => { tb.disabled = true; tb.textContent = '…'; test = await api('/api/settings/test', { model: data.selected }); render(); };
      q('.st-scan').onclick = async () => { data.scanning = true; render(); update(await api('/api/agents/scan', {})); };
      const td = q('.st-td');
      if (td) td.onchange = async () => update(await api('/api/settings', { use_thoughtdag_env: td.checked }));
      dlg.querySelectorAll('.st-del').forEach((b) => { b.onclick = async () => update(await api('/api/providers/remove', { key: b.dataset.key })); });
      dlg.querySelectorAll('.st-edit').forEach((b) => {
        b.onclick = () => { const p = data.providers.find((x) => x.key === b.dataset.key); form = { key: p.key, preset: p.preset || 'custom', name: p.name, base: p.base }; render(); };
      });
      const bg = q('.st-bridgego');
      if (bg) bg.onclick = async () => {   // start the bridge; its models join the list once it answers
        bridgeStarting = true; render();
        try { await api('/api/bridge/start', {}); } catch { bridgeStarting = false; render(); return; }
        for (let k = 0; k < 150 && dlg.isConnected && bridgeStarting; k++) {
          await new Promise((r) => setTimeout(r, 2000));
          if ((await api('/api/bridge')).running) break;
        }
        bridgeStarting = false;
        if (dlg.isConnected) update(await api('/api/models'));
      };
      const add = q('.st-add');
      if (add) add.onclick = () => { const p = data.presets[0]; form = { preset: p.id, name: '', base: p.base }; render(); };
      if (!form) return;
      const ps = q('.pf-preset');
      ps.onchange = () => { const p = data.presets.find((x) => x.id === ps.value); form = { preset: p.id, name: '', base: p.base }; render(); };   // another kind: a new provider, the edited one stays
      const keep = () => { form.base = q('.pf-base').value.trim(); if (q('.pf-name')) form.name = q('.pf-name').value.trim(); if (q('.pf-key') && q('.pf-key').value) form.api_key = q('.pf-key').value.trim(); };
      q('.pf-fetch').onclick = () => fetchModels();
      const pick = q('.st-pick'), count = q('.st-count'), search = q('.st-search');
      const recount = () => { if (count && pick) count.textContent = `· ${pick.querySelectorAll('input:checked').length}`; };
      if (pick) { pick.onchange = recount; recount(); }
      if (search) search.oninput = () => {
        const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
        pick.querySelectorAll('label').forEach((l) => { l.hidden = !words.every((w) => l.dataset.id.includes(w)); });
      };
      const oa = q('.pf-oauth');
      if (oa) oa.onclick = async () => { oa.disabled = true; if (window.desktop) dlg.close(); await connectOpenRouter(location.pathname + location.search); };
      const cp = q('.pf-copy');
      if (cp) cp.onclick = () => navigator.clipboard.writeText('npx openai-oauth').then(() => { cp.textContent = '✓'; }, () => {});
      const bs = q('.pf-bridge');
      if (bs) bs.onclick = async () => {
        form.bridgeStarting = true; render();
        try { await api('/api/bridge/start', {}); } catch (x) { form.bridgeStarting = false; render(); q('.pf-err').textContent = x.message; return; }
        for (let k = 0; k < 150 && dlg.isConnected && form && form.bridgeStarting; k++) {   // up to 5 minutes: a sign-in may be under way
          await new Promise((r) => setTimeout(r, 2000));
          const st = await api('/api/bridge');
          if (st.running) { form.bridge = st; form.bridgeStarting = false; render(); fetchModels(); return; }
        }
        if (form) { form.bridgeStarting = false; render(); }
      };
      const pre = data.presets.find((x) => x.id === form.preset) || {};
      if (pre.bridge && !form.bridge) api('/api/bridge').then((st) => { if (!form) return; form.bridge = st; render(); if (st.running && !form.found) fetchModels(); });
      q('.pf-cancel').onclick = () => { form = null; render(); };
      q('.pf-save').onclick = async () => {
        keep();
        const picked = [...dlg.querySelectorAll('.st-pick input:checked')].map((i) => i.value);
        const d = await api('/api/providers/save', { key: form.key, preset: form.preset, name: form.name, base: form.base, api_key: form.api_key, models: picked, minted: !!form.minted });
        form = null; update(d);
      };
    }
    async function fetchModels() {
      if (!form) return;
      if (q('.pf-base')) form.base = q('.pf-base').value.trim();
      if (q('.pf-name')) form.name = q('.pf-name').value.trim();
      if (q('.pf-key') && q('.pf-key').value) form.api_key = q('.pf-key').value.trim();
      const err = q('.pf-err');
      if (err) err.textContent = '…';
      try {
        const r = await api('/api/providers/probe', { base: form.base, api_key: form.api_key, key: form.key, preset: form.preset, minted: !!form.minted });
        form.found = r.models; form.picked = r.picked; render();
      } catch (x) { const e2 = q('.pf-err'); if (e2) e2.textContent = x.message; }
    }

    dlg.addEventListener('close', () => dlg.remove());
    if (opts && opts.add) form = { preset: data.presets[0].id, name: '', base: data.presets[0].base };   // straight to adding one
    if (opts && opts.minted) {   // back from OpenRouter with a key: the models to pick, free ones first
      const p = data.presets.find((x) => x.id === 'openrouter');
      form = { preset: 'openrouter', name: '', base: p.base, minted: true };
    }
    render();
    dlg.showModal();
    if (opts && opts.minted) fetchModels();
    // the startup scan may still be running: show what it finds as it lands
    const wait = async () => { if (!dlg.isConnected) return; if (data.scanning) { await new Promise((r) => setTimeout(r, 800)); update(await api('/api/models')); wait(); } };
    wait();
  }

  renderSidebar();
  // back from OpenRouter's consent page (#or-minted, or #or-failed=why)
  if (location.hash.startsWith('#or-')) {
    const hash = location.hash;
    history.replaceState(null, '', location.pathname + location.search);
    if (hash === '#or-minted') openSettings({ minted: true });
    else alert(t().or_failed.replace('{error}', decodeURIComponent(hash.split('=')[1] || '')));
  }
})();
