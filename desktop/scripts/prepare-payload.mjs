// The runtime the app ships, in desktop/payload:
//   python/   a standalone CPython (python-build-standalone, the "install_only_stripped" build for Apple silicon)
//             with PaperFold's packages (requirements.txt) installed into it
//   app/      the code: adr/ and web/
// electron-builder copies it into the app's Resources and signs every Mach-O file in it with the app (hardened
// runtime, build/entitlements.mac.plist), which notarization requires. Parts of CPython the server never uses
// (tkinter and its Tcl/Tk, the test suite, IDLE) are left out: less to sign, a smaller app.
//
//   node scripts/prepare-payload.mjs            the newest CPython 3.12 build
//   PBS_URL=<tar.gz url> node scripts/...       a given build
import { execFileSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync, createWriteStream } from 'node:fs';
import path from 'node:path';
import { pipeline } from 'node:stream/promises';
import { Readable } from 'node:stream';
import { fileURLToPath } from 'node:url';

const desktop = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const root = path.dirname(desktop);
const payload = path.join(desktop, 'payload');
const TARGET = 'aarch64-apple-darwin';

async function cpythonUrl() {
  if (process.env.PBS_URL) return process.env.PBS_URL;
  const r = await fetch('https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest', {
    headers: { 'User-Agent': 'paperfold-desktop', ...(process.env.GITHUB_TOKEN ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {}) },
  });
  if (!r.ok) throw new Error(`python-build-standalone releases: HTTP ${r.status}`);
  const rel = await r.json();
  const want = new RegExp(`^cpython-3\\.12\\.\\d+\\+\\d+-${TARGET}-install_only_stripped\\.tar\\.gz$`);
  const asset = rel.assets.find((a) => want.test(a.name));
  if (!asset) throw new Error(`no CPython 3.12 ${TARGET} build in ${rel.tag_name}`);
  return asset.browser_download_url;
}

rmSync(payload, { recursive: true, force: true });
mkdirSync(payload, { recursive: true });

const url = await cpythonUrl();
console.log('CPython:', url);
const tgz = path.join(payload, 'python.tar.gz');
const res = await fetch(url);
if (!res.ok) throw new Error(`download: HTTP ${res.status}`);
await pipeline(Readable.fromWeb(res.body), createWriteStream(tgz));
execFileSync('tar', ['-xzf', tgz, '-C', payload], { stdio: 'inherit' });
rmSync(tgz);
const py = path.join(payload, 'python', 'bin', 'python3');

console.log('installing PaperFold\'s packages…');
execFileSync(py, ['-m', 'pip', 'install', '--no-cache-dir', '--disable-pip-version-check', '--no-warn-script-location',
  '-r', path.join(root, 'requirements.txt')], { stdio: 'inherit', env: { ...process.env, PYTHONNOUSERSITE: '1' } });

// what the server never uses
const lib = path.join(payload, 'python', 'lib');
const stdlib = readdirSync(lib).find((d) => /^python3\.\d+$/.test(d));
for (const p of ['test', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'lib2to3']) rmSync(path.join(lib, stdlib, p), { recursive: true, force: true });
for (const f of readdirSync(path.join(lib, stdlib, 'lib-dynload'))) if (f.startsWith('_tkinter')) rmSync(path.join(lib, stdlib, 'lib-dynload', f));
for (const d of readdirSync(lib)) if (/^(tcl|tk|itcl|thread)\d/i.test(d) || /^lib(tcl|tk)/.test(d)) rmSync(path.join(lib, d), { recursive: true, force: true });
execFileSync('find', [payload, '-name', '__pycache__', '-type', 'd', '-prune', '-exec', 'rm', '-rf', '{}', '+']);

// the code
const app = path.join(payload, 'app');
mkdirSync(app, { recursive: true });
for (const d of ['adr', 'web']) {
  cpSync(path.join(root, d), path.join(app, d), { recursive: true, filter: (src) => !src.includes('__pycache__') });
}
writeFileSync(path.join(app, 'requirements.txt'), '# installed into ../python\n');

// a quick check that the runtime imports what the server needs
execFileSync(py, ['-s', '-c', 'import bs4, lxml, PIL, adr.server; print("payload ok")'], { cwd: app, stdio: 'inherit' });
if (!existsSync(path.join(app, 'web', 'reader.js'))) throw new Error('web/ missing from the payload');
