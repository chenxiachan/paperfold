// A reply folded to fewer words, from its own sentences: no model call, nothing rewritten.
//
// It works because the style section asks Claude to open every paragraph and list item with the sentence that
// states its point. Folding then keeps a prefix of what Claude wrote: the first sentence or two of each
// paragraph, the first sentence of each item, the headings, and at the last level the reply's first sentence.

export const LEVELS = ['Full', 'Brief', 'Points', 'Outline', 'Gist'] as const

type Kind = 'heading' | 'code' | 'list' | 'table' | 'quote' | 'para' | 'rule'
type Block = { kind: Kind; lines: string[] }

const FENCE = /^\s*(`{3,}|~{3,})/
const HEADING = /^\s{0,3}#{1,6}\s/
const ITEM = /^(\s*)([-*+]|\d+[.)])\s+/
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/

/** A markdown text as blocks: headings, code, lists, tables, quotes, paragraphs. */
export function blocks(md: string): Block[] {
  const out: Block[] = []
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  let i = 0
  while (i < lines.length) {
    const line = lines[i] ?? ''
    if (!line.trim()) {
      i++
      continue
    }
    const fence = FENCE.exec(line)
    if (fence) {
      const mark = fence[1] ?? '```'
      const buf = [line]
      i++
      while (i < lines.length) {
        const l = lines[i] ?? ''
        buf.push(l)
        i++
        if (l.trim().startsWith(mark)) break
      }
      out.push({ kind: 'code', lines: buf })
      continue
    }
    if (HEADING.test(line)) {
      out.push({ kind: 'heading', lines: [line] })
      i++
      continue
    }
    if (RULE.test(line)) {
      out.push({ kind: 'rule', lines: [line] })
      i++
      continue
    }
    const kind: Kind = /^\s*\|/.test(line) ? 'table' : /^\s*>/.test(line) ? 'quote' : ITEM.test(line) ? 'list' : 'para'
    const buf = [line]
    i++
    while (i < lines.length) {
      const l = lines[i] ?? ''
      if (!l.trim() || FENCE.test(l) || HEADING.test(l)) break
      if (kind === 'para' && ITEM.test(l)) break   // a paragraph that runs into a list
      buf.push(l)
      i++
    }
    out.push({ kind, lines: buf })
  }
  return out
}

const ABBREV = /\b(?:e\.g|i\.e|etc|vs|cf|al|approx|Dr|Mr|Ms|Fig|Eq|No)\.$/i

/** The text's first sentence, and whether more follows it. Inline code is never cut; a Chinese or Japanese stop
 *  ends a sentence without a space after it. */
export function firstSentence(text: string): { head: string; more: boolean; rest: string } {
  let inCode = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i] ?? ''
    if (c === '`') {
      inCode = !inCode
      continue
    }
    if (inCode) continue
    if ('。！？'.includes(c)) return cut(text, i + 1)
    if (!'.!?'.includes(c)) continue
    const after = /^([*_)"'”’\]]*)(\s+|$)/.exec(text.slice(i + 1))
    if (!after) continue   // "3.5", "a.b", "...": not a sentence's end
    if (ABBREV.test(text.slice(0, i + 1))) continue
    return cut(text, i + 1 + (after[1] ?? '').length)
  }
  return { head: text.trim(), more: false, rest: '' }
}

function cut(text: string, at: number) {
  const rest = text.slice(at).trim()
  return { head: balance(text.slice(0, at).trim()), more: rest.length > 0, rest }
}

