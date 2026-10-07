# PaperFold: development notes

How the reader works, how to run and extend it. For what it is and how to use it, see the [README](../README.md).
The notes format is [notes-format.md](notes-format.md).

The same semantic zoom as ThoughtDAG's plaques, applied to a paper's HTML (LaTeXML) version:

| Level | What a paragraph shows | Source |
|---|---|---|
| **Full** | the paragraph as written; key sentences in darker ink | author, verbatim |
| **Brief** | 1–3 of its sentences | author, verbatim (chosen by the model) |
| **Key** | takeaway + one sentence of reason | model, written |
| **Takeaway** | one headline sentence, on an outline with role dots | model, written |
| **Topic** | a noun phrase; the paper becomes a map of section cards | model, written |

Serif text is the author's; sans text is a summary. At every level the words that survive the next zoom-out are darker, and a level change moves each surviving word (and formula) to its new place instead of swapping the text.

## Use

```bash
python3 -m pip install -r requirements.txt   # beautifulsoup4, lxml, Pillow
python3 -m adr serve                    # http://localhost:3017  (ThoughtDAG keeps 3001)
```

The landing takes a link or ID (arXiv, PubMed Central, Europe PMC, bioRxiv, medRxiv, a DOI, Wikipedia), or a Markdown
file (the dashed box under the bar, or dropped anywhere on the page), and a language; a line under the bar names
the sources it reads; the sidebar lists every paper generated so far. In a paper,
the language menu switches between generated languages, generates a new one, or regenerates the current one.
Two languages. The paper is read in one (the menu at the top right, 12 languages: English, 简体中文, 繁體中文,
日本語, 한국어, Español, Français, Deutsch, Português, Italiano, Русский, हिन्दी): its text, and the names of its own
parts (figures, tables, theorems, references, equations). The interface speaks the reader's own: the browser's,
or the one chosen in Settings (kept in the browser, `pf-ui-lang`). A question is answered in the language it is
asked in, the interface's when that is unclear.

Where things are kept: the code in the project (`adr/`, `web/`); papers and exports in `papers/` and `out/` of the
project, or wherever `PAPERFOLD_DATA` points; settings and keys in `~/.paperfold/`.

A gallery for a free static host: `tools/gallery.json` lists one paper per field, each with its field and a line on
why it is worth reading in every gallery language (en, zh, de). `python3 tools/gallery.py --make <model>` generates
what the list lacks in a folder of its own (`out/gallery/papers`; a paper already in the library starts from there,
without its notes), and `python3 tools/gallery.py` writes `out/gallery/site/`: an index in the three languages and
each paper's static reader, opened at the Topic level. Only papers whose license lets anyone share a derivative go in
(CC BY, BY-SA, BY-NC, BY-NC-SA, CC0); `"consent": true` adds a paper whose authors agree. Before a paper goes public its text is proofread:
`--review` writes each paper's sentences and levels in every language to `out/gallery/review/`, and the corrections go
in `out/gallery/fixes/<id>.json`, which the build puts through the same assembly as the model's replies (only the
corrected fields change; the generated layers stay as they are). The corrections hold the papers' text, so they live in
the gallery's own repository, github.com/chenxiachan/paperfold-gallery (`fixes/`), not here; the build stops when a
paper's corrections are missing (`--unproofread` builds without them, for a look only). The site is published from that
repository by GitHub Pages at https://chenxiachan.github.io/paperfold-gallery/: copy `out/gallery/site` and
`out/gallery/fixes` into its clone (`out/gallery/deploy`) and push.

Models (⚙ Model & API), ported from ThoughtDAG's model access:

- **Agents on this computer**, found at startup (and on Rescan) on PATH, the login shell's PATH, the usual install
  directories and the node version managers. Claude Code, Codex and Pi run generations, each listing its own models
  (Pi brings whatever providers it is configured with); Gemini CLI, Qwen Code, opencode, Cursor Agent, Kimi CLI, Amp,
  Goose, Crush, Droid, Copilot CLI, iFlow and Aider are reported when present. Claude Code is called without the
  user's settings and CLAUDE.md (`--setting-sources project,local` in a scratch folder; again with them if that fails
  to sign in).
