const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const app = fs.readFileSync(path.join(__dirname, '..', 'textfold', 'web', 'app.js'), 'utf8');
const startCode = app.slice(app.indexOf('    async function start(ref, label, langOf) {'),
  app.indexOf('    // a file that needs the engine:'));
const formCode = app.slice(app.indexOf('    form.onsubmit = async (e) => {'),
  app.indexOf('    // a file, from the drop zone'));

function landing({ model = true, submit = async () => ({ status: 'queued' }) } = {}) {
  const input = { value: 'https://arxiv.org/abs/2601.12345' };
  const err = { hidden: false };
  const card = { hidden: true };
  const form = {};
  const context = vm.createContext({
    form, err, card, sel: { value: 'en' }, modelName: model ? 'model' : '',
    document: { getElementById: id => id === 'ref' ? input : null },
    t: () => ({ bad_ref: 'Invalid URL', no_model: 'No model' }),
    fail: text => { err.textContent = text; err.hidden = false; },
    errText: x => x, onCard: () => () => {}, submit,
  });
  vm.runInContext(`let latest = null; ${startCode}\n${formCode}`, context);
  return { input, err, card, submit: () => form.onsubmit({ preventDefault() {} }) };
}

test('a queued paper frees the input for the next arXiv link', async () => {
  const seen = [];
  const h = landing({ submit: async ref => { seen.push(ref); return { status: 'queued' }; } });
  await h.submit();
  assert.deepEqual(seen, ['https://arxiv.org/abs/2601.12345']);
  assert.equal(h.input.value, '');
});

test('invalid input, no model, and failed submission leave the link for correction or retry', async () => {
  const invalid = landing();
  invalid.input.value = 'wrong URL';
  await invalid.submit();
  assert.equal(invalid.input.value, 'wrong URL');

  const withoutModel = landing({ model: false });
  await withoutModel.submit();
  assert.equal(withoutModel.input.value, 'https://arxiv.org/abs/2601.12345');

  const refused = landing({ submit: async () => { throw new Error('Server unavailable'); } });
  await refused.submit();
  assert.equal(refused.input.value, 'https://arxiv.org/abs/2601.12345');
  assert.equal(refused.err.textContent, 'Server unavailable');
});

test('a slow submission never erases the next URL the reader has started typing', async () => {
  let accept;
  const h = landing({ submit: () => new Promise(resolve => { accept = resolve; }) });
  const pending = h.submit();
  h.input.value = 'https://arxiv.org/abs/2602.54321';
  accept({ status: 'queued' });
  await pending;
  assert.equal(h.input.value, 'https://arxiv.org/abs/2602.54321');
});