/** Closes the bold or code span a cut left open. */
function balance(s: string) {
  if ((s.match(/\*\*/g) ?? []).length % 2) s += '**'
  if ((s.match(/`/g) ?? []).length % 2) s += '`'
  return s
}

function sentences(text: string, n: number) {
  let rest = text.trim()
  const out: string[] = []
  let more = false
  for (let k = 0; k < n && rest; k++) {
    const s = firstSentence(rest)
    out.push(s.head)
    rest = s.rest
    more = s.more
  }
  return { text: out.join(' '), more }
}

/** A list's items: the marker, the indent and the item's text (its continuation lines joined). */
function items(b: Block) {
  const out: { indent: number; marker: string; text: string }[] = []
  for (const line of b.lines) {
    const m = ITEM.exec(line)
    if (m) out.push({ indent: (m[1] ?? '').length, marker: m[2] ?? '-', text: line.slice(m[0].length) })
    else if (out.length) out[out.length - 1]!.text += ' ' + line.trim()
  }
  return out
}

export function words(md: string) {
  const plain = md.replace(/```[\s\S]*?```/g, ' ')
  const cjk = (plain.match(/[぀-ヿ㐀-鿿豈-﫿]/g) ?? []).length
  const latin = (plain.replace(/[぀-ヿ㐀-鿿豈-﫿]/g, ' ').match(/[A-Za-z0-9][\w'’-]*/g) ?? []).length
  return cjk + latin
}

/** Below this many words a reply is read whole: there is nothing in "Done, the tests pass." to fold. */
export const MIN_WORDS = 80
/** A fold must hide at least this share of a reply, or the reader would not see that anything changed. */
export const MIN_HIDDEN = 0.25

/** Words as reading effort: a Chinese or Japanese character reads as about 1/1.6 of an English word. */
function reading(md: string) {
  const plain = md.replace(/```[\s\S]*?```/g, ' ')
  const cjk = (plain.match(/[぀-ヿ㐀-鿿豈-﫿]/g) ?? []).length
  return words(md) - cjk + cjk / 1.6
}

/** Whether a reply is worth showing folded: long enough to need it, and the fold hides enough of it. */
export function worthFolding(md: string, folded: string) {
  const all = reading(md)
  return all >= MIN_WORDS && 1 - reading(folded) / all >= MIN_HIDDEN
}

const MORE = ' …'

/** The text at a level: 1 Full (as written), 2 Brief, 3 Points, 4 Outline, 5 Gist. */
export function fold(md: string, level: number): { text: string; total: number; shown: number } {
  const total = words(md)
  if (level <= 1) return { text: md, total, shown: total }
  const out: string[] = []
  let underHeading = true   // at Outline, a section shows its heading and its first sentence
  let first = true          // at Gist, the reply shows its first sentence
  for (const b of blocks(md)) {
    if (level === 5 && !first) break
    switch (b.kind) {
      case 'rule':
        break
      case 'heading':
        if (level <= 4) out.push(b.lines[0] ?? '')
        underHeading = true
        break
      case 'code':
      case 'table': {
        const rows = b.lines.length - 2   // less the fences, or the header and its rule
        if (level === 2 && b.lines.length <= 8) out.push(b.lines.join('\n'))
        else if (level <= 3) out.push(b.kind === 'code' ? `\`⋯ ${Math.max(rows, 1)} lines of code\`` : `\`⋯ a table of ${Math.max(rows, 1)} rows\``)
        break
      }
      case 'list': {
        const its = items(b).filter((it) => level === 2 || it.indent === 0)
        if (level <= 3) {
          out.push(its.map((it) => {
            const s = firstSentence(it.text)
            return `${' '.repeat(it.indent)}${it.marker} ${s.head}${s.more ? MORE : ''}`
          }).join('\n'))
        } else if (underHeading || (level === 5 && first)) {
          const it = its[0]
          if (it) {
            const s = firstSentence(it.text)
            out.push(s.head + (s.more || its.length > 1 ? MORE : ''))
          }
          underHeading = false
          first = false
        }
        break
      }
      case 'quote':
      case 'para': {
        const raw = b.lines.map((l) => (b.kind === 'quote' ? l.replace(/^\s*>\s?/, '') : l).trim()).join(' ')
        if (level >= 4 && !underHeading) break
        const s = sentences(raw, level === 2 ? 2 : 1)
        out.push((b.kind === 'quote' ? '> ' : '') + s.text + (s.more ? MORE : ''))
        underHeading = false
        first = false
        break
      }
    }
  }
  const text = out.join('\n\n')
  return { text, total, shown: words(text) }
}
