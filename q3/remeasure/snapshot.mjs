// A static copy of a live page, so that the fleet and the emulator can both read the same bytes (A11-155, the drift-free comparison).
//   node snapshot.mjs <address> <out_dir>
// Writes <out_dir>/index.html and <out_dir>/meta.json. The browser is the emulator's own Chrome 155, asked as the emulator asks (Edge on Windows, the 1008x872 window), the page is loaded,
// scrolled to its end and back so what loads on scroll is there, and its DOM is written out with:
//   - every script, <noscript>, preload hint, <base>, meta refresh and inline event handler removed (the copy does nothing by itself);
//   - every stylesheet inlined (the browser's own text of it, so a rule a script inserted is in), its url()s made absolute;
//   - every URL made absolute, except a link to a place on the page itself (`#x`), and a link to the page's own address, which points at the copy (`index.html`), so "same page" stays "same page";
//   - an iframe of the same origin written into its own `srcdoc` by the same steps; any other iframe keeps its address;
//   - form values written into attributes.
// What it does not freeze: images, fonts and the content of other-origin iframes are still fetched live; shadow DOM is not serialised (no `getHTML`).
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync, readFileSync } from "node:fs";
const [, , address, outDir, ...rest] = process.argv;
if (!address || !outDir) throw new Error("usage: node snapshot.mjs <address> <out_dir>");
const TAG = `${process.pid}-${Date.now()}`;      // one profile per run; the browser picks its own debugging port, so runs side by side cannot meet in one browser
const R = process.env.EMU_DOWNLOADS || process.env.HOME + "/spikes/announcement-emulator-5661";
const PROFILE = `/tmp/snap-profile-${TAG}`;
rmSync(PROFILE, { recursive: true, force: true });
const chrome = spawn(R + "/chrome155/chrome-linux64/chrome", ["--headless=new", "--no-sandbox", "--window-size=1008,872", "--user-data-dir=" + PROFILE, "--no-first-run",
  "--remote-debugging-port=0", "about:blank"], { env: { ...process.env, LD_LIBRARY_PATH: R + "/libs/root/usr/lib/x86_64-linux-gnu" }, stdio: "ignore" });
const done = (code) => { try { chrome.kill("SIGKILL"); } catch {} rmSync(PROFILE, { recursive: true, force: true }); process.exit(code); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const waiters = new Map(), listeners = [];
const cdp = (method, params = {}) => new Promise((resolve) => { const i = ++id; waiters.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => { const r = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400)); return r.result?.result?.value; };

async function connect() {
  let PORT;
  for (let i = 0; i < 60; i++) {
    try {
      PORT = Number(readFileSync(PROFILE + "/DevToolsActivePort", "utf8").split("\n")[0]);
      const t = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((x) => x.type === "page");
      if (t) { ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
        ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && waiters.has(d.id)) { waiters.get(d.id)(d); waiters.delete(d.id); } else listeners.forEach((l) => l(d)); }; return; }
    } catch {}
    await sleep(500);
  }
  throw new Error("no page target");
}

// Runs in the page. `sheets` maps a stylesheet's address to its text; `self` is the page's address; returns the serialised document.
const SERIALISE = `(function (sheets, self) {
  const URL_ATTRS = { a: ['href'], area: ['href'], link: ['href'], img: ['src'], source: ['src'], video: ['src', 'poster'], audio: ['src'], track: ['src'], iframe: ['src'], embed: ['src'], object: ['data'], form: ['action'], input: ['src'] };
  const noFragment = (u) => u.split('#')[0];
  const abs = (v, base) => { try { return new URL(v, base).href; } catch { return v; } };
  const absSrcset = (v, base) => v.split(',').map((c) => { const p = c.trim().split(/\\s+/); p[0] = abs(p[0], base); return p.join(' '); }).join(', ');
  function serialise(doc) {
    const base = doc.baseURI; [...doc.documentElement.querySelectorAll('*')].forEach((e, i) => e.setAttribute('data-snap', String(i)));
    const clone = doc.documentElement.cloneNode(true);
    const origStyles = [...doc.documentElement.querySelectorAll('style')], cloneStyles = [...clone.querySelectorAll('style')];
    origStyles.forEach((s, i) => { try { cloneStyles[i].textContent = [...s.sheet.cssRules].map((r) => r.cssText).join('\\n'); } catch {} });
    clone.querySelectorAll('script, noscript, base, template').forEach((e) => e.remove());
    clone.querySelectorAll('link[rel~=preload], link[rel~=prefetch], link[rel~=modulepreload], link[rel~=dns-prefetch], link[rel~=preconnect]').forEach((e) => e.remove());
    clone.querySelectorAll('meta[http-equiv]').forEach((e) => { if (/refresh/i.test(e.getAttribute('http-equiv'))) e.remove(); });
    for (const link of [...clone.querySelectorAll('link[rel~=stylesheet]')]) {
      const href = abs(link.getAttribute('href') || '', base), text = sheets[href];
      if (text == null) continue;
      const style = doc.createElement('style'); if (link.media) style.media = link.media; style.textContent = text; link.replaceWith(style);
    }
    if (doc.adoptedStyleSheets && doc.adoptedStyleSheets.length) {
      const style = doc.createElement('style'); style.textContent = doc.adoptedStyleSheets.map((s) => [...s.cssRules].map((r) => r.cssText).join('\\n')).join('\\n'); clone.querySelector('head')?.append(style);
    }
    const byId = new Map([...clone.querySelectorAll('[data-snap]')].map((e) => [e.getAttribute('data-snap'), e]));
    const pairs = [...doc.documentElement.querySelectorAll('[data-snap]')].map((o) => [o, byId.get(o.getAttribute('data-snap'))]).filter(([, c]) => c);
    for (const [o, c] of pairs) {
      c.removeAttribute('data-snap');
      for (const a of [...c.attributes]) if (/^on/i.test(a.name)) c.removeAttribute(a.name);
      const t = c.localName;
      for (const attr of URL_ATTRS[t] || []) {
        const v = c.getAttribute(attr); if (v == null || v === '' || v.startsWith('#') || /^(javascript|mailto|tel|data|blob|about):/i.test(v)) continue;
        let u = abs(v, base);
        if (t === 'a' && noFragment(u) === noFragment(self)) u = '@@SELF@@' + (u.includes('#') ? '#' + u.split('#').slice(1).join('#') : '');
        c.setAttribute(attr, u);
      }
      for (const attr of ['srcset', 'imagesrcset']) if (c.hasAttribute(attr)) c.setAttribute(attr, absSrcset(c.getAttribute(attr), base));
      if (t === 'input') { if (o.type === 'checkbox' || o.type === 'radio') { if (o.checked) c.setAttribute('checked', ''); else c.removeAttribute('checked'); } else if (o.type !== 'password' && o.type !== 'file') c.setAttribute('value', o.value); }
      if (t === 'textarea') c.textContent = o.value;
      if (t === 'option') { if (o.selected) c.setAttribute('selected', ''); else c.removeAttribute('selected'); }
      if (t === 'iframe') {
        let inner = null; try { inner = o.contentDocument; } catch {}
        if (inner && inner.documentElement) { c.removeAttribute('src'); c.setAttribute('srcdoc', serialise(inner)); }
      }
    }
    if (!clone.querySelector('meta[charset]')) { const m = doc.createElement('meta'); m.setAttribute('charset', 'utf-8'); clone.querySelector('head')?.prepend(m); }
    return '<!DOCTYPE html>\\n' + clone.outerHTML;
  }
  return JSON.stringify({ html: serialise(document), title: document.title, href: location.href, elements: document.querySelectorAll('*').length, iframes: document.querySelectorAll('iframe').length });
})`;