- **Two easy ways in** (`adr/bridges.py`, as in ThoughtDAG):
  - **ChatGPT plan, local bridge**: openai-oauth (npm) serves the plan as an OpenAI-compatible endpoint on
    127.0.0.1:10531, signed in with Codex's login (or a browser sign-in). Running, it joins the providers on its own
    (as a running Ollama does), with its text models; not running, the providers list has a row to start it (`npx -y openai-oauth@2 --detach`; `npx openai-oauth stop` stops it). On the test
    paper: 174 s with gpt-5.5 at the recommended levels, nothing failed, no cost beyond the plan; a section takes about
    8 s against 13 s through `codex exec`.
  - **OpenRouter in one click**: OAuth with PKCE. The server makes the verifier, OpenRouter's consent page sends the
    reader back to `/oauth/openrouter` with a code, the code and verifier become a key, and the key waits in memory
    until the reader picks models and saves. Free models are listed first (the free router, then known makers, never an
    anonymous "stealth" model by default) and a new connection picks five of them. (Their limits, not shown to the
    reader: 20 a minute; 50 a day until $10 of credit has been bought, then 1,000; a paper takes about 40 calls.)
  - **The model list** of a provider shows the picked models first, and a search box narrows a long list (OpenRouter
    lists 466) as you type, keeping what is ticked. Changing the kind of a provider being edited makes a new one.
  - **Rate limits**: a 429, 502, 503 or 529 is waited out (Retry-After, else 5, 15, 30, 45 s) and asked again.
- **Thinking, per task**, set by the reader's tools and not by the reader (a reader is here to read):
  `models.DEFAULT_THINKING` gives the levels and takeaways off, the argument links low, the translation off, the
  questions low, from the model bench.
  Each caller spells a level its own way: Claude Code `--effort`, and off as `MAX_THINKING_TOKENS=0`; Codex
  `model_reasoning_effort` (off as `none`, else `low`); Pi `--thinking`; the Claude API thinking and effort by model
  (off is `between_tools` on Sonnet 5.x, `disabled` on older models, the least effort where thinking cannot be
  switched off, no thinking on Haiku); OpenAI-compatible APIs the provider's field (OpenRouter `reasoning`, GLM and
  DeepSeek and Kimi `thinking`, Qwen `enable_thinking`), then OpenAI's `reasoning_effort` (off as none, minimal, low:
  some models always think).
- **A level is a request, never a condition.** These spellings change as APIs change, so a request refused for one
  (a 400 or 422, or an answer left in the reasoning) is sent the next way, and last without any reasoning field; the
  way that worked is remembered for the run. Under every caller, a call that fails with a level set is made once more
  at the model's default, and the reply records why (`note`). Tested against a fake endpoint that refuses the fields,
  answers empty, refuses JSON mode or takes one spelling only, and live on Zhipu and OpenRouter.
- **Reasoning costs time, hardly quality, for this work** (measured on one paper, 2026-10-04): DeepSeek flash
  through Pi took 44 s without thinking and 386 s at xhigh, with the same blind grades; Sonnet 108 s against 395 s,
  +0.14 on a 5-point scale; Haiku 163 s against 1545 s. A weaker model costs more quality than switching thinking off.
  Without thinking a reply's JSON fails to parse now and then (asked for once more), and a long section's
  translation came back short: translations are made in parts of about 5,000 characters.
- **API providers**: keys from the environment, or a `.env` here or in `~/.paperfold/`: Zhipu, Qwen, OpenAI,
  Anthropic, Google, DeepSeek, Kimi, OpenRouter, Ollama. (Until v0.9 ThoughtDAG's `.env` was read too; its providers
  were copied once into the settings.) Others are added in the dialog
  from ThoughtDAG's presets (OpenRouter, Z.ai, 智谱, GLM Coding, Kimi Code, MiniMax, DeepSeek, OpenAI, Google AI Studio,
  Moonshot, Ollama, a ChatGPT bridge, Anthropic, custom): the endpoint's `/models` is fetched and you pick which to offer.
  Keys added here stay in `~/.paperfold/settings.json` (mode 600), outside the project folder. (Before the name
  PaperFold they were in `~/.dynamic-reader/`: copied from there once, and left in place.)

Command line, without the server:

