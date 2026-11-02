const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// The browser's button (extension/background.js): the page and its frames sent as one, each frame's page put where its
// iframe is, by its address; a frame it could not read keeps its place empty; the readings of reader.js sent with it,
// made in the top frame only, and the page sent without them when they fail; when TextFold cannot be reached, or is
// older than the extension, a page that says what to do. And what the manifest asks for, in each language.
const dir = path.join(__dirname, '..', 'extension');

const plain = (x) => JSON.parse(JSON.stringify(x));   // (from the extension's own context)
const READING = { defuddle: { html: '<p>Top</p>', title: 'A', words: 120 }, notes: 0, errors: [] };

// native: what TextFold's host does with a message (by default, keeps it)
function background(readerFails, native) {
  const sent = [], badges = [], scripts = [], tabs = [], titles = [], installed = [];
  const chrome = {
    action: { onClicked: { addListener() {} }, setBadgeText: (b) => badges.push(b.text), setBadgeBackgroundColor() {}, setTitle: (t) => titles.push(t.title) },
    scripting: { executeScript: async (o) => {
      scripts.push(o);
      if (o.func) return [{ frameId: 0, result: READING }];
      if (o.files.includes('reader.js')) {
        if (readerFails) throw new Error('Cannot access contents of the page');
        return [{ frameId: 0, result: null }];
      }
      return [
        { frameId: 0, result: { url: 'https://a.example/p', title: 'A', html: '<html><body><p>Top</p><div class="x" data-tf-frame="0" data-tf-frame-src="https://a.example/inner?a=1&amp;b=2"><!--TF-FRAME-0--></div><div data-tf-frame="1" data-tf-frame-src="https://ads.example/x"><!--TF-FRAME-1--></div></body></html>' } },
        { frameId: 7, result: { url: 'https://a.example/inner?a=1&b=2', title: '', html: '<html><head></head><body><p>Inside</p></body></html>' } },
      ];
    } },
    runtime: {
      sendNativeMessage: async (host, msg) => { sent.push([host, msg]); return native ? native(msg) : { ok: true, paper: 'web-a-example-1', new: true, open: null }; },
      getURL: (p) => `chrome-extension://abc/${p}`,
      onInstalled: { addListener: (f) => installed.push(f) },
    },
    i18n: { getMessage: (k, subs) => (subs ? `${k}:${subs.join(',')}` : k) },
    tabs: { create: (t) => tabs.push(t) },
  };
  const context = vm.createContext({ chrome, self: {}, console });
  context.importScripts = (...files) => files.forEach((f) => vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), context));
  vm.runInContext(fs.readFileSync(path.join(dir, 'background.js'), 'utf8'), context);
  return { capture: context.self.capture, mathSources: context.self.mathSources, reach: context.self.reach, sent, badges, scripts, tabs, titles, installed };
}

test('the frames are put in their places and the page is sent to TextFold', async () => {
  const b = background();
  const reply = await b.capture({ id: 3, index: 0 });
  assert.equal(reply.ok, true);
  const [host, msg] = b.sent[0];
  assert.equal(host, 'app.textfold.capture');
  assert.equal(msg.format, 'textfold/snapshot');
  assert.match(msg.html, /data-tf-frame-src="https:\/\/a\.example\/inner\?a=1&amp;b=2"><p>Inside<\/p><\/div>/);
  assert.match(msg.html, /<!--TF-FRAME-1-->/);   // (a frame the tab did not let it into: its place, empty)
  assert.deepEqual(b.badges, ['…', '✓']);
});

test('the readings are made in the top frame, on the snapshot sent, and sent with it', async () => {
  const b = background();
  await b.capture({ id: 3, index: 0 });
  const files = b.scripts.find((o) => o.files && o.files.includes('reader.js'));
  const call = b.scripts.find((o) => o.func && o.args);
  assert.deepEqual(plain(files.target), { tabId: 3, frameIds: [0] });
  assert.deepEqual(plain(files.files), ['vendor/defuddle/defuddle.js', 'vendor/readability/Readability.js', 'reader.js']);
  const [, msg] = b.sent[0];
  assert.equal(call.args[0], msg.html);
  assert.equal(call.args[1], 'https://a.example/p');
  assert.deepEqual(msg.read, READING);
});

