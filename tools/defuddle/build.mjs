// What the browser's button reads a page with (extension/reader.js), built into extension/vendor:
//
//   Defuddle (MIT, https://github.com/kepano/defuddle), the article of a page the way Obsidian's Web Clipper takes it,
//   with TextFold's changes below, as one script that sets self.Defuddle;
//   Readability (Apache-2.0, https://github.com/mozilla/readability), Firefox's reading view, as it comes.
//
//   cd tools/defuddle && npm ci && node build.mjs
//
// Each change replaces text that must be in Defuddle's files exactly once: a newer Defuddle that moved it stops the
// build here, to be looked at again (and the change offered upstream).
import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const mods = path.join(here, 'node_modules');
const out = path.join(here, '..', '..', 'extension', 'vendor');
const version = (name) => JSON.parse(fs.readFileSync(path.join(mods, name, 'package.json'), 'utf8')).version;

const CHANGES = [
  {
    file: 'elements/footnotes.js',
    why: 'a container that failed the check of footnotes gave its parts as footnotes all the same: a page whose ' +
         'reference links point back into its text (Elsevier) had its whole text copied as footnote 1',
    old: `        if (externalMatch < Math.max(2, Math.ceil(externalTotal * 0.75)))
            bestContainer = null;
`,
    new: `        if (externalMatch < Math.max(2, Math.ceil(externalTotal * 0.75)))
            return;   // (TextFold: not footnotes, so none of its parts either)
`,
  },
  {
    file: 'elements/footnotes.js',
    why: 'the lists that look like footnote lists (ol.references, #footnotes) went even when no footnote was found in ' +
         'them: a reference list whose items name themselves otherwise than its citations do (Elsevier) was lost',
    old: `        element.querySelectorAll(constants_1.FOOTNOTE_LIST_SELECTORS).forEach((list) => list.remove());
`,
    new: `        if (Object.keys(footnotes).length > 0)   // (TextFold)
            element.querySelectorAll(constants_1.FOOTNOTE_LIST_SELECTORS).forEach((list) => list.remove());
`,
  },
  {
    file: 'removals/selectors.js',
    why: "a selector names a page's furniture by its class: an element holding the article's own running text, or " +
         "called an abstract, is not furniture whatever else it is called (Elsevier's abstract and highlights are " +
         "div.abstract.author, which .author took for a byline), and a link inside a sentence that names something " +
         '(a citation [3], (Fig. 1)) is not a heading\'s permalink (a[href^="#"][class*="anchor"])',
    old: `        if (el.tagName === 'A' && el.closest('h1, h2, h3, h4, h5, h6')) {
            return;
        }
`,
    new: `        if (el.tagName === 'A' && el.closest('h1, h2, h3, h4, h5, h6')) {
            return;
        }
        if ((type === 'exact' && tfRunningText(el)) || tfInSentence(el)) {
            return;   // (TextFold)
        }
`,
  },
  {
    file: 'removals/selectors.js',
    why: '(the two tests the change above uses)',
    old: `function hasVisibleText(node, hidden, elementsToRemove) {`,
    new: `// TextFold: an element called an abstract (a scholarly page's abstract, highlights, summary), or one with at least
// 80 words (a CJK character half of one), a fifth or less of them in links; never a page's navigation, aside, header,
// footer, form or dialog.
function tfRunningText(el) {
    if (/^(NAV|ASIDE|HEADER|FOOTER|FORM|DIALOG|BUTTON)$/.test(el.tagName) ||
        /^(navigation|complementary|banner|contentinfo|dialog|alertdialog|menu|toolbar)$/.test(el.getAttribute('role') || '')) {
        return false;
    }
    if (/(^|[\\s_-])abstracts?($|[\\s_-])/i.test((el.getAttribute('class') || '') + ' ' + (el.id || ''))) {
        return true;
    }
    const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
    const words = text.split(' ').length + (text.match(/[\\u3040-\\u30ff\\u3400-\\u9fff\\uac00-\\ud7af]/g) || []).length / 2;
    if (words < 80) {
        return false;
    }
    let linked = 0;
    el.querySelectorAll('a').forEach((a) => { linked += (a.textContent || '').replace(/\\s+/g, ' ').trim().length; });
    return linked <= text.length / 5;
}
// TextFold: a link to a place on the page, with a letter or a digit in it, in a block (a paragraph, a list's item, a
// cell, a caption, a div a page writes its paragraphs in) that says more than the link does.
function tfInSentence(el) {
    if (el.tagName !== 'A' || !(el.getAttribute('href') || '').startsWith('#') || !/[\\p{L}\\p{N}]/u.test(el.textContent || '')) {
        return false;
    }
    const block = el.parentElement && el.parentElement.closest('p, li, td, th, dd, dt, figcaption, blockquote, div');
    const said = (s) => (s || '').replace(/\\s+/g, '').length;
    return !!block && said(block.textContent) >= said(el.textContent) + 20;
}
function hasVisibleText(node, hidden, elementsToRemove) {`,
  },
  {
    file: 'elements/images.js',
    why: "a figure's caption was the first element any of the selectors matched, in the order of the page: Elsevier's " +
         'figures hold their download links ("anchor-text") before their caption; the selectors are tried in turn now',
    old: `    const combinedSelector = captionSelectors.join(', ');
    const captionElements = element.querySelectorAll(combinedSelector);
`,
    new: `    const captionElements = captionSelectors.flatMap((s) => Array.from(element.querySelectorAll(s)));   // (TextFold)
`,
  },
];

