<div align="center">

<img src="docs/assets/logo.svg" width="72" alt="PaperFold">

# PaperFold

**Zoom any text for your better understanding**

<img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-6B5CE7?style=flat-square">
<img alt="12 languages" src="https://img.shields.io/badge/languages-12-6B5CE7?style=flat-square">
<img alt="Runs on your computer" src="https://img.shields.io/badge/runs-on_your_computer-E08A3C?style=flat-square">
<a href="LICENSE"><img alt="Apache License 2.0" src="https://img.shields.io/badge/license-Apache_2.0-6B5CE7?style=flat-square"></a>

**English** · [简体中文](README.zh-CN.md)

**[Try it →](https://chenxiachan.github.io/paperfold-gallery/)** arXiv papers from different fields, nothing to install.

<br>

<img src="docs/assets/zoom.gif" width="880" alt="A paper folding from its full text into a map of its sections, and back">

<br><br>

### Also for agent output

Your agent writes more than you have time to read. A [Claude Code mod](https://code.claude.com/docs/en/plugins/mods/overview) folds every reply the same way, one key per level. [More ↓](#in-claude-code)

<img src="docs/assets/textfold.gif" width="880" alt="A reply in Claude Code folding from the full text to two sentences a paragraph, then one, and back, one key at a time">

</div>

## What's new

- **October 2026: your agent's replies fold too.** [TextFold](#in-claude-code) puts the five levels on every Claude Code reply. Press 5 for the answer in one sentence, 1 for every word.
- **October 2026: more than arXiv.** Paste the link or DOI of a paper on PubMed Central, bioRxiv or medRxiv, or a Wikipedia article in any language, or drag in a Markdown file of your own. Each opens at the same five levels.

## Read with less in your head

A paper asks you to hold its whole argument in mind while you read it one paragraph at a time. PaperFold holds the argument for you. Fold the paper to see how its sections build on each other, unfold the part you care about, and the sentence you were reading never leaves the screen.

| | Level | Each paragraph becomes | In whose words |
|:-:|---|---|---|
| **1** | **Full** | the paragraph as written | the authors' |
| **2** | **Brief** | its one to three key sentences, verbatim | the authors' |
| **3** | **Key** | its point and the reason for it | AI |
| **4** | **Takeaway** | one line on the spine of its section | AI |
| **5** | **Topic** | a few words; the paper becomes a map of section cards | AI |

## What you get

- **Words that travel.** As you zoom, every word that stays slides to its new place and the rest fade around it.
- **Zoom under your fingers.** Pinch, ⌘-scroll or drag the level bar. Stop halfway, turn back, or open one paragraph alone.
- **Always know who is speaking.** The authors' words are set in a serif and AI's in a sans serif. Each paragraph is colored by its role in the argument.
- **Ask, and see the evidence.** Ask about a passage or about the whole paper. Every answer cites the paragraphs it rests on, one click away.
- **Notes that zoom with the paper.** Highlight and write in the margin, and what you marked stays as you zoom out. Export to Obsidian, PDF or JSON.
- **Your language.** Twelve languages, translated sentence by sentence, with every formula as typeset.

<table>
<tr>
<td width="50%"><img src="docs/assets/notes.png" alt="Highlights in the full text and a note in the margin"></td>
<td width="50%"><img src="docs/assets/keep.png" alt="The highlighted passages kept at the Takeaway level"></td>
</tr>
<tr>
<td align="center"><sub>Highlight and write in the margin…</sub></td>
<td align="center"><sub>…and keep what you marked as you zoom out.</sub></td>
</tr>
</table>

## Get started

```bash
git clone https://github.com/chenxiachan/paperfold.git
cd paperfold
python3 -m pip install -r requirements.txt
python3 -m adr serve
```

Open `http://localhost:3017`, which the last command prints. The first time, [connect a model](#connect-a-model); then paste the link or DOI of a paper on arXiv, PubMed Central, bioRxiv or medRxiv, or a Wikipedia article, or drag in a Markdown file, and pick a language.

You need Python 3.9 or newer (the one macOS ships with works). An arXiv paper needs its HTML version, as most papers since late 2023 have; a bioRxiv or medRxiv preprint, or a Wikipedia article in any language, is read from the site itself; any other paper needs its open full text in [Europe PMC](https://europepmc.org) (open-access articles in PubMed Central, and preprints such as Research Square's); a Markdown file needs nothing.

## Connect a model

PaperFold uses a model you already have, and there is no account to create. It looks for one when it starts; if it finds none, the first page offers the ways in.

| You have | What to do |
|---|---|
| Claude Code, Codex or Pi | Nothing. PaperFold finds it and uses it. |
| A ChatGPT plan | Click **Use my ChatGPT plan**. A small bridge starts on your computer and signs in with your account (needs Node.js). |
| Nothing yet | Click **OpenRouter in one click**. Authorize once, and free models are ready. |
| An API key | **Settings › Add provider**: Anthropic, OpenAI, DeepSeek, Qwen, Zhipu GLM, Kimi, MiniMax, Google, Ollama, or any OpenAI-compatible endpoint. |

## In the reader

| Do | To |
|---|---|
| Pinch, or ⌘ / Ctrl + scroll | zoom around the pointer |
| `1` to `5` | jump to a level |
| Click a paragraph | open just that paragraph |
| Select text | highlight, write a note, or ask |
| **Ask the paper**, bottom right | ask about the whole paper |
| `L` | next language |

## Share a paper

```bash
python3 -m adr export 2201.11903
```

This writes one self-contained HTML file to `out/2201.11903/` that opens anywhere without a server. PaperFold's license covers its code: a paper, and the levels and translations made from it, stay under the license its authors chose, shown under every title. Most arXiv papers allow reading but not redistribution, so share a page only when that license allows it, as Creative Commons licenses do.

## In Claude Code

TextFold puts the five levels on every reply in Claude Code. Press 5 for the answer in one sentence, 3 for the point of every paragraph, 1 for every word. Nothing is paraphrased, so at every level you read exactly what Claude said.

<details>
<summary><b>Install it, and see what each level gives you</b></summary>

<br>

It needs Claude Code 2.1.287 or later, in the terminal or in the Code tab of the Desktop app.

```bash
claude plugin marketplace add chenxiachan/paperfold
claude plugin install textfold@paperfold
```

| Key | Level | What you get |
|:-:|---|---|
| **1** | **Full** | every word Claude wrote |
| **2** | **Brief** | each point, with the reason behind it |
| **3** | **Points** | just the points, at a glance |
| **4** | **Outline** | the map of a long reply: its sections, and what each one says |
| **5** | **Gist** | the answer, in one sentence |

Type the digit while the prompt is empty, or pick a level in the row above the prompt. Short replies stay whole: one under about 80 words, or one a fold would barely shorten, always shows as written.

**Why you can trust a fold.** TextFold asks Claude to lead with the point: the answer first in every reply, the key sentence first in every paragraph. A fold keeps what Claude put first. There is no second model and no summary, so a fold costs nothing, takes no time, and never puts words in Claude's mouth.

More in [plugins/textfold](plugins/textfold/README.md).

</details>

<br>

<div align="center">

**If PaperFold makes papers easier to read, ⭐ star it so others can find it.**

</div>

---

<div align="center">

[Apache 2.0](./LICENSE) © 2026 Xia Chen · [Development](docs/DEVELOPMENT.md) · [Contributing](CONTRIBUTING.md) · [Feedback](https://github.com/chenxiachan/paperfold/issues)

</div>
