const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// "Drop it here" (app.js whileDragged): it comes with a file dragged over the page and goes when the file leaves the
// window, is dropped, or stops coming by, however many dragleave events the page's redrawn elements took with them.
const app = fs.readFileSync(path.join(__dirname, '..', 'textfold', 'web', 'app.js'), 'utf8');
const code = app.slice(app.indexOf('  function whileDragged(on, off) {'), app.indexOf('  // ── a delete\'s Undo'));

function page() {
  let now = 0, next = 0;
  const timers = new Map(), on = { document: {}, window: {} }, said = [];
  const listen = (where) => (type, fn, capture) => { on[where][type] = { fn, capture: !!capture }; };
  const context = vm.createContext({
    document: { addEventListener: listen('document') },
    addEventListener: listen('window'),
    setTimeout: (fn, ms) => { timers.set(++next, { at: now + ms, fn }); return next; },
    clearTimeout: (id) => { timers.delete(id); },
  });
  vm.runInContext(`${code}\nwhileDragged(() => said.push('on'), () => said.push('off'));`, Object.assign(context, { said }));
  const ev = (type, { files = true, related = {} } = {}) => {
    const e = { type, relatedTarget: related, dataTransfer: { types: files ? ['Files'] : ['text/plain'] }, prevented: false };
    e.preventDefault = () => { e.prevented = true; };
    const where = on.document[type] ? 'document' : 'window';
    on[where][type].fn(e);
    return e;
  };
  const wait = (ms) => {
    now += ms;
    for (const [id, t] of [...timers].sort((a, b) => a[1].at - b[1].at)) if (t.at <= now && timers.has(id)) { timers.delete(id); t.fn(); }
  };
  return { ev, wait, said, on };
}

test('it comes once, and is not drawn again under the pointer', () => {
  const p = page();
  p.ev('dragenter');
  for (let k = 0; k < 20; k++) { p.ev('dragenter'); p.ev('dragover'); }
  assert.deepEqual(p.said, ['on']);
  assert.equal(p.ev('dragover').prevented, true);
});

test('dragleave events lost with redrawn elements do not keep it: out of the window, it goes', () => {
  const p = page();
  for (let k = 0; k < 12; k++) p.ev('dragenter');   // twelve in, none of their dragleave come back
  p.ev('dragleave');                               // (from one element to the next: it stays)
  p.wait(40);
  assert.deepEqual(p.said, ['on']);
  p.ev('dragleave', { related: null });            // out of the window
  p.wait(60);
  assert.deepEqual(p.said, ['on', 'off']);
});

test('held still it stays; called off without a leave, it goes in a second', () => {
  const p = page();
  p.ev('dragenter');
  for (let k = 0; k < 10; k++) { p.wait(300); p.ev('dragover'); }
  assert.deepEqual(p.said, ['on']);
  p.wait(1000);
  assert.deepEqual(p.said, ['on', 'off']);
});

test('dropped, it goes before the page says what comes of the file', () => {
  const p = page();
  p.ev('dragenter');
  assert.equal(p.on.window.drop.capture, true);
  p.ev('drop');
  assert.deepEqual(p.said, ['on', 'off']);
  p.wait(2000);
  assert.deepEqual(p.said, ['on', 'off']);
});

test('text or a link dragged within the page is not a file', () => {
  const p = page();
  p.ev('dragenter', { files: false });
  assert.equal(p.ev('dragover', { files: false }).prevented, false);
  p.ev('dragleave', { related: null });
  p.wait(2000);
  assert.deepEqual(p.said, []);
});
