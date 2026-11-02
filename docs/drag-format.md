# Dragged out of the reader (`textfold/drag`, version 1)

What the reader gives an app when a part of a text is dragged into it (a notes app, an editor): the text as it reads
at the level shown, where it is, and a `textfold://` link back to exactly there, which the desktop app opens
(`desktop/README.md`, Links). Fields may be added without a new version; a field renamed or removed comes with
version 2.

## What is dragged

| Dragged | `kind` | The link | `text` |
|---|---|---|---|
| a paragraph, by the handle beside it on hover (its text stays selectable) | `paragraph` | `u=<id>&level=<level>` | the paragraph at its level |
| a section's heading, by its handle: the whole section, its subsections with it | `section` | `s=<id>&level=<level>` | the section as it reads at that level: at Key and Takeaway its summary, then a `- ` bullet per paragraph; at Brief and Full a paragraph each, blank lines between (Brief keeps its `…`); each subsection after its own heading (and summary) |
| a section's one-line summary (Key, Takeaway), by its handle | `summary` | `s=<id>&level=<level>` | the summary |
| an equation set apart (Full, Brief), by its handle | `equation` | `u=<the paragraph it goes with>&eq=<id>&level=<level>` (`s=` with `eq=` when its section has no paragraph) | the equation in LaTeX as `$$…$$`, its number as `\tag{…}` (`\tag*{…}` for one without brackets), several rows in `\begin{gathered}` |
| a section's card on the Topic map, grabbed anywhere (no handles there) | `section` | `s=<id>&level=topic` | as the card reads: its summary (the line under its title, which goes in `heading`), then on a line of its own its paragraphs' topics (its chips), joined by ` · ` |
| a selection in one paragraph | `selection` | `u=<that paragraph>&level=<level>` (`s=` when it is on a heading or summary alone) | the selected words |
| a selection over several paragraphs | `selection` | `u=<the first>&to=<the last>&level=<level>` | the selected words, a paragraph each (a heading or summary it crosses too), blank lines between; an equation it crosses whole, as `$$…$$` (on equations alone, the link is the first one's) |
| a highlight's or a note's card, in the margin or the notes list | `note` | `n=<note id>` | the note's text, else its quote |
| a conversation's card (Ask), in the margin or the notes list | `ask` | `n=<note id>` | the answer in one sentence |
| one message of a conversation, in the chat (the whole paper) or a note's window, by its handle; or words selected in it | `ask` | `n=<note id>&t=<turn>` | the question, or the answer: its Markdown, a citation as its label, `(§3 ¶2)` |

Every link is `textfold://open?paper=<id>&…&lang=<code>`, the language the text was read in, values URL-encoded.
`t=<turn>` is the place of a turn in its conversation, from 0: the chat, or the note's window, opens scrolled to it.
`to=<paragraph>` goes with `u=`: the reader flashes every paragraph from `u` to `to` together. `s=` flashes the whole
section, its subsections with it. `eq=<equation>` goes with `u=` (or `s=`): the reader opens at the equation where the
level shows it (Full, Brief), else at that paragraph, as a reader from before `eq=` does.
(`chip`, a kind of the first drafts of this format, is not made: a chip goes with its card.)

## The four types

- `text/plain`: Markdown that reads well anywhere: the text (a note's or a conversation's quote) as a quote, each of
  its lines a paragraph of the quote (bullets one after another one list), then the note's text, or the question in
  bold and the answer, then `— [<title> › <section>](textfold://…)`.
- `text/uri-list`: the link.
- `text/html`: the same, as a `<blockquote>` and a link, in a `<div data-textfold="…">` that holds the JSON below:
  a custom type may not survive from one app to another, HTML does.
- `application/x-textfold+json`: the JSON.

## The JSON

```json
{
  "format": "textfold/drag",
  "version": 1,
  "paper": "2512.23916",
  "title": "…",
  "authors": ["…"],
  "citekey": "wei2022",
  "section": { "id": "S3", "num": "3", "title": "Method" },
  "heading": "3 Method",
  "kind": "section",
  "level": "key",
  "lang": "en",
  "text": "…",
  "written": true,
  "units": ["S3.p1", "S3.p2"],
  "quote": "…",
  "comment": "…",
  "link": "textfold://open?paper=2512.23916&s=S3&level=key&lang=en"
}
```

- **paper**, **title**, **authors**: the document's id, its title as the reader shows it (the name the reader gave it
  in the library, else its title in `lang`), its authors as stored.
- **citekey**: the Zotero item's, for a document read from an item's own file (its meta's `zotero`); left out
  otherwise.
- **section**: the section it is in, `null` outside any (a document's opening text, the whole paper).
- **heading**: for a section (its heading's handle, or its card on the Topic map), its heading as the reader shows it,
  number and title. Left out otherwise.
- **equation**: for an equation, its id (`S2.E1` in an arXiv paper, `eq-heat` for one a Markdown file labels
  `\label{eq:heat}`). Left out otherwise.
- **level**: the level shown when it was dragged: `topic`, `takeaway`, `key`, `brief` or `full`.
- **lang**: the language it was read in.
- **text**: what was dragged, as it reads at that level, in plain text: a formula as `$LaTeX$`, a gap as `…`.
- **written**: `true` when `text` is the model's words: a paragraph or selection at Key or Takeaway, a summary, a
  card of the Topic map, a conversation's answer (or words selected in it). (A translation is the model's too: `lang` says which language it is.)
- **units**: the paragraphs the text holds, in reading order: a paragraph's own id; a section's, its subsections'
  included; a card's chips; every paragraph a selection touches. Left out for a summary, a note and a conversation.
- **quote**: the passage, for a note, a conversation and a selection, when there is one.
- **comment**: the reader's own words, when there are any: a note's text; a conversation's first question, or, for
  one answer, the question it answers.
- **link**: the `textfold://` link back.
