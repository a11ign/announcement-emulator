// A live Chrome 155 session for the emulator spike: serves one page, accepts JSON commands on stdin (dump, key, eval), answers on stdout.
import http from 'node:http'; import {readFileSync} from 'node:fs'; import {spawn, execSync} from 'node:child_process'; import readline from 'node:readline';
const [,, pageFile, extDir, chromeBin] = process.argv;
const R = process.env.HOME + '/spikes/announcement-emulator-5661';
const id = readFileSync(R + '/q1/ext-id.txt', 'utf8').trim();
let pending = null, want = null, wantFocus, wantAction, wantScroll;
const srv = http.createServer((req, res) => {
  if (req.url === '/page.html') { res.setHeader('content-type', 'text/html'); return res.end(readFileSync(pageFile)); }
  if (req.url.startsWith('/aria/')) {      // NVDA's include/w3c-aria-practices submodule (pinned 84b921a0), served over http because the tests' file:// iframes cannot load from this origin
    const rel = req.url.slice(6).split('?')[0]; if (rel.includes('..')) { res.statusCode = 400; return res.end(); }
    // Under file:// Chrome refuses a page's XHR to other files, which is why NVDA's real run never gets the "Open In CodePen" buttons examples.js adds only after
    // those requests succeed. Refuse fetch/XHR (Sec-Fetch-Dest: empty) the same way; documents, scripts and styles load as before.
    if (req.headers['sec-fetch-dest'] === 'empty') { res.statusCode = 404; return res.end(); }
    try { const body = readFileSync(R + '/aria-practices/' + rel); res.setHeader('content-type', rel.endsWith('.html') ? 'text/html' : rel.endsWith('.css') ? 'text/css' : rel.endsWith('.js') ? 'text/javascript' : 'application/octet-stream'); return res.end(body); }
    catch (e) { res.statusCode = 404; return res.end(); }
  }
  if (req.url === '/poll') { res.end(JSON.stringify(want ? {dump: want} : wantFocus !== undefined ? {focus: wantFocus} : wantAction !== undefined ? {action: wantAction} : wantScroll !== undefined ? {scroll: wantScroll} : {})); want = null; wantFocus = undefined; wantAction = undefined; wantScroll = undefined; return; }
  let b = ''; req.on('data', d => b += d);
  req.on('end', () => { if (req.url === '/dump' && pending) { const p = pending; pending = null; p(JSON.parse(b)); } res.end('ok'); });
}).listen(8765);
execSync('rm -rf /tmp/emu-profile');
const ch = spawn(chromeBin, ['--headless=new', '--no-sandbox', '--force-renderer-accessibility', '--window-size=1280,3000', '--user-data-dir=/tmp/emu-profile', '--no-first-run',
  '--remote-debugging-port=9333', '--allowlisted-extension-id=' + id, '--load-extension=' + extDir, '--disable-features=DisableLoadExtensionCommandLineSwitch',
  'http://127.0.0.1:8765/page.html'], {env: {...process.env, LD_LIBRARY_PATH: R + '/libs/root/usr/lib/x86_64-linux-gnu'}, stdio: ['ignore', 'ignore', 'ignore']});
process.on('exit', () => { try { ch.kill('SIGKILL'); } catch (e) {} });
process.stdin.on('end', () => process.exit(0));
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, msgId = 0; const waiters = new Map();
async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9333/json/list')).json();
      const t = list.find(t => t.url.startsWith('http://127.0.0.1:8765/page.html'));
      if (t) { ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
        ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && waiters.has(d.id)) { waiters.get(d.id)(d); waiters.delete(d.id); } }; return; }
    } catch (e) {}
    await sleep(500);
  }
  throw new Error('no page target');
}
const cdp = (method, params = {}) => new Promise(r => { const i = ++msgId; waiters.set(i, r); ws.send(JSON.stringify({id: i, method, params})); });
const KEYS = {Tab: [9, 'Tab'], Enter: [13, 'Enter'], Space: [32, 'Space'], ArrowDown: [40, 'ArrowDown'], ArrowUp: [38, 'ArrowUp'], ArrowLeft: [37, 'ArrowLeft'], ArrowRight: [39, 'ArrowRight'], Escape: [27, 'Escape'], Home: [36, 'Home'], End: [35, 'End']};
async function key(name, mods = 0) {
  const [vk, code] = KEYS[name]; const text = name === 'Enter' ? '\r' : name === 'Space' ? ' ' : undefined;
  await cdp('Input.dispatchKeyEvent', {type: text ? 'keyDown' : 'rawKeyDown', key: name === 'Space' ? ' ' : name, code, windowsVirtualKeyCode: vk, modifiers: mods, text});
  await cdp('Input.dispatchKeyEvent', {type: 'keyUp', key: name === 'Space' ? ' ' : name, code, windowsVirtualKeyCode: vk, modifiers: mods});
}
function dump(timeout = 45000) { return new Promise((ok, no) => { const t = setTimeout(() => no(new Error('dump timeout')), timeout); pending = d => { clearTimeout(t); ok(d); }; want = Date.now(); }); }
await connect();
await cdp('Page.enable'); await cdp('Runtime.enable');
console.log(JSON.stringify({ready: true}));
const rl = readline.createInterface({input: process.stdin});
for await (const line of rl) {
  let c; try { c = JSON.parse(line); } catch (e) { continue; }
  try {
    if (c.cmd === 'dump') console.log(JSON.stringify({ok: true, dump: await dump()}));
    else if (c.cmd === 'key') { await key(c.key, c.mods || 0); await sleep(c.wait || 400); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'focus') { wantFocus = c.ix; await sleep(c.wait || 700); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'action') { wantAction = c.ix; await sleep(c.wait || 700); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'scroll') { wantScroll = c.ix; await sleep(c.wait || 500); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'click') {
      for (const [type, extra] of [['mouseMoved', {}], ['mousePressed', {button: 'left', clickCount: 1}], ['mouseReleased', {button: 'left', clickCount: 1}]]) await cdp('Input.dispatchMouseEvent', {type, x: c.x, y: c.y, ...extra});
      await sleep(c.wait || 700); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'eval') { const r = await cdp('Runtime.evaluate', {expression: c.expr, returnByValue: true}); console.log(JSON.stringify({ok: true, value: r.result?.result?.value})); }
    else if (c.cmd === 'quit') break;
  } catch (e) { console.log(JSON.stringify({ok: false, error: String(e)})); }
}
ch.kill(); srv.close(); process.exit(0);
