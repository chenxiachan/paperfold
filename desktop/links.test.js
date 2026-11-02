// links.js, without Electron: `npm test` here, or `node --test links.test.js` (tests/test_desktop_links.py runs it too)
const test = require('node:test');
const assert = require('node:assert/strict');
const { parse, readerUrl, fromArgv, validId } = require('./links');

const BASE = 'http://127.0.0.1:31917';

test('a link opens its paper, at its paragraph and level, in its language', () => {
  const parts = parse('textfold://open?paper=2512.23916&u=S3.p2&level=key&lang=zh-Hant');
  assert.deepEqual(parts, { paper: '2512.23916', u: 'S3.p2', level: 'key', lang: 'zh-Hant' });
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/2512.23916?lang=zh-Hant#u=S3.p2&level=key`);
});

test('a link to a note opens the note, which brings its own paragraph', () => {
  const parts = parse('textfold://open?paper=wiki-en-13460&u=S1.p1&n=n-k2x9q0ab');
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/wiki-en-13460#n=n-k2x9q0ab`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=wiki-en-13460&n=n-k2x9q0ab&level=topic')),
    `${BASE}/p/wiki-en-13460#n=n-k2x9q0ab&level=topic`);
});

test('a link to a section opens it at its level', () => {
  const parts = parse('textfold://open?paper=2512.23916&s=S3.SS1&level=takeaway');
  assert.deepEqual(parts, { paper: '2512.23916', s: 'S3.SS1', level: 'takeaway' });
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/2512.23916#s=S3.SS1&level=takeaway`);
  // (one place: a paragraph is more exact than its section, a note more than either)
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&s=S3&u=S3.p2')), `${BASE}/p/2512.23916#u=S3.p2`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&s=S3&n=n-k2x9q0ab')), `${BASE}/p/2512.23916#n=n-k2x9q0ab`);
});

test('a link to a run of paragraphs, from u to to', () => {
  const parts = parse('textfold://open?paper=2512.23916&u=S1.p1.1&to=S1.p3.1&level=key');
  assert.deepEqual(parts, { paper: '2512.23916', u: 'S1.p1.1', to: 'S1.p3.1', level: 'key' });
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/2512.23916#u=S1.p1.1&to=S1.p3.1&level=key`);
  // (to goes with u: alone, or with a section or a note, it names nothing)
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&s=S1&to=S1.p3.1')), `${BASE}/p/2512.23916#s=S1`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&n=n-1&u=S1.p1.1&to=S1.p3.1')), `${BASE}/p/2512.23916#n=n-1`);
});

test('a link to an equation opens it, by way of the paragraph it goes with', () => {
  const parts = parse('textfold://open?paper=md-notes-on-diffusion-694d6667&u=p-e426aba2&eq=eq-heat&level=full&lang=en');
  assert.equal(parts.eq, 'eq-heat');
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/md-notes-on-diffusion-694d6667?lang=en#u=p-e426aba2&eq=eq-heat&level=full`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&s=S2&eq=S2.E1')), `${BASE}/p/2512.23916#s=S2&eq=S2.E1`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&n=n-1&eq=S2.E1')), `${BASE}/p/2512.23916#n=n-1`);   // (a note brings its own place)
  assert.equal(parse('textfold://open?paper=2512.23916&eq=S2%2FE1'), null);
});

test('a link to one turn of a conversation', () => {
  const parts = parse('textfold://open?paper=2512.23916&n=n-chat0001&t=2&lang=de');
  assert.deepEqual(parts, { paper: '2512.23916', n: 'n-chat0001', t: '2', lang: 'de' });
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/2512.23916?lang=de#n=n-chat0001&t=2`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&n=n-chat0001&t=007')), `${BASE}/p/2512.23916#n=n-chat0001&t=7`);
  // (a turn without its conversation names nothing)
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=2512.23916&u=S3.p2&t=1')), `${BASE}/p/2512.23916#u=S3.p2`);
});

test('the paper alone, or at a level alone', () => {
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=pmc1234567')), `${BASE}/p/pmc1234567`);
  assert.equal(readerUrl(BASE, parse('textfold://open?paper=pmc1234567&level=full')), `${BASE}/p/pmc1234567#level=full`);
});

