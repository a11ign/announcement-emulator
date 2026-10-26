// A live Chrome 155 session for the emulator spike: serves one page, accepts JSON commands on stdin (dump, key, eval), answers on stdout.
import {fileURLToPath} from 'node:url'; import http from 'node:http'; import {readFileSync, mkdirSync, writeFileSync, cpSync, rmSync} from 'node:fs'; import {spawn} from 'node:child_process'; import readline from 'node:readline'; import {tmpdir} from 'node:os'; import {join} from 'node:path';
const [,, pageFile, extDir0, chromeBin] = process.argv;
// A live URL instead of a served file: pageFile is 'url:<address>'. Ports are per session so several can run side by side (EMU_PORT, EMU_CDP).
const PORT = Number(process.env.EMU_PORT || 8765), CDP = Number(process.env.EMU_CDP || 9333);
const LIVE = pageFile.startsWith('url:'), LIVE_URL = LIVE ? pageFile.slice(4) : null;
// headless=new puts 143 px of browser UI inside the window: 1008x872 gives a page the 1008x729 the fleet's Edge reports (environment.innerWidth/innerHeight)
const [VW, VH] = (process.env.EMU_VIEWPORT || (LIVE ? '1008x872' : '1280x3000')).split('x').map(Number);
const UA = process.env.EMU_UA || null; let target = LIVE ? '' : 'http://127.0.0.1:' + PORT + '/page.html';
const R = process.env.EMU_DOWNLOADS || process.env.HOME + '/spikes/announcement-emulator-5661';
const CODE = fileURLToPath(new URL('..', import.meta.url));
const id = readFileSync(CODE + 'q1/ext-id.txt', 'utf8').trim();
let pending = null, want = null, wantFocus, wantAction, wantScroll, wantHistory;
const srv = http.createServer((req, res) => {
  if (req.url === '/page.html' && !LIVE) { res.setHeader('content-type', 'text/html'); return res.end(readFileSync(pageFile)); }
  if (req.url.startsWith('/aria/')) {      // NVDA's include/w3c-aria-practices submodule (pinned 84b921a0), served over http because the tests' file:// iframes cannot load from this origin
    const rel = req.url.slice(6).split('?')[0]; if (rel.includes('..')) { res.statusCode = 400; return res.end(); }
    // Under file:// Chrome refuses a page's XHR to other files, which is why NVDA's real run never gets the "Open In CodePen" buttons examples.js adds only after
    // those requests succeed. Refuse fetch/XHR (Sec-Fetch-Dest: empty) the same way; documents, scripts and styles load as before.
    if (req.headers['sec-fetch-dest'] === 'empty') { res.statusCode = 404; return res.end(); }
    try { const body = readFileSync(R + '/aria-practices/' + rel); res.setHeader('content-type', rel.endsWith('.html') ? 'text/html' : rel.endsWith('.css') ? 'text/css' : rel.endsWith('.js') ? 'text/javascript' : 'application/octet-stream'); return res.end(body); }
    catch (e) { res.statusCode = 404; return res.end(); }
  }
  if (req.url === '/poll') { res.end(JSON.stringify({target, ...(wantHistory ? {history: wantHistory} : {}), ...(want ? {dump: want} : wantFocus !== undefined ? {focus: wantFocus} : wantAction !== undefined ? {action: wantAction} : wantScroll !== undefined ? {scroll: wantScroll} : {})})); want = null; wantHistory = undefined; wantFocus = undefined; wantAction = undefined; wantScroll = undefined; return; }
  let b = ''; req.on('data', d => b += d);
  req.on('end', () => { if (req.url === '/dump' && pending) { const p = pending; pending = null; p(JSON.parse(b)); } res.end('ok'); });
}).listen(PORT);
// A second session on a port in use fails to listen: it must not remove the first one's profile and extension copy (the error is rethrown, as an unhandled 'error' event is).
let ownsPort = true; srv.once('error', e => { ownsPort = false; throw e; });
// A11-279: the profile and the extension copy live under tmpdir() (so a run's private TMPDIR holds them, not /tmp) and are removed when the session ends: they were left behind by every session.
const PROFILE = join(tmpdir(), 'emu-profile-' + PORT); rmSync(PROFILE, {recursive: true, force: true});
// the companion extension, with this session's collector port written into a private copy
const extDir = PROFILE + '-ext'; rmSync(extDir, {recursive: true, force: true}); mkdirSync(extDir, {recursive: true}); cpSync(extDir0, extDir, {recursive: true});
writeFileSync(extDir + '/bg.js', readFileSync(extDir0 + '/bg.js', 'utf8').replaceAll('__PORT__', String(PORT)));
// A11-279: removed when the session ends, and also when the launch below is refused.
process.on('exit', () => { if (ownsPort) for (const dir of [PROFILE, extDir]) { try { rmSync(dir, {recursive: true, force: true, maxRetries: 3}); } catch (e) {} } });
// A replay (A11-165): the page is read through a proxy that answers every request from a recording, and the run's certificate authority is trusted by its SPKI hash. With EMU_PROXY unset the launch is as it was.
if (process.env.EMU_PROXY && !process.env.EMU_PROXY_SPKI) throw new Error('EMU_PROXY needs EMU_PROXY_SPKI, the hash of the certificate authority the proxy signs with');
const REPLAY = process.env.EMU_PROXY ? ['--proxy-server=' + process.env.EMU_PROXY, '--ignore-certificate-errors-spki-list=' + process.env.EMU_PROXY_SPKI, '--disable-background-networking'] : [];
const ch = spawn(chromeBin, ['--headless=new', '--no-sandbox', '--force-renderer-accessibility', `--window-size=${VW},${VH}`, '--user-data-dir=' + PROFILE, '--no-first-run', ...REPLAY,
  '--remote-debugging-port=' + CDP, '--allowlisted-extension-id=' + id, '--load-extension=' + extDir, '--disable-features=DisableLoadExtensionCommandLineSwitch',
  LIVE ? LIVE_URL : 'http://127.0.0.1:' + PORT + '/page.html'], {env: {...process.env, LD_LIBRARY_PATH: R + '/libs/root/usr/lib/x86_64-linux-gnu'}, stdio: ['ignore', 'ignore', 'ignore']});
