# TextFold as an app

The same local server and reader in one window, with its own Python, so a reader needs nothing installed. Agents
on the computer (Claude Code, Codex, Pi, WorkBuddy), the ChatGPT bridge and API providers work as they do in the browser.
What you read is kept where `python3 -m textfold serve` keeps it, so the two share one library: on a Mac
`~/Library/Application Support/TextFold/`, on Windows `%LOCALAPPDATA%\TextFold\`. Settings and keys are in
`~/.textfold/`. `TEXTFOLD_DATA` points the app at another folder, as it does the server.

| System | File | Signed |
|---|---|---|
| macOS, Apple silicon | `TextFold-mac-arm64.dmg` | yes, and notarized |
| macOS, Intel | `TextFold-mac-x64.dmg` | yes, and notarized |
| Windows, 64-bit | `TextFold-win-x64-setup.exe` | not yet: SmartScreen asks once, More info › Run anyway |

The installers' names carry no version, so `releases/latest/download/<name>` is always the newest (the download page
links there); the `.zip` files the Macs update from do (`TextFold-<version>-mac-<arch>.zip`).

## Updates

The app asks GitHub for the newest release a few seconds after it starts and every four hours: it reads the
release's public `latest-mac.yml` or `latest.yml`, and sends nothing of the reader's. A newer version shows as a note
at the bottom right of the page, in the reader's language. Nothing downloads until they click Download (only what
changed, when the blockmap allows), and the new version installs when they click Restart, or the next time they quit.
Settings shows the version and checks by hand. A copy run from the code (`npm start`) does not update itself.
`TEXTFOLD_UPDATES=<url>` points the app at another folder of release files, for a test.

## Links

`textfold://open?paper=<document id>[&u=<paragraph id>[&to=<paragraph id>]][&s=<section id>][&eq=<equation id>][&n=<note id>[&t=<turn>]][&level=<full|brief|key|takeaway|topic>][&lang=<code>]`,
its values URL-encoded, opens a document of the library in the window, at a paragraph (or the run of them from u to
to) or a section and a level, or at a note (a conversation at one of its turns, counted from 0), in a language: another program (an editor's plugin) links to it so. A link with any part wrong is not followed;
one to a document not in the library says so, with its id, and opens the library (`links.js`; `npm test` runs its tests, and `tests/test_desktop_links.py`
keeps its ids, levels and languages the server's). Only the installed app claims the scheme: declared for macOS in
`package.json` (`build.protocols`), and claimed when it starts, which Windows needs, since its installer registers none.
A copy run from the code never claims it; a link on its command line still opens (`npm start -- "textfold://open?paper=2512.23916"`).

## Build

```bash
cd desktop
npm install
npm run pack:mac      # unsigned, out/mac-<arch>/TextFold.app: to try it
npm run dist:mac      # Apple silicon: signed and notarized .dmg and .zip (needs the signing environment below)
npm run dist:mac:x64  # Intel, on an Intel Mac or on Apple silicon (its Python runs under Rosetta)
npm run dist:win      # Windows, on Windows: the setup .exe
```

`npm run payload` (run by each) downloads a standalone CPython 3.12 for the system (python-build-standalone),
installs `requirements.txt` into it and copies `textfold/` (the reader's pages inside it) beside it, in
`desktop/payload/`. Build outside a synced folder (Dropbox, iCloud Drive), or have it skip `desktop/node_modules`,
`desktop/payload` and `desktop/out` (several hundred MB).

Before it ships, that Python runs TextFold's tests, reads a Markdown, an HTML and a CSV file without a model, and
serves the reader with them listed:

```bash
payload/python/bin/python3 scripts/smoke.py      # payload\python\python.exe scripts\smoke.py on Windows
```

## Releases

`.github/workflows/desktop.yml` builds the three on their own systems (macos-15, macos-15-intel, windows-latest) when a
version is tagged, as `publish.yml` sends the package to PyPI. They go into a draft release, published once all three
have succeeded, with the files the apps update from: `latest.yml`, and one `latest-mac.yml` for both Macs
(`scripts/latest-mac.py`, since each Mac's build writes its own). The tag, `textfold/__init__.py` and this folder's
`package.json` name the same version, or nothing is built. Run by hand (Actions › desktop › Run workflow), the files
are the run's artifacts, and a version may be given to the app alone: two such builds, an older and a newer, try an
update from one to the other.

## Signing and notarization

The Developer ID certificate and the Apple account are the ones ThoughtDAG's desktop build uses; nothing is tied
to one app. The repository's secrets:

| Secret | What |
|---|---|
| `MAC_CERT_P12_BASE64` | the Developer ID Application certificate, exported as .p12, in base64 |
| `MAC_CERT_PASSWORD` | the .p12's password |
| `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` | for notarization |

On a computer, the same names without the prefix: `CSC_LINK` (the .p12's path or its base64) and `CSC_KEY_PASSWORD`,
then the three Apple ones. The app id is `io.github.chenxiachan.textfold`. electron-builder signs every Mach-O file
in the bundle, the bundled Python and its compiled modules included, with the hardened runtime and
`build/entitlements.mac.plist`.

## Windows

The server runs with no console window of its own, and the programs it starts (agents, MinerU, npx) start without
one either (`server._quiet_children`). An agent installed by npm is a `.cmd` shim, which would pass its arguments
through cmd.exe; the script it names is run by node instead (`agents.argv`). The installer is per user, in
`%LOCALAPPDATA%\Programs\TextFold`.
