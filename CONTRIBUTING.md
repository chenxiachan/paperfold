# Contributing to PaperFold

Thank you for helping. PaperFold is small on purpose: a Python server with no framework, and a reader in plain JavaScript. How it works, and where everything lives, is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## One rule above the others

No change may make the zoom less smooth. If you touch the reader, measure before and after, as [Smoothness is a rule](docs/DEVELOPMENT.md#smoothness-is-a-rule) describes, and put both numbers in your pull request.

## Set up

```bash
git clone https://github.com/chenxiachan/paperfold.git
cd paperfold
python3 -m pip install -r requirements.txt
python3 -m adr serve
```

Then open `http://localhost:3017` and connect a model (the README says how).

## Good places to start

- **A paper that reads wrong.** Open an issue with its arXiv ID, the level and language, and the paragraph (a screenshot is fine). Most fixes go in `adr/parse.py`, which turns arXiv's HTML into paragraphs, formulas and citations.
- **A language.** Reading languages are listed in `adr/langs.py`; the interface's words are in `web/i18n.js`, in twelve languages.
- **A model provider.** Presets and model lists are in `adr/providers.py` and `adr/models.py`.

## Pull requests

- One change per pull request: what it changes, why, and how you checked it.
- Match the code around it: plain names, and comments that say why rather than what.
- Keep keys and papers out of commits. Settings and keys live in `~/.paperfold/`; papers and their levels in `papers/`, which git ignores.

By contributing, you agree that your work is released under the [Apache License 2.0](LICENSE).
