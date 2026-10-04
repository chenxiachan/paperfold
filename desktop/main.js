// PaperFold as an app: the same local server and the same reader, in one window.
//
// The packaged app carries its own Python (payload/python, from python-build-standalone) and the code (payload/app:
// adr/ and web/). It starts the server on a free port of 127.0.0.1, with the reader's papers kept in the app's data
// folder (PAPERFOLD_DATA), and points its window at it. Settings and keys stay where the server always keeps them,
// ~/.paperfold. Pages on other sites open in the system browser, where the reader is already signed in.
// Run from the repository without a payload (`npm start`), it uses the python3 on the PATH and the repository itself.
const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const net = require('net');
const path = require('path');

const PAYLOAD = app.isPackaged ? path.join(process.resourcesPath, 'payload') : path.join(__dirname, 'payload');
const PACKED = fs.existsSync(path.join(PAYLOAD, 'python', 'bin', 'python3'));
const PYTHON = PACKED ? path.join(PAYLOAD, 'python', 'bin', 'python3') : 'python3';
const CODE = PACKED ? path.join(PAYLOAD, 'app') : path.join(__dirname, '..');

let server = null;
let win = null;

app.setName('PaperFold');   // the data folder: ~/Library/Application Support/PaperFold (papers/, out/, server.log)
if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });

// a free port from a quiet base, so a server run by hand on 3017 is never in the way
function freePort(start = 31917) {
  return new Promise((resolve) => {
    const probe = net.createServer();
    probe.once('error', () => resolve(freePort(start + 1)));
    probe.once('listening', () => probe.close(() => resolve(start)));
    probe.listen(start, '127.0.0.1');
  });
}

async function waitReady(port, tries = 160) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/api/models`);
      if (r.ok) return true;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function startServer(port) {
  // A GUI app starts with a bare PATH: the usual install places are added so that the server finds node and npx
  // (the ChatGPT bridge) at once; it also asks the login shell for the agents' places (adr/agents.py).
  const extra = ['/opt/homebrew/bin', '/usr/local/bin', path.join(app.getPath('home'), '.local', 'bin')];
  const env = {
    ...process.env,
    PATH: [...extra, process.env.PATH || '/usr/bin:/bin'].join(':'),
    PAPERFOLD_DATA: app.getPath('userData'),
    PYTHONNOUSERSITE: '1',
    PYTHONDONTWRITEBYTECODE: '1',
  };
  const log = fs.createWriteStream(path.join(app.getPath('userData'), 'server.log'), { flags: 'a' });
  server = spawn(PYTHON, ['-s', '-u', '-m', 'adr', 'serve', '--port', String(port)], { cwd: CODE, env, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.pipe(log);
  server.stderr.pipe(log);
  server.on('exit', (code) => { server = null; if (code && win && !win.isDestroyed()) win.webContents.send?.('server-exit', code); });
}

async function open() {
  win = new BrowserWindow({
    width: 1360, height: 900, minWidth: 720, minHeight: 520, show: true, title: 'PaperFold',
    backgroundColor: '#FAF9F7',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: true },
  });
  win.loadFile(path.join(__dirname, 'splash.html'));
  const local = (url) => /^http:\/\/(127\.0\.0\.1|localhost):\d+\//.test(url);
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (e, url) => {
    if (local(url) || url.startsWith('file:')) return;
    e.preventDefault();
    if (/^https?:/.test(url)) shell.openExternal(url);
  });

  const port = await freePort();
  startServer(port);
  if (!(await waitReady(port))) {
    const where = path.join(app.getPath('userData'), 'server.log');
    win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`<pre style="font:14px -apple-system;padding:24px">PaperFold could not start its server.\n\nThe log is in ${where}</pre>`)}`);
    return;
  }
  win.loadURL(`http://127.0.0.1:${port}/`);
}

ipcMain.handle('open-external', (_e, url) => (/^https?:/.test(url) ? shell.openExternal(url) : null));

app.whenReady().then(open);
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { if (server) server.kill(); });
app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) open(); });
