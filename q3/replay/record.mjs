// Load one page in the emulator's own Chrome 155 through a recording proxy, so that every request it makes is in the archive (A11-165).
//   node record.mjs <address> <proxy host:port> <ca spki hash> [meta.json]
// The browser is set up as q3/remeasure/snapshot.mjs set it up and as the emulator asks (Edge on Windows, the 1008x872 window), the page is loaded, and scrolled to its end and back (the emulator's own scroll,
// q3/sweep.py load_lazy_content) so what loads on scroll is in the archive. Nothing is rewritten: the scripts stay. The proxy writes the archive; this prints one JSON line of what the page was.
import { spawn } from "node:child_process";
import { rmSync, readFileSync, writeFileSync } from "node:fs";
const [, , address, proxy, spki, metaPath] = process.argv;
if (!address || !proxy || !spki) throw new Error("usage: node record.mjs <address> <proxy host:port> <ca spki hash> [meta.json]");
const R = process.env.EMU_DOWNLOADS || process.env.HOME + "/spikes/announcement-emulator-5661";
const PROFILE = `/tmp/record-profile-${process.pid}-${Date.now()}`;
rmSync(PROFILE, { recursive: true, force: true });
const chrome = spawn(R + "/chrome155/chrome-linux64/chrome", ["--headless=new", "--no-sandbox", "--window-size=1008,872", "--user-data-dir=" + PROFILE, "--no-first-run", "--proxy-server=" + proxy,
  "--ignore-certificate-errors-spki-list=" + spki, "--disable-background-networking", "--remote-debugging-port=0", "about:blank"],
  { env: { ...process.env, LD_LIBRARY_PATH: R + "/libs/root/usr/lib/x86_64-linux-gnu" }, stdio: "ignore" });
const done = (code) => { try { chrome.kill("SIGKILL"); } catch {} rmSync(PROFILE, { recursive: true, force: true }); process.exit(code); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const waiters = new Map();
const cdp = (method, params = {}) => new Promise((resolve) => { const i = ++id; waiters.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => (await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.result?.value;
async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const port = Number(readFileSync(PROFILE + "/DevToolsActivePort", "utf8").split("\n")[0]);
      const t = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((x) => x.type === "page");
      if (t) { ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
        ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && waiters.has(d.id)) { waiters.get(d.id)(d); waiters.delete(d.id); } }; return; }
    } catch {}
    await sleep(500);
  }
  throw new Error("no page target");
}
try {
  await connect();
  await cdp("Page.enable"); await cdp("Runtime.enable");
  await cdp("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0", platform: "Win32",
    userAgentMetadata: { brands: [{ brand: "Microsoft Edge", version: "155" }, { brand: "Chromium", version: "155" }, { brand: "Not?A_Brand", version: "99" }], fullVersion: "155.0.4283.62", platform: "Windows", platformVersion: "19.0.0", architecture: "x86", model: "", mobile: false } });
  const nav = await cdp("Page.navigate", { url: address });
  const t0 = Date.now();
  while (Date.now() - t0 < 40000) { if ((await evaluate("document.readyState")) === "complete") break; await sleep(500); }
  await sleep(2500);
  for (let i = 0; i < 120; i++) {
    const atEnd = await evaluate("window.scrollBy(0, Math.max(300, innerHeight - 100)); innerHeight + scrollY >= document.documentElement.scrollHeight - 2");
    await sleep(350); if (atEnd) break;
  }
  await sleep(2000); await evaluate("window.scrollTo(0, 0)"); await sleep(1500);
  const meta = { address, finalAddress: await evaluate("location.href"), title: await evaluate("document.title"), navigateError: nav.result?.errorText || null, readyState: await evaluate("document.readyState"), recordedAt: new Date().toISOString() };
  if (metaPath) writeFileSync(metaPath, JSON.stringify(meta, null, 1));
  console.log(JSON.stringify(meta));
  done(meta.navigateError ? 2 : 0);
} catch (e) { console.error(String(e.message || e).slice(0, 300)); done(1); }
