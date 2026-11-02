const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// The edit history (app.js review): each place the edits changed in a text since it was last generated
// (placesOf), found by comparing it with the text before them, paragraph by paragraph and then word by word (diffOf).
const app = fs.readFileSync(path.join(__dirname, '..', 'textfold', 'web', 'app.js'), 'utf8');
const code = app.slice(app.indexOf('    function diffOf(a, b) {'), app.indexOf('    // The Markdown a document was read from'));
const context = vm.createContext({});
vm.runInContext(`${code}\nthis.diffOf = diffOf; this.placesOf = placesOf;`, context);
const { diffOf, placesOf } = context;
const plain = (x) => JSON.parse(JSON.stringify(x));
const withPlace = (text, p, words) => text.slice(0, p.at) + words + text.slice(p.at + p.now.length);   // (as showHistory)

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

const WAS = '# Diary\n\nOpening.\n\n## Monday\n\nThe cornpressor ran, and the pump did the work.\n\n<figure><img src="images/a.jpg"></figure>\n\nall night.\n\n## Tuesday\n\nCold.';
const NOW = '# Diary\n\nOpening.\n\n## Monday\n\nThe compressor ran, and the heat pump did the job all night.\n\n<figure><img src="images/a.jpg"></figure>\n\n## Tuesday\n\nCold.\n\nA new line.';

test('each place changed, where it is in the text as it is now', () => {
  const places = plain(placesOf(WAS, NOW));
  assert.deepEqual(places.map(({ was, now }) => [was, now]), [
    ['cornpressor', 'compressor'],
    ['', 'heat '],
    ['work', 'job all night'],                                           // words side by side: one place
    ['all night.\n\n', ''],                                              // a paragraph taken out, with its break
    ['', '\n\nA new line.'],
  ]);
  for (const p of places) assert.equal(NOW.slice(p.at, p.at + p.now.length), p.now);
  assert.deepEqual(plain(placesOf(WAS, WAS)), []);
});

// (the words of a place, the white space at its ends aside: which of two spaces a word is put in with is the comparison's choice)
const words = (places) => plain(places).map(({ was, now }) => [was.trim(), now.trim()]);

test('each undone by itself leaves the others as they are; all undone, the text is the one before', () => {
  const places = placesOf(WAS, NOW);
  places.forEach((p, i) => {
    assert.deepEqual(words(placesOf(WAS, withPlace(NOW, p, p.was))), words(places).filter((_, k) => k !== i));
  });
  let text = NOW;
  for (let left = placesOf(WAS, text); left.length; left = placesOf(WAS, text)) text = withPlace(text, left[0], left[0].was);
  assert.equal(text, WAS);
});

test('one written anew: the others stay', () => {
  const [first] = placesOf(WAS, NOW);
  const text = withPlace(NOW, first, 'big compressor');
  assert.ok(text.startsWith('# Diary\n\nOpening.\n\n## Monday\n\nThe big compressor ran, and the heat pump'));
  assert.deepEqual(words(placesOf(WAS, text)), [['cornpressor', 'big compressor'], ...words(placesOf(WAS, NOW)).slice(1)]);
});

test('words as each language has them: a Chinese sentence has no spaces between its words', () => {
  assert.deepEqual(words(placesOf('热泵在夜里一直运行，压缩机做了所有的功。\n\n第二段。', '热泵在整个夜里一直运行，压缩机做了全部的功。\n\n第二段。')),
    [['', '整个'], ['所有', '全部']]);
});

test('paragraphs joined: the break taken out, a space put in', () => {
  const places = plain(placesOf('It ran\n\nall night.', 'It ran all night.'));
  assert.deepEqual(places, [{ at: 6, was: '\n\n', now: ' ' }]);
});
