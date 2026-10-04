# PaperFold as an app

The same local server and reader in one window, with its own Python, so a reader needs nothing installed. Agents
on the computer (Claude Code, Codex, Pi), the ChatGPT bridge and API providers work as they do in the browser.
Papers are kept in `~/Library/Application Support/PaperFold/`; settings and keys in `~/.paperfold/`, shared with
`python3 -m adr serve`.

## Build

```bash
cd desktop
npm install
npm run pack:mac      # unsigned, out/mac-arm64/PaperFold.app: to try it
npm run dist:mac      # signed and notarized .dmg and .zip (needs the signing environment below)
```

`npm run payload` (run by both) downloads a standalone CPython 3.12 (python-build-standalone), installs
`requirements.txt` into it and copies `adr/` and `web/` beside it, in `desktop/payload/`. Build outside a synced
folder (Dropbox, iCloud Drive), or have it skip `desktop/node_modules`, `desktop/payload` and `desktop/out` (several
hundred MB).

## Signing and notarization

The Developer ID certificate and the Apple account are the ones ThoughtDAG's desktop build uses; nothing is tied
to one app. In CI (`.github/workflows/desktop.yml`, on a `v*` tag or by hand), add these repository secrets, the
same values as ThoughtDAG's:

| Secret | What |
|---|---|
| `MAC_CERT_P12_BASE64` | the Developer ID Application certificate, exported as .p12, in base64 |
| `MAC_CERT_PASSWORD` | the .p12's password |
| `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` | for notarization |

The app id is `io.github.chenxiachan.paperfold`. electron-builder signs every Mach-O file in the bundle, the
bundled Python and its compiled modules included, with the hardened runtime and `build/entitlements.mac.plist`.
