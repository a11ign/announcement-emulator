// Load one page in the emulator's own Chrome 155 through a recording proxy, so that every request it makes is in the archive (A11-165), with consent already given (A11-166).
//   node record.mjs <address> <proxy host:port> <ca spki hash> [meta.json [consent.json]]
//   node record.mjs --consent <address> <consent.json>          only the consent pass (no proxy): what the rule finds on the page, for the unit tests and for fixing the list before a run
// The browser is set up as q3/remeasure/snapshot.mjs set it up and as the emulator asks (Edge on Windows, the 1008x872 window), the page is loaded, and scrolled to its end and back (the emulator's own scroll,
// q3/sweep.py load_lazy_content) so what loads on scroll is in the archive. Nothing is rewritten: the scripts stay. The proxy writes the archive; this prints one JSON line of what the page was.
// With a consent.json path the page is first loaded once with no proxy in a browser of its own (the consent pass, consent.mjs): if the rule finds the page's "accept all" control, it is activated and the cookies the browser then
// holds are read through CDP; the page is then loaded again through the proxy WITH those cookies, and that load is the archive. consent.json is the sidecar's content (consent.py): `given` with the cookies, `no-dialog`, or `not-matched`.
import { spawn } from "node:child_process";
import { rmSync, readFileSync, writeFileSync } from "node:fs";
import { classify, nodesOf } from "./consent.mjs";
const R = process.env.EMU_DOWNLOADS || process.env.HOME + "/spikes/announcement-emulator-5661";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const USER_AGENT = { userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0", platform: "Win32",
  userAgentMetadata: { brands: [{ brand: "Microsoft Edge", version: "155" }, { brand: "Chromium", version: "155" }, { brand: "Not?A_Brand", version: "99" }], fullVersion: "155.0.4283.62", platform: "Windows", platformVersion: "19.0.0", architecture: "x86", model: "", mobile: false } };

class Browser {
  /** Chrome with its own profile, the proxy and the run's authority only when given. */
  static async launch({ proxy, spki } = {}) {
    const b = new Browser();
    b.profile = `/tmp/record-profile-${process.pid}-${Date.now()}`;
    rmSync(b.profile, { recursive: true, force: true });
    b.chrome = spawn(R + "/chrome155/chrome-linux64/chrome", ["--headless=new", "--no-sandbox", "--window-size=1008,872", "--user-data-dir=" + b.profile, "--no-first-run",
      ...(proxy ? ["--proxy-server=" + proxy, "--ignore-certificate-errors-spki-list=" + spki] : []), "--disable-background-networking", "--remote-debugging-port=0", "about:blank"],
      { env: { ...process.env, LD_LIBRARY_PATH: R + "/libs/root/usr/lib/x86_64-linux-gnu" }, stdio: "ignore" });
    b.id = 0; b.waiters = new Map();
    try {
      await b.connect();
      await b.cdp("Page.enable"); await b.cdp("Runtime.enable"); await b.cdp("Emulation.setUserAgentOverride", USER_AGENT);
    } catch (e) { b.close(); throw e; }      // a browser that never offered a page is not left running
    return b;
  }
  async connect() {
    for (let i = 0; i < 60; i++) {
      try {
        const port = Number(readFileSync(this.profile + "/DevToolsActivePort", "utf8").split("\n")[0]);
        const t = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((x) => x.type === "page");
        if (t) { this.ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((ok, no) => { this.ws.onopen = ok; this.ws.onerror = no; });
          this.ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && this.waiters.has(d.id)) { this.waiters.get(d.id)(d); this.waiters.delete(d.id); } }; return; }
      } catch {}
      await sleep(500);
    }
    throw new Error("no page target");
  }
  cdp(method, params = {}) { return new Promise((resolve) => { const i = ++this.id; this.waiters.set(i, resolve); this.ws.send(JSON.stringify({ id: i, method, params })); }); }
  async evaluate(expression) { return (await this.cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.result?.value; }
  /** Navigate and wait for the document to be complete (at most 40 s). The error text, or null. */
  async load(address) {
    const nav = await this.cdp("Page.navigate", { url: address });
    const t0 = Date.now();
    while (Date.now() - t0 < 40000) { if ((await this.evaluate("document.readyState")) === "complete") break; await sleep(500); }
    return nav.result?.errorText || null;
  }
  close() { try { this.chrome.kill("SIGKILL"); } catch {} rmSync(this.profile, { recursive: true, force: true }); }
}

/** The page's accessibility nodes, read until the rule finds a control or `attempts` readings are used (a dialog may build itself some seconds after the load). */
async function classifyPage(b, attempts = 4) {
  let verdict, nodes;
  for (let i = 0; i < attempts; i++) {
    nodes = nodesOf((await b.cdp("Accessibility.getFullAXTree")).result?.nodes ?? []);
    verdict = classify(nodes);
    if (verdict.outcome === "control") break;
    await sleep(1500);
  }
  return { verdict, nodes };
}