```bash
python3 -m adr 2512.23916 --lang zh --lang ja   # generate English + translations, then export
python3 -m adr export 2512.23916                # one self-contained HTML file in out/<id>/
```

### Is the same paper always the same?

Only because it is stored. The model samples differently on every run, so two generations of one paper differ in
wording, chosen key sentences, topics and links (Full is the author's text and never changes). Each paper keeps
versioned layers in `papers/<id>/layers/` (`en.json`, `tr-<lang>.json`); the reader is assembled from them with no
model call, so it reads the same every time it is opened. Regenerate writes a new version; a translation built on an
older English version is marked outdated. Model replies are also cached by prompt in `papers/<id>/llm-cache/`.

In the page: pinch or ⌘/Ctrl-scroll zooms around the pointer, scrolling over the level bar or dragging it zooms too,
keys `1`–`5` jump to a level, `-`/`=` step, `L` cycles languages, clicking a paragraph below Full opens just that one,
`Esc` closes it. The zoom is continuous: it can stop half way or turn back, and it lays nothing out while it runs. When
the reader is still, the screen is laid out at each level ahead of time (in a hidden copy, one level per idle moment),
and a zoom plays those keyframes; the page takes over again at rest.

Notes: select text anywhere (a paragraph at any level, a section's summary or its title) to highlight it, write a note,
or ask the model about it (the answer, in the reading language, cites the paragraphs it rests on; a cite opens that
paragraph to its full text in place). The reader's own notes sit in the left margin, the conversations with the model
and the links in the right. Full and Brief show whole cards, Key shows them compact, and Takeaway and Topic show only a
mark, with the notes on hover. Highlights zoom with the words. `#n=<note id>` opens the reader at a note.

What the model is given for a question (`adr/notes.py`, `prompt`): the title, the abstract and a line per section
(with where the reader is); the level they read at and whose words it shows (at Key and below, a warning that the
selection is the model's wording, not the authors'); the selection and its paragraph in the authors' words (or, for a
section, its summary and each paragraph's point); up to five passages from anywhere in the paper that share the
question's telling words (IDF over the English and the reading-language text; symbols such as D=4 kept whole, CJK
matched by character pairs, question words dropped); the earlier turns; and the paragraphs it may cite. The system
prompt asks it to answer from the paper, say where, and keep general knowledge apart.

The notes button opens the list of every highlight, note and question, by section and filtered by kind: a click flies
to the passage (opening its paragraph in place where the zoom hides it) and opens the note; × deletes it after a
second click. Below the list are the exports: the paper as a PDF at the level being read (the column as it stands,
paragraphs opened in place included, every paragraph drawn at that level first, the notes under their paragraphs, the
level named on top and the PaperFold mark at the end; ⌘P prints the same), the notes alone as a PDF, Markdown for
Obsidian (block ids, callouts, links back) and the notes data (JSON, with `made_by`). The notes button is always
there, so the exports are too.

The chat (the button in the corner, in the app) asks about the whole paper. Each conversation is a note with
`on: "paper"`; the model is given the abstract, every paragraph's point section by section (at most 60,000
characters: a long paper keeps every section and fewer paragraphs each) and eight passages found for the question.
The answer cites up to five paragraphs; a cite opens its paragraph in place.

In the app the mark (in the bar and in the sidebar's rail) leads home; the rail's second button opens the list of
papers. A paper is deleted from the list after a prompt that says what goes with it: its folder (layers, model
replies, notes) moves to `papers/.trash/<id>-<time>/`, from where it can be moved back. A paper being generated
cannot be deleted. The format, the contract for every export, is `docs/notes-format.md`; the server keeps notes in
`papers/<id>/notes.json`, a static page in the browser.

Links: the author's cross-references (parsed) and argument links (one model call: supports / builds on / qualifies /
explains) show as margin notes at Full, Brief and Key; on the Topic map, hovering a chip
keeps its linked chips lit and lets the rest step back. Hovering a reference previews its target; clicking jumps there
and a Back pill returns.

## Other sources: one parser, through semantic HTML