test('values may be URL-encoded, and the path may end in a slash', () => {
  assert.deepEqual(parse('textfold://open/?paper=2512%2E23916&u=S3%2Ep2'), { paper: '2512.23916', u: 'S3.p2' });
});

test('a parameter this app does not know is left alone', () => {
  assert.deepEqual(parse('textfold://open?paper=2512.23916&from=obsidian'), { paper: '2512.23916' });
});

test('every id store.py takes, and nothing else', () => {
  for (const id of ['2512.23916', '2201.11903', 'md-notes-on-graphs-1a2b3c', 'pmc1234567', 'ppr123456', 'biorxiv-2024.01.02.573',
    'medrxiv-2023.11.20.23298000', 'wiki-en-13460', 'wiki-zh-classical-42', 'gh-chenxiachan--textfold', 'pdf-0123456789abcdef',
    'doc-0123456789abcdef', 'web-example-com-0123456789ab']) {
    assert.ok(validId(id), id);
  }
  for (const id of ['', '2512.239', '2512.23916v2', '../etc', 'md-', 'md-Upper-1a', 'pdf-0123', 'wiki-en-x', 'gh-a/b',
    'web-example.com-0123456789ab', `md-${'a'.repeat(80)}`, '2512.23916/../x']) {
    assert.ok(!validId(id), id);
  }
});

test('a link with any part wrong is not followed', () => {
  for (const link of [
    'textfold://open',                                            // no paper
    'textfold://open?paper=../../etc/passwd',
    'textfold://open?paper=2512.23916&paper=2201.11903',           // which one?
    'textfold://open?paper=2512.23916&u=S3.p2%23x',
    'textfold://open?paper=2512.23916&u=',
    'textfold://open?paper=2512.23916&u=S3+p2',                    // (a space)
    'textfold://open?paper=2512.23916&s=S3/../x',
    'textfold://open?paper=2512.23916&s=S3&s=S4',
    'textfold://open?paper=2512.23916&n=n-1&t=-1',
    'textfold://open?paper=2512.23916&u=S1.p1.1&to=S1.p3.1%23x',
    'textfold://open?paper=2512.23916&u=S1.p1.1&to=a&to=b',
    'textfold://open?paper=2512.23916&n=n-1&t=1000',
    'textfold://open?paper=2512.23916&n=n-1&t=1.5',
    'textfold://open?paper=2512.23916&n=n-1%3Cscript%3E',
    'textfold://open?paper=2512.23916&level=Key',
    'textfold://open?paper=2512.23916&level=all',
    'textfold://open?paper=2512.23916&lang=xx',
    'textfold://open?paper=2512.23916&lang=zh-hant',
    'textfold://read?paper=2512.23916',                           // not open
    'textfold://open/more?paper=2512.23916',
    'textfold://someone@open?paper=2512.23916',
    'textfold:open?paper=2512.23916',
    'https://open?paper=2512.23916',
    'not a link',
    null,
  ]) {
    assert.equal(parse(link), null, String(link));
  }
});

test('a later part of a paragraph parse.py split (u6~2) is a paragraph like any other', () => {
  const parts = parse('textfold://open?paper=pdf-4932df23a9594286&u=u6~2&to=u85~3&level=brief');
  assert.deepEqual(parts, { paper: 'pdf-4932df23a9594286', u: 'u6~2', to: 'u85~3', level: 'brief' });
  assert.equal(readerUrl(BASE, parts), `${BASE}/p/pdf-4932df23a9594286#u=u6~2&to=u85~3&level=brief`);
  assert.equal(parse('textfold://open?paper=pdf-4932df23a9594286&u=u6~2/x'), null);   // still no other character
});

test('the link among the arguments Windows and Linux start the app with', () => {
  assert.equal(fromArgv(['C:\\TextFold\\TextFold.exe', '--allow-file-access-from-files', 'textfold://open?paper=2512.23916']),
    'textfold://open?paper=2512.23916');
  assert.equal(fromArgv(['/usr/bin/textfold', '.']), null);
  assert.equal(fromArgv(undefined), null);
});