process.on('exit', () => { try { ch.kill('SIGKILL'); } catch (e) {} });
process.stdin.on('end', () => process.exit(0));
for (const [signal, code] of [['SIGINT', 130], ['SIGTERM', 143]]) process.on(signal, () => process.exit(code));
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, msgId = 0; const waiters = new Map();
async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:' + CDP + '/json/list')).json();
      const t = list.find(t => t.type === 'page' && (LIVE ? t.url.startsWith('http') : t.url.startsWith('http://127.0.0.1:' + PORT + '/page.html')));
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
if (LIVE) {      // the fleet's browser is Microsoft Edge on Windows: say so to the sites we ask (the tree is Chrome's either way)
  const ver = '155.0.4283.62';
  await cdp('Emulation.setUserAgentOverride', {userAgent: UA || `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0`, platform: 'Win32',
    userAgentMetadata: {brands: [{brand: 'Microsoft Edge', version: '155'}, {brand: 'Chromium', version: '155'}, {brand: 'Not?A_Brand', version: '99'}], fullVersion: ver, platform: 'Windows', platformVersion: '19.0.0', architecture: 'x86', model: '', mobile: false}});
}
console.log(JSON.stringify({ready: true}));
const rl = readline.createInterface({input: process.stdin});
for await (const line of rl) {
  let c; try { c = JSON.parse(line); } catch (e) { continue; }
  try {
    if (c.cmd === 'dump') console.log(JSON.stringify({ok: true, dump: await dump()}));
    else if (c.cmd === 'key') { await key(c.key, c.mods || 0); await sleep(c.wait || 400); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'navigate') {      // the page was opened by the command line (so the browser puts focus in it, as it does on the fleet); wait for it to load
      let ready = false; const t0 = Date.now();
      while (Date.now() - t0 < (c.timeout || 40000)) { const r = await cdp('Runtime.evaluate', {expression: 'document.readyState', returnByValue: true}); if (r.result?.result?.value === 'complete') { ready = true; break; } await sleep(250); }
      await sleep(c.settle || 2500);
      const href = (await cdp('Runtime.evaluate', {expression: 'location.href', returnByValue: true})).result?.result?.value || c.url;
      target = href.split('#')[0]; console.log(JSON.stringify({ok: true, loaded: ready, href}));
    }
    else if (c.cmd === 'history') { wantHistory = c.urls; await sleep(1500); console.log(JSON.stringify({ok: true})); }
    else if (c.cmd === 'reload') {
      await cdp('Page.reload', {}); await sleep(1000);
      let ready = false; const t0 = Date.now();
      while (Date.now() - t0 < 40000) { const r = await cdp('Runtime.evaluate', {expression: 'document.readyState', returnByValue: true}); if (r.result?.result?.value === 'complete') { ready = true; break; } await sleep(250); }
      await sleep(c.settle || 2500); console.log(JSON.stringify({ok: true, loaded: ready}));
    }
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