arXiv's LaTeXML page is read by `parse.py`. Every other source is first written as plain semantic HTML (headings,
paragraphs, lists, tables, figures with captions, math, footnotes), and `semantic.normalize` rewrites that HTML in
the shape LaTeXML gives arXiv's pages: sections with titles, `ltx_p` paragraphs, figures and tables with their
captions and labels, equation tables, footnotes inside the text, a references section as a bibliography. So every
source is cut into units by the same code and drawn by the same reader; a new format is a converter to semantic HTML,
nothing more. Text before the first heading becomes an untitled first section with the id `abstract`, so it is the
context every model call is given, as an abstract is.

`normalize` is also where a document is made safe. The reader runs on the local server's origin, so a script in a
file could drive that server: only the elements and attributes a document needs are kept, links only to `#`, http(s)
and mailto, images only as files the import stored. Markdown is rendered with HTML in it shown as text.

Markdown (`markdown.py`): CommonMark with GitHub's tables and strikethrough, footnotes, definition lists, YAML front
matter (title, authors, license) and math, `$...$` and `$$...$$` by Pandoc's rules and `\(...\)`, `\[...\]` as chat
models write them; formulas become MathML with their LaTeX as `alttext`, as LaTeXML writes them. A lone image is a
figure, its caption the paragraph after it ("Figure 1: ...") or its alt text; a "Table 1: ..." paragraph next to a
table is its caption; a numbered heading ("2.1 Methods") keeps its number apart.

A document is stored by `local.py` as a paper is: `papers/md-<title words>-<hash>/` with `source.html` (normalized),
`source.md`, `meta.json` and `img/`, the images copied from beside the file, downloaded, or decoded, once. The id
carries a hash of the text, so the same file opened twice is one paper and an edited file a new one; a stored document
is never rewritten, since its layers belong to the text they were made from. `python3 -m adr notes.md` does the same
from the command line (images found beside the file); the landing sends the file's text (`POST /api/import`), so
images given by a relative path are left out there and shown by name.

JATS XML (`jats.py`), the format of PubMed Central, Europe PMC, bioRxiv and medRxiv, PLOS and eLife: sections keep
their titles (and their markup), figures and tables their labels and captions, formulas the MathML the publisher wrote
(its TeX, where given, as alttext), citations and cross-references link to their targets, the reference list becomes the
bibliography. Figures an archive keeps apart (`<floats-group>`) are placed after the paragraph that first cites them.

Europe PMC (`epmc.py`) is where papers beyond arXiv are fetched: a PMC id (an open-access article), a PPR id (a
preprint whose full text it holds: bioRxiv, medRxiv, Research Square and others), any link holding one, or a DOI, looked
up there (`no-fulltext` when it holds no open full text). One request for the XML through its public REST API; figures
from PubMed Central's CDN (the XML names each one's blob in a processing instruction) or, for a preprint, Europe PMC's
file service. Stored as `papers/pmc<n>/` or `papers/ppr<n>/`, with `source.xml`, once. A full text it does not hold
comes back as an HTTP 500, read as `no-fulltext`.

