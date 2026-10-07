import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Level } from '../types'
import { fold, LEVELS, worthFolding } from './fold'

// The level every reply is read at: 1 Full (as written) to 5 Gist. Full until the reader picks another.
const level = atom({ plugin: 'textfold', key: 'level' } as const, 1 as Level)

// What Claude is asked, so that a fold of its reply still reads: the point first, at every scale. It changes
// the order of what Claude says, not what it says or how much.
const STYLE = `# Replies that fold
The person reading this session can fold your replies with one key: to each paragraph's first sentence or two, to the headings, or to the reply's first sentence. Write so that every fold still reads:
- Open the reply with one sentence that answers, or that says what you did.
- Open every paragraph and every list item with a sentence that states its point and reads on its own; reasons, details and caveats come after it.
- Give a reply longer than four paragraphs a few short headings.
This changes the order of what you write, not its content or its length.`

export const register: Register = (on) => {
  // Approach B: Claude writes foldable replies, so folding needs no model call
  on('prompt.compose', async ($, e, next) => {
    const { sections } = await next(e)
    return { sections: [...sections, { id: 'textfold:style', text: STYLE, scope: 'session' }] }
  })

  // Each text block of a reply, drawn by Claude Code at the chosen level, with a line saying how much is folded;
  // a short block, or one the fold would barely shorten, as written
  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    const n = await read($, level)
    if (n <= 1) return next(e)
    const f = fold(e.props.text, n)
    if (!worthFolding(e.props.text, f.text)) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const theirs = await next({ ...e, props: { ...e.props, text: f.text || '…' } })
    return (
      <Box flexDirection="column">
        {theirs}
        <Text dimColor>{`  ${LEVELS[n - 1]} · ${f.shown} of ${f.total} words · 1 unfolds`}</Text>
      </Box>
    )
  })

  // Above the prompt: the five levels; with the prompt empty, a digit picks one
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const n = await read($, level)
    const { Box, Button, Text } = $.ui.resolve(e)
    const theirs = await next(e)
    const row = (
      <Box flexDirection="row" columnGap={2}>
        <Text dimColor>fold</Text>
        {LEVELS.map((name, i) => (
          <Button
            key={`level-${i + 1}`}
            label={name}
            hotkey={String(i + 1)}
            plain
            dimColor={n !== i + 1}
            onPress={() => update($, level, () => (i + 1) as Level)}
          />
        ))}
      </Box>
    )
    return theirs ? (
      <Box flexDirection="column">
        {theirs}
        {row}
      </Box>
    ) : (
      row
    )
  })
}