function cssAbsolute(text, sheetUrl) {
  const abs = (v) => { try { return new URL(v, sheetUrl).href; } catch { return v; } };
  return text
    .replace(/url\(\s*(['"]?)([^)'"]+)\1\s*\)/g, (m, q, v) => (/^(data:|#)/i.test(v.trim()) ? m : `url("${abs(v.trim())}")`))
    .replace(/@import\s+(['"])([^'"]+)\1/g, (m, q, v) => `@import "${abs(v)}"`);
}

try {
  await connect();
  const headers = new Map();
  listeners.push((d) => { if (d.method === "CSS.styleSheetAdded") headers.set(d.params.header.styleSheetId, d.params.header); });
  await cdp("Page.enable"); await cdp("Runtime.enable"); await cdp("DOM.enable"); await cdp("CSS.enable");
  await cdp("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0", platform: "Win32",
    userAgentMetadata: { brands: [{ brand: "Microsoft Edge", version: "155" }, { brand: "Chromium", version: "155" }, { brand: "Not?A_Brand", version: "99" }], fullVersion: "155.0.4283.62", platform: "Windows", platformVersion: "19.0.0", architecture: "x86", model: "", mobile: false } });
  await cdp("Page.navigate", { url: address });
  const t0 = Date.now();
  while (Date.now() - t0 < 40000) { if ((await evaluate("document.readyState")) === "complete") break; await sleep(500); }
  await sleep(2500);
  for (let i = 0; i < 120; i++) {      // the emulator's own scroll (q3/sweep.py load_lazy_content)
    const atEnd = await evaluate("window.scrollBy(0, Math.max(300, innerHeight - 100)); innerHeight + scrollY >= document.documentElement.scrollHeight - 2");
    await sleep(350); if (atEnd) break;
  }
  await sleep(2000); await evaluate("window.scrollTo(0, 0)"); await sleep(500);
  const sheets = {};
  for (const h of headers.values()) {
    if (h.isInline || !h.sourceURL || !/^https?:/.test(h.sourceURL)) continue;
    const r = await cdp("CSS.getStyleSheetText", { styleSheetId: h.styleSheetId });
    if (r.result?.text != null) sheets[h.sourceURL] = cssAbsolute(r.result.text, h.sourceURL);
  }
  const out = JSON.parse(await evaluate(`${SERIALISE}(${JSON.stringify(sheets)}, ${JSON.stringify(address.split("#")[0])})`));
  mkdirSync(outDir, { recursive: true });
  writeFileSync(outDir + "/index.html", out.html.replaceAll("@@SELF@@", "index.html"));      // the copy is served as <slug>/index.html: a link to the page itself stays a link to this document, on whatever host serves it
  writeFileSync(outDir + "/meta.json", JSON.stringify({ address, finalAddress: out.href, title: out.title, bytes: Buffer.byteLength(out.html), elements: out.elements, iframes: out.iframes,
    stylesheetsInlined: Object.keys(sheets).length, snapshotAt: new Date().toISOString() }, null, 1));
  console.log(`${out.title.slice(0, 60)} | ${out.elements} elements, ${Buffer.byteLength(out.html)} bytes, ${Object.keys(sheets).length} sheets`);
  done(0);
} catch (e) { console.error(String(e.message || e).slice(0, 300)); done(1); }
