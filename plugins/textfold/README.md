# TextFold for Claude Code

Your agent writes more than you have time to read. TextFold folds every Claude Code reply to the level you need, from every word to the answer in one sentence, with one key. A [mod](https://code.claude.com/docs/en/plugins/mods/overview) for Claude Code, from [PaperFold](../../README.md).

<img src="../../docs/assets/textfold.gif" width="880" alt="A reply in Claude Code folding from the full text to two sentences a paragraph, then one, and back, one key at a time">

| Key | Level | What you get |
|:-:|---|---|
| **1** | **Full** | every word Claude wrote |
| **2** | **Brief** | each point, with the reason behind it |
| **3** | **Points** | just the points, at a glance |
| **4** | **Outline** | the map of a long reply: its sections, and what each one says |
| **5** | **Gist** | the answer, in one sentence |

Type the digit while the prompt is empty, or pick a level in the row above the prompt. A folded reply tells you how much of it you are seeing, and `1` brings back every word. Short replies stay whole: one under about 80 words, or one a fold would barely shorten, always shows as written.

**Start folded.** A session starts at Full. To start at another level, run `/config` and set **Starting level**; in the session, the row above the prompt and the keys 1 to 5 still change it.

## Why you can trust a fold

Nothing is paraphrased. TextFold adds a short section to the system prompt that asks Claude to lead with the point: the answer first in every reply, and the sentence that states its point first in every paragraph and list item. A fold keeps what Claude put first. There is no second model and no summary, so a fold costs nothing, takes no time, and never puts words in Claude's mouth.

## Install

It needs Claude Code 2.1.287 or later, in the terminal or in the Code tab of the Desktop app.

```bash
claude plugin marketplace add chenxiachan/paperfold
claude plugin install textfold@paperfold
```

To try it from a clone without installing it, start Claude Code with `claude --plugin-dir paperfold/plugins/textfold`.

## Good to know

- The section changes the order of what Claude writes, not what it says or how much. Check on your own work that Claude does it as well as before.
- Turning the mod on changes the system prompt, so the prompt cache starts over once in that session.
- The VS Code extension and `claude -p` draw nothing of a mod; there the section still applies and the replies are not folded.

The tests run with `claude plugin test plugins/textfold`.