test("MathJax's formulas are asked for their sources in the page's own world, before the snapshot", async () => {
  const b = background();
  await b.capture({ id: 3, index: 0 });
  assert.equal(b.scripts[0].world, 'MAIN');
  assert.equal(b.scripts[0].func.name, 'mathSources');
  assert.deepEqual(plain(b.scripts[1].files), ['snapshot.js']);
});

test("a page's MathJax 3 or 4, and 2: each formula's source written on its drawing", () => {
  const b = background();
  const els = [0, 1, 2].map(() => { const a = {}; return { setAttribute: (k, v) => { a[k] = v; }, a }; });
  const win = { MathJax: { startup: { document: { math: [
    { typesetRoot: els[0], math: 'y_i', display: false, inputJax: { name: 'TeX' } },
    { typesetRoot: els[1], math: '<math><mi>z</mi></math>', display: true, inputJax: { name: 'MathML' } },
  ] } } } };
  const run = (w, d) => vm.runInNewContext(`(${b.mathSources.toString()})()`, { window: w, document: d });
  assert.equal(run(win, {}), 2);
  assert.deepEqual(els[0].a, { 'data-tf-math': 'y_i', 'data-tf-math-in': 'tex' });
  assert.deepEqual(els[1].a, { 'data-tf-math': '<math><mi>z</mi></math>', 'data-tf-math-in': 'mathml', 'data-tf-math-display': 'block' });
  const v2 = { MathJax: { Hub: { getAllJax: () => [{ inputID: 'MathJax-Element-1', originalText: 'x^2', inputJax: 'TeX', root: { Get: () => 'inline' } }] } } };
  assert.equal(run(v2, { getElementById: (id) => (id === 'MathJax-Element-1-Frame' ? els[2] : null) }), 1);
  assert.equal(els[2].a['data-tf-math'], 'x^2');
  assert.equal(run({}, {}), 0);   // (no MathJax)
});

test('a page whose readings fail is sent all the same, with why', async () => {
  const b = background(true);
  const reply = await b.capture({ id: 3, index: 0 });
  assert.equal(reply.ok, true);
  const [, msg] = b.sent[0];
  assert.match(msg.read.errors[0], /Cannot access/);
  assert.match(msg.html, /<p>Inside<\/p>/);
});

test('a TextFold not there, not letting the extension in, or gone: a page says what to do', async () => {
  const said = { missing: 'Specified native messaging host not found.', forbidden: 'Access to the specified native messaging host is forbidden.',
                 exited: 'Native host has exited.' };
  for (const [why, message] of Object.entries(said)) {
    const b = background(false, () => { throw new Error(message); });
    const reply = await b.capture({ id: 3, index: 4 });
    assert.deepEqual(plain(reply), { ok: false, error: why });
    assert.deepEqual(plain(b.tabs), [{ url: `chrome-extension://abc/setup.html#${why}`, index: 5 }]);
    assert.deepEqual(b.badges, ['…', '!']);
    assert.equal(b.titles.at(-1), 'TextFold: err_setup');
  }
});

test('a TextFold older than the extension says so, and the reader is told to update it', async () => {
  const b = background(false, () => ({ ok: false, error: 'update-textfold' }));
  assert.equal((await b.capture({ id: 3, index: 0 })).error, 'update-textfold');
  assert.equal(b.tabs[0].url, 'chrome-extension://abc/setup.html#update');
  assert.equal(b.titles.at(-1), 'TextFold: err_update');
  const other = background(false, () => ({ ok: false, error: 'web-notext' }));
  await other.capture({ id: 3, index: 0 });
  assert.deepEqual(other.tabs, []);   // (a page with too little to read: said on the button, no page opened)
  assert.equal(other.titles.at(-1), 'TextFold: err_notext');
});

