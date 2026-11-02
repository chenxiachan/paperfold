const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// The editor (app.js editText): the section the words selected are in, shown alone (sectionAt); its edit history, each
// version with what its save changed, the paragraphs (changesOf) and, in them, the words (diffOf).
const app = fs.readFileSync(path.join(__dirname, '..', 'textfold', 'web', 'app.js'), 'utf8');
const code = app.slice(app.indexOf('    function diffOf(a, b) {'), app.indexOf('    // The Markdown a document was read from'));
const context = vm.createContext({});
vm.runInContext(`${code}\nthis.diffOf = diffOf; this.changesOf = changesOf; this.sectionAt = sectionAt;`, context);
const { diffOf, changesOf, sectionAt } = context;
const plain = (x) => JSON.parse(JSON.stringify(x));

test('the words of a paragraph: what was taken out and put in, in order', () => {
  assert.deepEqual(plain(diffOf(['the', 'cornpressor', 'does', 'it'], ['the', 'compressor', 'does', 'all', 'of', 'it'])), [
    ['=', 'the'], ['-', 'cornpressor'], ['+', 'compressor'], ['=', 'does'], ['+', 'all'], ['+', 'of'], ['=', 'it'],
  ]);
  assert.deepEqual(plain(diffOf(['a', 'b'], ['a', 'b'])), [['=', 'a'], ['=', 'b']]);
  assert.deepEqual(plain(diffOf([], ['a'])), [['+', 'a']]);
  assert.deepEqual(plain(diffOf(['a', 'x', 'b'], ['b', 'a'])).filter(([k]) => k === '=').length, 1);
});

test('too long to compare: all of the one out and the other in, what they begin and end with kept', () => {
  const a = ['start', ...Array.from({ length: 1500 }, (_, i) => `a${i}`), 'end'];
  const b = ['start', ...Array.from({ length: 1500 }, (_, i) => `b${i}`), 'end'];
  const ops = diffOf(a, b);
  assert.deepEqual(plain(ops[0]), ['=', 'start']);
  assert.deepEqual(plain(ops.at(-1)), ['=', 'end']);
  assert.equal(ops.filter(([k]) => k === '-').length, 1500);
  assert.equal(ops.filter(([k]) => k === '+').length, 1500);
});

test('the paragraphs changed, each run under the heading before it', () => {
  const was = '# Diary\n\nOpening.\n\n## Monday\n\nThe cornpressor ran.\n\n<figure><img src="images/a.jpg"></figure>\n\nall night.\n\n## Tuesday\n\nCold.';
  const now = '# Diary\n\nOpening.\n\n## Monday\n\nThe compressor ran all night.\n\n<figure><img src="images/a.jpg"></figure>\n\n## Tuesday\n\nCold.\n\nA new line.';
  assert.deepEqual(plain(changesOf(was, now)), [
    { heading: 'Monday', was: 'The cornpressor ran.', now: 'The compressor ran all night.' },
    { heading: 'Monday', was: 'all night.', now: '' },
    { heading: 'Tuesday', was: '', now: 'A new line.' },
  ]);
  assert.deepEqual(plain(changesOf(was, was)), []);
});

test('the section a place is in: from the heading above it to the next one', () => {
  const text = '# Title\n\nBy someone.\n\n## One\n\nFirst #1 paragraph.\n\n<figure></figure>\n\n### One.a\n\nDeeper.\n\n## Two\n\nLast.\n';
  const at = (w) => text.indexOf(w), part = (w) => { const [a, b] = sectionAt(text, at(w)); return text.slice(a, b); };
  assert.equal(part('First'), '## One\n\nFirst #1 paragraph.\n\n<figure></figure>\n\n');
  assert.equal(part('Deeper'), '### One.a\n\nDeeper.\n\n');
  assert.equal(part('One.a'), '### One.a\n\nDeeper.\n\n');   // (a heading's own words: its section)
  assert.equal(part('Last'), '## Two\n\nLast.\n');
  assert.equal(part('By someone'), '# Title\n\nBy someone.\n\n');
  assert.deepEqual(plain(sectionAt('No heading at all.', 3)), [0, 18]);
});
