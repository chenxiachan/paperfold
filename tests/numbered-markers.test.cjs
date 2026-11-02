const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const web = path.join(__dirname, '..', 'textfold', 'web');
const reader = fs.readFileSync(path.join(web, 'reader.js'), 'utf8');
const css = fs.readFileSync(path.join(web, 'reader.css'), 'utf8');
const unitNode = reader.slice(reader.indexOf('  function unitNode(uid, tag) {'),
  reader.indexOf('  const paperHead ='));

function nodeFor(marker) {
  const h = (tag, className, textContent) => ({
    tag, className, textContent, dataset: {}, children: [],
    append(...children) { this.children.push(...children); },
  });
  const context = vm.createContext({
    h, U: { u1: { role: 'item', marker, lad: { role: 'method' } } },
    unitEl: new Map(), spans: new Map(), order: new Map(),
  });
  return vm.runInContext(`${unitNode}\nunitNode('u1', 'li')`, context);
}

test('numbered and named list markers are distinguished from plain bullets', () => {
  for (const marker of ['(1)', '2.', '(a)', '④', '一、']) {
    const node = nodeFor(marker);
    const label = node.children.find(x => x.className.startsWith('mk'));
    assert.match(label.className, /mk-labeled/, marker);
    assert.equal(label.textContent, marker);
  }
  const bullet = nodeFor('•').children.find(x => x.className.startsWith('mk'));
  assert.doesNotMatch(bullet.className, /mk-labeled/);
});

test('meaningful list markers remain visible at Brief, Takeaway and Topic', () => {
  for (const level of ['2', '1', '0']) {
    assert.match(css, new RegExp(`li\\.u\\[data-l="${level}"\\] \\.mk\\.mk-labeled[^{}]*\\{[^}]*display: (?:inline|inline-block)`), level);
  }
  assert.match(css, /li\.u\.numbered\[data-l="0"\] \.tx[^{}]*\{[^}]*display: inline/);
});