test('kept, the button says where: in the library, and to open TextFold when it is not running', async () => {
  const closed = background();
  await closed.capture({ id: 3, index: 0 });
  assert.equal(closed.titles.at(-1), 'saved_closed');
  const running = background(false, () => ({ ok: true, paper: 'web-a-example-1', new: false, open: 'http://127.0.0.1:31917/p/web-a-example-1' }));
  await running.capture({ id: 3, index: 0 });
  assert.equal(running.titles.at(-1), 'already');
  assert.deepEqual(plain(running.tabs), [{ url: 'http://127.0.0.1:31917/p/web-a-example-1', index: 1 }]);
  assert.equal(running.sent[0][1].version, 1);
});

test('a hello: which TextFold answers, or why none does; once installed, the page opens only when none does', async () => {
  const cases = [
    [() => ({ ok: true, textfold: '0.10.40', protocol: 1, running: false }), { why: null, textfold: '0.10.40' }],
    [() => ({ ok: false, error: 'not-a-snapshot' }), { why: 'update' }],   // (a TextFold from before the hello)
    [() => { throw new Error('Specified native messaging host not found.'); }, { why: 'missing' }],
    [() => { throw new Error('something else'); }, { why: 'exited' }],
  ];
  for (const [native, want] of cases) {
    const b = background(false, native);
    assert.deepEqual(plain(await b.reach()), want);
    assert.deepEqual(plain(b.sent[0][1]), { format: 'textfold/hello', version: 1 });
  }
  const none = background(false, () => { throw new Error('Specified native messaging host not found.'); });
  await none.installed[0]({ reason: 'install' });
  assert.deepEqual(plain(none.tabs), [{ url: 'chrome-extension://abc/setup.html#missing' }]);
  const there = background(false, () => ({ ok: true, textfold: '0.10.40', protocol: 1 }));
  await there.installed[0]({ reason: 'install' });
  await there.installed[0]({ reason: 'update' });
  assert.deepEqual(there.tabs, []);
});

test('each language has every message, its placeholders, and a description the stores take', () => {
  const read = (loc) => JSON.parse(fs.readFileSync(path.join(dir, '_locales', loc, 'messages.json'), 'utf8'));
  const en = read('en');
  const locs = fs.readdirSync(path.join(dir, '_locales'));
  assert.equal(locs.length, 13);   // (the app's 12 languages; Portuguese for Brazil and Portugal)
  for (const loc of locs) {
    const m = read(loc);
    assert.deepEqual(Object.keys(m).sort(), Object.keys(en).sort(), loc);
    for (const [k, v] of Object.entries(m)) {
      assert.deepEqual(Object.keys(v.placeholders || {}), Object.keys(en[k].placeholders || {}), `${loc} ${k}`);
      for (const p of Object.keys(v.placeholders || {})) assert.ok(v.message.includes(`$${p.toUpperCase()}$`), `${loc} ${k}`);
    }
    assert.ok(m.description.message.length <= 132, loc);
  }
  const manifest = fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8');
  for (const [, k] of manifest.matchAll(/__MSG_(\w+)__/g)) assert.ok(en[k], k);
  const page = fs.readFileSync(path.join(dir, 'setup.html'), 'utf8') + fs.readFileSync(path.join(dir, 'setup.js'), 'utf8');
  for (const [, a, b] of page.matchAll(/data-i18n="(\w+)"|'(step_\w+)'/g)) assert.ok(en[a || b], a || b);
  for (const why of ['ok', 'missing', 'forbidden', 'exited', 'update']) assert.ok(en[`${why}_title`] && (why === 'ok' || en[`${why}_text`]), why);
});

test('the readers the extension runs are in it, each with its license', () => {
  for (const f of ['vendor/defuddle/defuddle.js', 'vendor/defuddle/LICENSE', 'vendor/readability/Readability.js',
                   'vendor/readability/LICENSE.md', 'reader.js']) {
    assert.ok(fs.existsSync(path.join(dir, f)), f);
  }
  assert.match(fs.readFileSync(path.join(dir, 'vendor/defuddle/defuddle.js'), 'utf8').slice(0, 2000), /changes:/);
});

test('the extension asks for the tab it is clicked on, and nothing more', () => {
  const m = JSON.parse(fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
  assert.deepEqual(m.permissions.sort(), ['activeTab', 'nativeMessaging', 'scripting']);
  assert.equal(m.host_permissions, undefined);
  assert.equal(m.manifest_version, 3);
});
