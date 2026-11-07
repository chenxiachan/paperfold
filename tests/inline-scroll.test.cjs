// A box set in a line of text that scrolls across (a long formula, an unbreakable atom) scrolls across only: with
// overflow-x alone, overflow-y is auto too, and where scrollbars take room (Windows, Linux) every formula a few pixels
// taller than its box drew a vertical scrollbar beside it (#117).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const web = path.join(__dirname, '..', 'textfold', 'web');
const rules = (file) => [...fs.readFileSync(path.join(web, file), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  .matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, sel, body]) => ({ sel: sel.trim(), body }));

test('every scroll box in a line scrolls across and never up and down', () => {
  const inline = rules('reader.css').filter(({ sel, body }) => /overflow-x:\s*auto/.test(body) &&
    (/display:\s*inline-(?:flex|block)/.test(body) || /(?:^|[\s,>(])math\b/.test(sel)));
  assert.ok(inline.length >= 4, inline.map((r) => r.sel).join('\n'));   // (MathML, KaTeX, .inline-math, an atom)
  for (const { sel, body } of inline) assert.match(body, /overflow-y:\s*hidden/, sel);
});
