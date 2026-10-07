/** The level a reply is read at: 1 Full, 2 Brief, 3 Points, 4 Outline, 5 Gist. */
export type Level = 1 | 2 | 3 | 4 | 5

declare module 'claude-code' {
  interface PluginState {
    textfold: { level: Level }
  }
}