bioRxiv and medRxiv (`biorxiv.py`) are read from the servers themselves: Europe PMC holds the full text of about one
bioRxiv preprint in seventeen. A link or DOI (prefixes 10.1101 and 10.64898) is looked up in their API, which gives each
version's JATS; the newest version whose XML has a body is read (a version just posted carries the abstract alone).
Their XML draws tables and display formulas as pictures, shown as such; a formula pictured inside a line stays in it
(`pf-inline`, an atom). Figures are served under their HighWire ids (`F1.large.jpg`), other pictures from the site's
`embed/` folder. Every request to www.biorxiv.org and www.medrxiv.org waits seven seconds after the last, as their
robots.txt asks (faster, their firewall blocks the reader's address for a while), so a paper with many pictures takes a
minute or two; the job's progress counts them. Stored as `papers/biorxiv-<DOI suffix>/` or `papers/medrxiv-…/`. When a site
still turns this computer away (HTTP 403 for the XML), the preprint is read from Europe PMC if it holds the full text,
under the same id; else the job says so.

Wikipedia (`wiki.py`), any language edition: the title is resolved by the Action API (redirects followed to the article
itself) and the article's Parsoid HTML read from the MediaWiki REST API; a Chinese article is asked for in zh-cn, since
its source mixes scripts and leaves the words it must not convert empty until it is converted. Left out: infoboxes,
navigation boxes and sidebars, hatnotes, maintenance notices, inline icons, layout tables, and the sections that only
list links ("See also", "External links", "Further reading", in the larger editions' words). Links to other articles
are read as their words, so the model can rephrase and translate them; a formula keeps its MathML (its TeX without
Wikipedia's `{\displaystyle …}` as alttext), and one alone in its line is a display formula; the reference lists
become one bibliography the marks [1] point into. Stored as `papers/wiki-<language>-<page id>/` with the revision read and
the day it was read (`snapshot`, shown under the title and carried into the notes' exports: the article may have changed
since), under CC BY-SA 4.0.

The model is still told it reads a paper, and the levels are made in English first: a document in another language
is read with English levels over its own text. Making the levels in the document's language is the next step.

## No other server

A page asks no other server for anything: no font service, no CDN. The fonts (Inter, Source Serif 4, as woff2 subsets)
and KaTeX live in `web/vendor/`. The app serves them from `/static/vendor/`; a gallery copies them into its `assets/`
beside the pages; a single exported file carries the Latin faces inside, and KaTeX too when the model wrote math that
matches no formula of the paper. (Loading Google Fonts sends a visitor's IP address to Google, which a German court
found unlawful without consent in 2022.)

## Smoothness is a rule

No change may make the zoom less smooth. Measure before and after with the GPU at 2x pixels, reading the frames the
screen actually showed, on a dense paper (2512.23916):

```bash
python3 -m adr export 2512.23916
python3 tools/zoombench.py 2512.23916                 # out/compare/<id>/<version>.html pages
```

Frame intervals from requestAnimationFrame in a default headless browser hide most of what a reader feels.

## Layout

```
adr/fetch.py    arXiv HTML + metadata, figure images
adr/parse.py    LaTeXML → units (paragraph, list item, caption) as token streams; math, citations, refs stay atomic
adr/semantic.py any semantic HTML → the HTML parse.py reads; the sanitizing boundary
adr/markdown.py a Markdown file → semantic HTML (front matter, footnotes, math)
adr/local.py    documents from this computer: stored as papers (md-…), with their images
adr/jats.py     JATS XML → semantic HTML (PubMed Central, Europe PMC, bioRxiv, PLOS, eLife)
adr/epmc.py     papers from Europe PMC by PMC or PPR id, link or DOI (pmc…, ppr…)
adr/biorxiv.py  preprints from bioRxiv and medRxiv, from their own JATS (biorxiv-…, medrxiv-…)
adr/wiki.py     Wikipedia articles, any language edition (wiki-<lang>-<page id>)
adr/tokens.py   tokenizer, sentence splitter, LCS alignment
adr/ladder.py   one model call per section; validation; written words aligned to source words for the morph
adr/links.py    argument links, one call over the whole paper
adr/translate.py  any language: sentence-aligned translation + short levels, one call per section (langs.py: the 12 languages)
adr/store.py    versioned layers per paper; assembling a reader from them
adr/pipeline.py fetch → parse → English ladder + links (once) → translation, with progress
adr/server.py   local server: pages, /api/papers, /api/jobs (and /api/jobs/stop), /api/generate, /api/settings
adr/agents.py   local agents: the scan, model catalogs, one-shot runs (claude -p, codex exec, pi -p)
adr/providers.py API providers: ThoughtDAG's env registry and presets, /models probing
adr/models.py   one catalog of agent and API models; settings; resolving a model id
adr/llm.py      the call (cached) for every kind of model; llm_openai.py: OpenAI-compatible endpoints
adr/build.py    reader pages: app mode (served) and static mode (one file)
adr/notes.py    the reader's notes (docs/notes-format.md) and questions answered by the model
web/            reader.js (render + FLIP morph), app.js (sidebar, landing, settings, jobs), i18n.js, CSS, templates
tools/zoombench.py  zoom smoothness as the screen sees it (GPU, 2x, Chrome's frame trace), on out/compare/<id>/ pages
tools/readme_assets.py  the README's pictures, made from a real paper in the reader
```

Atoms (formulas, citations, cross-references, footnotes) are numbered in reading order, and the stored layers name
them by number. A parser change that reads more of a page (description lists, October 2026) renumbers every atom after
the new ones, so a paper generated before it needs its layers made again, or its atom numbers mapped from the old parse
to the new one by content and order.