/** Activate a control as a person would: scrolled into view and clicked at the middle of its box; if it has no box, its own click(). */
async function activate(b, backendId) {
  await b.cdp("DOM.enable");
  await b.cdp("DOM.scrollIntoViewIfNeeded", { backendNodeId: backendId });
  const box = (await b.cdp("DOM.getBoxModel", { backendNodeId: backendId })).result?.model?.content;
  if (box) {
    const x = (box[0] + box[2] + box[4] + box[6]) / 4, y = (box[1] + box[3] + box[5] + box[7]) / 4;
    for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) await b.cdp("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: type === "mouseMoved" ? 0 : 1 });
    return "mouse";
  }
  const object = (await b.cdp("DOM.resolveNode", { backendNodeId: backendId })).result?.object;
  if (!object) throw new Error("the control is not in the page any more");
  await b.cdp("Runtime.callFunctionOn", { objectId: object.objectId, functionDeclaration: "function () { this.click(); }" });
  return "click()";
}

/** The consent pass: the sidecar's content for `address`. A page that does not load is an error, not an outcome. */
async function givenConsent(address) {
  const b = await Browser.launch();
  try {
    const error = await b.load(address);
    if (error) throw new Error(`the consent pass could not load the page: ${error}`);
    await sleep(2500);
    const { verdict, nodes } = await classifyPage(b);
    const base = { address, recordedAt: new Date().toISOString() };
    if (verdict.outcome === "none") return { ...base, outcome: "no-dialog", why: verdict.why };
    if (verdict.outcome === "dialog") return { ...base, outcome: "not-matched", why: verdict.why };
    const control = { role: verdict.control.role, name: verdict.control.name };
    const before = await b.evaluate("location.href.split('#')[0]");
    let how;
    try { how = await activate(b, verdict.control.backendId); } catch (e) { return { ...base, outcome: "not-matched", why: `${verdict.why}, which could not be activated: ${String(e.message || e).slice(0, 120)}` }; }
    await sleep(2500);
    const after = await b.evaluate("location.href.split('#')[0]");
    if (after !== before) return { ...base, outcome: "not-matched", why: `${verdict.why}; activating it left the page` };
    const gone = !classify(nodesOf((await b.cdp("Accessibility.getFullAXTree")).result?.nodes ?? [])).control;
    const cookies = (await b.cdp("Network.getAllCookies")).result?.cookies ?? [];
    return { ...base, outcome: "given", why: `${verdict.why}, activated by ${how}; the control is ${gone ? "gone" : "still there"} after it`, control: { ...control, goneAfter: gone }, cookies };
  } finally { b.close(); }
}

const cdpCookie = (c) => ({ name: c.name, value: c.value, domain: c.domain, path: c.path, secure: c.secure, httpOnly: c.httpOnly, ...(c.sameSite ? { sameSite: c.sameSite } : {}), ...(c.session || !(c.expires > 0) ? {} : { expires: c.expires }) });

const [, , first, second, third, fourth, fifth] = process.argv;
if (first === "--consent") {
  if (!second || !third) throw new Error("usage: node record.mjs --consent <address> <consent.json>");
  try { const consent = await givenConsent(second); writeFileSync(third, JSON.stringify(consent, null, 1)); console.log(JSON.stringify({ outcome: consent.outcome, why: consent.why, cookies: (consent.cookies || []).length })); process.exit(0); }
  catch (e) { console.error(String(e.message || e).slice(0, 300)); process.exit(1); }
}
const [address, proxy, spki, metaPath, consentPath] = [first, second, third, fourth, fifth];
if (!address || !proxy || !spki) throw new Error("usage: node record.mjs <address> <proxy host:port> <ca spki hash> [meta.json [consent.json]]");
let b;
try {
  const consent = consentPath ? await givenConsent(address) : null;
  if (consentPath) writeFileSync(consentPath, JSON.stringify(consent, null, 1));
  b = await Browser.launch({ proxy, spki });
  if (consent?.outcome === "given" && consent.cookies.length) {
    const set = await b.cdp("Network.setCookies", { cookies: consent.cookies.map(cdpCookie) });
    if (set.error) throw new Error(`the recording browser refused the consent cookies: ${JSON.stringify(set.error).slice(0, 160)}`);      // a page recorded without them would be filed as `given`
  }
  const navigateError = await b.load(address);
  await sleep(2500);
  for (let i = 0; i < 120; i++) {
    const atEnd = await b.evaluate("window.scrollBy(0, Math.max(300, innerHeight - 100)); innerHeight + scrollY >= document.documentElement.scrollHeight - 2");
    await sleep(350); if (atEnd) break;
  }
  await sleep(2000); await b.evaluate("window.scrollTo(0, 0)"); await sleep(1500);
  const meta = { address, finalAddress: await b.evaluate("location.href"), title: await b.evaluate("document.title"), navigateError, readyState: await b.evaluate("document.readyState"), recordedAt: new Date().toISOString(),
    ...(consent ? { consent: consent.outcome } : {}) };
  if (metaPath) writeFileSync(metaPath, JSON.stringify(meta, null, 1));
  console.log(JSON.stringify(meta));
  b.close(); process.exit(meta.navigateError ? 2 : 0);
} catch (e) { console.error(String(e.message || e).slice(0, 300)); if (b) b.close(); process.exit(1); }
