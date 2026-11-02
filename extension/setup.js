// The page that says whether TextFold answers this extension and, when it does not, what to do (opened by
// background.js when a click finds no TextFold, once installed, and as the extension's options). Its words are the
// browser's language's (_locales).
const say = (key, subs) => chrome.i18n.getMessage(key, subs) || key;
const STEPS = { missing: ['step_download', 'step_open', 'step_again'], forbidden: ['step_update', 'step_open', 'step_again'],
                exited: ['step_open', 'step_again'], update: ['step_update', 'step_again'] };
const $ = (id) => document.getElementById(id);

document.documentElement.lang = chrome.i18n.getUILanguage();
for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = say(el.dataset.i18n);
document.title = `TextFold · ${say('setup_title')}`;

function show(why, version) {
  $('state').dataset.state = why || 'ok';
  $('title').textContent = say(`${why || 'ok'}_title`);
  $('text').textContent = why ? say(`${why}_text`) : say('ok_text', [version || '']);
  $('steps').replaceChildren(...(STEPS[why] || []).map((k) => Object.assign(document.createElement('li'), { textContent: say(k) })));
  $('download').hidden = !why;
}

async function check() {
  $('check').disabled = true;
  const r = await reach();
  show(r.why, r.textfold);
  $('check').disabled = false;
}

if (STEPS[location.hash.slice(1)]) show(location.hash.slice(1));   // (what the click found, until the check says)
$('check').addEventListener('click', check);
check();
