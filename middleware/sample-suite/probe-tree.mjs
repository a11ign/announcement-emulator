// Does this platform's Chrome give the companion extension a tab's own tree, when it gives it no desktop tree? (A11-208, the macOS probe: chrome.automation.getTree(tabId) beside getDesktop.)
//   BASELINE_CHROME=<chrome> [BASELINE_LIBS=<libs>] EXTENSION_SRC=<a copy of emu/ext2> EXTENSION_ID=<id> [PROBE_DESKTOP=0] node probe-tree.mjs
// PROBE_DESKTOP=0 asks the manifest for the tab's trees only (no "desktop": true).
// Prints one JSON object: what the extension's worker posted (hello, desktop, tab, tree, after), the page's own view of the focus, and the browser's version.
import { chromium } from "@playwright/test";
import { createServer } from "node:http";
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const { BASELINE_CHROME: executablePath, EXTENSION_SRC: source, EXTENSION_ID: id, BASELINE_LIBS: libs } = process.env;
const posts = {};
const waiters = new Map();
const server = createServer((req, res) => {
  let body = ""; req.on("data", (c) => (body += c));
  req.on("end", () => { const kind = req.url.slice(1); try { posts[kind] = JSON.parse(body); } catch { posts[kind] = body; } waiters.get(kind)?.(); res.setHeader("access-control-allow-origin", "*"); res.end("ok"); });
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;
const seen = (kind, ms) => new Promise((resolve) => { if (kind in posts) return resolve(true); const t = setTimeout(() => resolve(false), ms); waiters.set(kind, () => { clearTimeout(t); resolve(true); }); });

const dir = mkdtempSync(join(tmpdir(), "probe-tree-"));
cpSync(source, dir, { recursive: true });
const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
manifest.background.service_worker = "probe-sw.js";
const desktop = process.env.PROBE_DESKTOP !== "0";
if (!desktop) delete manifest.automation.desktop;
writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
writeFileSync(join(dir, "probe-sw.js"), readFileSync(new URL("./probe-tree-sw.js", import.meta.url), "utf8").replace("__PORT__", String(port)).replace("__DESKTOP__", desktop ? "1" : "0"));

const browser = await chromium.launch({
  executablePath, headless: true, ignoreDefaultArgs: ["--disable-extensions"],
  args: ["--force-renderer-accessibility", `--load-extension=${dir}`, `--allowlisted-extension-id=${id}`, "--disable-features=DisableLoadExtensionCommandLineSwitch"],
  env: { ...process.env, LD_LIBRARY_PATH: [libs, process.env.LD_LIBRARY_PATH].filter(Boolean).join(":") },
});
const out = { version: browser.version() };
try {
  const page = await (await browser.newContext()).newPage();
  await page.goto("data:text/html,<title>probe</title><button>Save</button><input aria-label=Name>");
  const gotTree = await seen("tree", 20000);
  if (gotTree) {
    await page.focus("button");
    await page.focus("input");
    await page.keyboard.type("ab");
    await seen("after", 10000);
  }
  out.activeElement = await page.evaluate(() => document.activeElement?.tagName);
} finally { await browser.close(); server.close(); }
out.posts = posts;
console.log(JSON.stringify(out, null, 1));
