import { expect, test } from 'claude-code/testing'

const REPLY =
  'The bug was in the cache key, and it is fixed. Two requests for the same paper shared one key, so the second request read the first one’s translation. It only showed when two languages were open at once, which is why the tests missed it.\n\n' +
  'The key now includes the language. That makes each translation its own entry, and old entries stay valid because English keeps its old key. The tests now open two languages side by side, and they pass on a laptop in about a minute.'
const SHORT = 'Done. The tests pass, and the branch is ready to merge.'

const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 100, scroll: { offset: 0, bodyRows: 10 }, view: {} },
} as const
const MESSAGE = { component: 'AssistantMessage', props: { text: REPLY, isFirstOfReply: true } } as const
const SHORT_MESSAGE = { component: 'AssistantMessage', props: { text: SHORT, isFirstOfReply: true } } as const
const FOLDED = { type: 'Text', text: /^ {2}\w+ · \d+ of \d+ words · 1 unfolds$/ } as const

test('the system prompt asks Claude for replies that fold', async ($, on) => {
  // The engine's own prompt, which the mod adds its section after
  on('prompt.compose', async () => ({ sections: [{ id: 'intro', text: 'You are Claude Code.', scope: 'shared' }] }))
  const { sections } = await $.prompt.compose({
    model: 'claude-opus-5-5', promptModel: 'claude-opus-5-5', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [],
  })
  expect(sections[0]?.id).toBe('intro')
  const style = sections.find((s) => s.id === 'textfold:style')
  expect(style?.scope).toBe('session')
  expect(style?.text).toContain('Open every paragraph and every list item with a sentence that states its point')
})

test('a level picked in the band folds the replies, and 1 unfolds them, on the terminal and the desktop', async ($, on) => {
  // Claude Code's own drawing: a reply as its text (the band, empty)
  on('ui.render', async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    if (e.component !== 'AssistantMessage') return Box({ children: [] })
    return Text({ children: [e.props.text] })
  })
  for (const surface of ['terminal', 'desktop'] as const) {
    const band = await $.ui.mount({ plugin: 'textfold', surface, ...BAND })
    await band.press({ key: 'level-1' })
    const message = await $.ui.mount({ plugin: 'textfold', surface, ...MESSAGE })
    expect(await message.find(FOLDED)).toBeUndefined()

    expect((await message.find({ type: 'Text' }))?.text).toBe(REPLY)

    await band.press({ key: 'level-3' })
    expect((await message.find(FOLDED))?.text).toBe('  Points · 17 of 89 words · 1 unfolds')
    expect((await message.find({ type: 'Text' }))?.text).toBe(
      'The bug was in the cache key, and it is fixed. …\n\nThe key now includes the language. …',
    )

    await band.press({ key: 'level-1' })
    expect(await message.find(FOLDED)).toBeUndefined()
    await message.unmount()
    await band.unmount()
  }
})

test('a short reply stays as written at every level', async ($, on) => {
  on('ui.render', async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    if (e.component !== 'AssistantMessage') return Box({ children: [] })
    return Text({ children: [e.props.text] })
  })
  const band = await $.ui.mount({ plugin: 'textfold', surface: 'terminal', ...BAND })
  const message = await $.ui.mount({ plugin: 'textfold', surface: 'terminal', ...SHORT_MESSAGE })
  for (const key of ['level-3', 'level-5'] as const) {
    await band.press({ key })
    expect(await message.find(FOLDED)).toBeUndefined()
    expect((await message.find({ type: 'Text' }))?.text).toBe(SHORT)
  }
  await message.unmount()
  await band.unmount()
})

test('a session starts at the level the setting names', { options: { level: 'Points' } }, async ($, on) => {
  on('ui.render', async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    if (e.component !== 'AssistantMessage') return Box({ children: [] })
    return Text({ children: [e.props.text] })
  })
  const band = await $.ui.mount({ plugin: 'textfold', surface: 'terminal', ...BAND })
  const message = await $.ui.mount({ plugin: 'textfold', surface: 'terminal', ...MESSAGE })
  expect((await message.find(FOLDED))?.text).toBe('  Points · 17 of 89 words · 1 unfolds')
  await band.press({ key: 'level-1' })
  expect(await message.find(FOLDED)).toBeUndefined()
  await message.unmount()
  await band.unmount()
})
