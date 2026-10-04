# Notes format (`paperfold/notes`, version 1)

A reader's highlights, notes and questions on one paper. One file per paper: `papers/<arXiv id>/notes.json` when the
local server runs; in a static page, the same records in the browser's storage. Everything that leaves the reader
(Markdown for Obsidian, and later ThoughtDAG nodes) is converted from this format, so it is the one contract between
them. Files written before the name PaperFold say `"format": "dynamic-reader/notes"`; it is the same format, and a
reader of it accepts both names. It follows the W3C Web Annotation model loosely: a note has a body and a target, and the target is anchored in
more than one way, so it can be found again when the text around it changes.

```json
{
  "format": "paperfold/notes",
  "version": 1,
  "made_by": "PaperFold · https://github.com/chenxiachan/paperfold",
  "paper": { "id": "2605.00089", "version": "v1", "title": "…", "url": "https://arxiv.org/abs/2605.00089v1" },
  "notes": [
    {
      "id": "n-k3f9a2qx",
      "kind": "highlight",
      "created": "2026-10-03T10:00:00Z",
      "updated": "2026-10-03T10:00:00Z",
      "anchor": {
        "unit": "S2.SS3.p2",
        "section": "S2.SS3",
        "lang": "en",
        "level": 4,
        "tokens": [12, 30],
        "sents": [1],
        "quote": { "exact": "…", "prefix": "…", "suffix": "…" }
      },
      "text": "",
      "thread": []
    }
  ]
}
```

## Fields

- **id**: stable for the life of the note. In Markdown it becomes the Obsidian block id (`^n-k3f9a2qx`), so other
  notes can link to it, and the reader opens at it with `#n=<id>`.
- **kind**: `highlight` (marked text, maybe with a note), `note` (written first), `ask` (a conversation with the model
  about the passage: a question, its answer, follow-up questions and theirs).
- **anchor**, four ways of finding the passage again, from the most precise to the most robust:
  - `unit`: the paragraph (or list item, caption) in the parsed paper. `section` is its section, for grouping. A note
    can also be on a section itself: then `unit` is null, `section` is the section, and `on` says where, `summary` (the
    section's one-line summary, written by the model; `tokens` count its words) or `title`. A conversation about the
    whole paper (the reader's chat) has `on: "paper"`, `unit` and `section` null, and an empty quote; it is listed
    first, under "The whole paper".
  - `lang`, `level`: the language and zoom level (4 Full, 3 Brief, 2 Key, 1 Takeaway, 0 Topic; the numbers are what is stored, the names are the reader's) it was made at.
  - `tokens`: first and last token, inclusive, in the unit's full text in `lang`. A selection in a written level
    (Key, Takeaway) maps back to the words of the full text the model's words came from; `null` when the selection
    held only words the model wrote itself.
  - `sents`: the sentences of the unit the passage lies in. Translation is sentence by sentence, so these hold in every
    language: a note made in Chinese is shown on the same sentences in English.
  - `quote`: the selected text exactly, with up to 40 characters before and after (W3C `TextQuoteSelector`). This is
    what finds the passage again when ids and token numbers no longer fit (a new arXiv version of the paper).
- **text**: the reader's own note, plain text with line breaks.
- **thread**: the turns of an `ask` note, in order, each `{ "q", "a", "takeaway", "cites", "next", "model", "lang", "at" }`:
  the question, the answer (Markdown), the answer in one sentence, the units of the paper the answer rests on (in the
  order the answer first cites them), two questions to go on with, the model id, the answer's language and when it was
  given. The answer cites inline: `[[S3.p2.1]]` right after a statement is the unit it rests on, `[[?]]` ends a sentence
  that is the model's own inference rather than the paper's, and `[[!12]]` is a citation that named no unit (kept, so it
  shows as one that went wrong). Answers from before inline citations have none and list their units in `cites` only. Each question is asked with the turns before it (the last
  six), so a follow-up can say "and why is that?". While the model is answering, the last turn has an empty `a` and
  `pending: true`; when it failed, `error`. (The first notes stored a single turn as `ask`; it reads as a thread of
  one.)

## Converting

- To Obsidian (done): one Markdown note per paper; a highlight is a quote with the block id `^<id>`; a conversation is a
  `[!question]` callout, the first question its title and each follow-up in bold; every note links back to the reader.
  The note ends with a line saying it was made with PaperFold.
- To PDF (done): the browser prints the notes in reading order (each passage, the reader's note, the conversation
  with its cites and the level it was asked at), with the PaperFold mark at the end.
- To ThoughtDAG (planned): a highlight or note becomes a material node quoting the passage (paper id, unit, quote); a
  conversation becomes a chain of question nodes hanging from it, one per turn.

## How a note is shown at each level

- Full, Brief: the words in `tokens` are marked when the note's language is the one being read; in another language,
  the sentences in `sents` are marked more lightly.
- Key, Takeaway: the written words that came from those tokens are marked.
- Wherever none of the passage is on screen (a sentence the Brief level leaves out, a chip on the Topic map), the
  paragraph carries a mark, so nothing a reader wrote disappears when they zoom out.
- The reader's own notes (with text) sit in the left margin, the conversations with the model in the right margin
  above the paragraph's links: at Full and Brief in full, at Key shortened to the question and its one-line answer.
  At Takeaway and Topic only the paragraph's mark stays; hovering it shows its notes.
- A note on a section's summary is marked on the summary (shown at Key, Takeaway, Topic); its cards hang after the
  section's heading, which also carries a mark.
- A conversation keeps the level it was started at (`anchor.level`), shown with it: what was selected may not be on
  screen at another level.

## Not yet

- Finding a passage again by its quote after the paper's text changed (a regenerated summary, a new arXiv version):
  the quote is stored for it.
- Handwriting. When it comes it will be a body of its own (strokes) on the same anchors.
