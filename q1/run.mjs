import http from 'node:http'; import {readFileSync, writeFileSync} from 'node:fs'; import {spawn} from 'node:child_process';
const [,, mode, outFile] = process.argv; // mode: allow | noallow
const id = readFileSync('ext-id.txt','utf8').trim();
const R = process.env.EMU_DOWNLOADS || process.env.HOME + '/spikes/announcement-emulator-5661';
let want = false, got = null;
const srv = http.createServer((req, res) => {
  const u = req.url;
  if (u === '/page.html') { res.setHeader('content-type','text/html'); return res.end(readFileSync(process.env.PAGE || 'page.html')); }
  if (u === '/poll') { res.end(JSON.stringify(want ? {tabUrl: 'http://127.0.0.1:8765/page.html'} : {})); want = false; return; }
  let b=''; req.on('data', d => b += d); req.on('end', () => { got = got || {}; got[u.slice(1)] = JSON.parse(b || '{}'); console.log('POST', u, b.length); res.end('ok'); });
}).listen(8765);
const xv = {kill(){}}; import('node:child_process').then(c=>c.execSync('rm -rf /tmp/q1-profile-'+mode));
const flags = ['--headless=new','--no-sandbox','--force-renderer-accessibility','--user-data-dir=/tmp/q1-profile-' + mode,'--no-first-run','--load-extension=' + process.cwd() + '/ext',
  '--disable-features=DisableLoadExtensionCommandLineSwitch','http://127.0.0.1:8765/page.html'];
if (mode === 'allow') flags.unshift('--allowlisted-extension-id=' + id);
const ch = spawn(process.env.CHROME || (process.env.HOME + '/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'), flags,
  {env:{...process.env, DISPLAY:':77', LD_LIBRARY_PATH: R + '/libs/root/usr/lib/x86_64-linux-gnu'}, stdio:['ignore','ignore','pipe']});
let err=''; ch.stderr.on('data', d => err += d);
await new Promise(r => setTimeout(r, 6000)); want = true;
await new Promise(r => setTimeout(r, 6000));
writeFileSync(outFile, JSON.stringify({mode, got, chromeStderrTail: err.split('\n').filter(l => /extension|automation|ERROR/i.test(l)).slice(-15)}, null, 1));
ch.kill(); xv.kill(); srv.close(); process.exit(0);
