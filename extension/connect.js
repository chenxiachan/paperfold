// How the extension reaches TextFold on this computer (background.js, setup.js): the native messaging host TextFold
// registers (textfold/capture.py), the make of the messages sent to it, and why it could not be reached.
const HOST = 'app.textfold.capture';
const PROTOCOL = 1;   // (textfold/capture.py's PROTOCOL: a TextFold that knows an older one says update-textfold)

// why TextFold could not be reached, from what the browser said (in English, whatever its language): missing (no host
// registered), forbidden (registered, but not for this extension), exited (registered, but its program did not run);
// else null
function unreachable(message) {
  const m = String(message || '');
  if (/not found/i.test(m)) return 'missing';
  if (/forbidden/i.test(m)) return 'forbidden';
  if (/exited|communicating|failed to start/i.test(m)) return 'exited';
  return null;
}

// whether TextFold answers: {why: null, textfold: its version}, or {why} (as unreachable, or update when it is older
// than this extension)
async function reach() {
  try {
    const r = await chrome.runtime.sendNativeMessage(HOST, { format: 'textfold/hello', version: PROTOCOL });
    if (!r || !r.ok) return { why: 'update' };   // (a TextFold from before the hello: not-a-snapshot)
    return { why: typeof r.protocol === 'number' && r.protocol < PROTOCOL ? 'update' : null, textfold: r.textfold };
  } catch (e) {
    return { why: unreachable(e && e.message) || 'exited' };
  }
}