const work = path.join(here, '.build');
fs.rmSync(work, { recursive: true, force: true });
fs.cpSync(path.join(mods, 'defuddle', 'dist'), path.join(work, 'dist'), { recursive: true, filter: (f) => !f.endsWith('.map') });
for (const c of CHANGES) {
  const f = path.join(work, 'dist', c.file);
  const src = fs.readFileSync(f, 'utf8');
  const n = src.split(c.old).length - 1;
  if (n !== 1) {
    throw new Error(`${c.file}: the text to change is there ${n} times, not once (${c.why.slice(0, 80)}…)`);
  }
  fs.writeFileSync(f, src.replace(c.old, () => c.new));
}

const notes = CHANGES.filter((c) => !c.why.startsWith('(')).map((c, i) => ` *  ${i + 1}. ${c.file}: ${c.why}`).join('\n');
fs.mkdirSync(path.join(out, 'defuddle'), { recursive: true });
await build({
  // (and the MathML-to-LaTeX converter it holds, for a formula whose source is MathML: reader.js)
  stdin: { contents: "self.Defuddle = require('./dist/defuddle.js').Defuddle; self.TFMathMLToLaTeX = require('mathml-to-latex').MathMLToLaTeX;",
           resolveDir: work, loader: 'js' },
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: 'chrome116',
  nodePaths: [mods],
  legalComments: 'inline',
  outfile: path.join(out, 'defuddle', 'defuddle.js'),
  banner: { js: `/* Defuddle ${version('defuddle')} (MIT, https://github.com/kepano/defuddle; LICENSE beside this file), with
 * temml ${version('temml')} and mathml-to-latex ${version('mathml-to-latex')} (MIT), built by TextFold's tools/defuddle/build.mjs
 * with these changes:
${notes}
 */` },
});
fs.copyFileSync(path.join(mods, 'defuddle', 'LICENSE'), path.join(out, 'defuddle', 'LICENSE'));
fs.rmSync(work, { recursive: true, force: true });

fs.mkdirSync(path.join(out, 'readability'), { recursive: true });
const rd = fs.readFileSync(path.join(mods, '@mozilla', 'readability', 'Readability.js'), 'utf8');
fs.writeFileSync(path.join(out, 'readability', 'Readability.js'),
  `/* Readability ${version('@mozilla/readability')} (Apache-2.0, https://github.com/mozilla/readability; LICENSE beside this file), as it comes */\n` + rd);
fs.copyFileSync(path.join(mods, '@mozilla', 'readability', 'LICENSE.md'), path.join(out, 'readability', 'LICENSE.md'));
for (const f of ['defuddle/defuddle.js', 'readability/Readability.js']) {
  console.log(f, Math.round(fs.statSync(path.join(out, f)).size / 1024), 'KB');
}
