// Is the companion extension up in a browser launched the way the middleware launches it, and does it have chrome.automation? (A11-208, the macOS probe.)
//   BASELINE_CHROME=<chrome> [BASELINE_LIBS=<libs>] EXTENSION_DIR=<a prepared copy of the extension> EXTENSION_ID=<id> node probe-extension.mjs
// Prints one JSON object: the browser's version and flags, the extension targets it has, and what its service worker can see.
import { chromium } from "@playwright/test";

const { BASELINE_CHROME: executablePath, EXTENSION_DIR: dir, EXTENSION_ID: id, BASELINE_LIBS: libs } = process.env;
const browser = await chromium.launch({
  executablePath, headless: true, ignoreDefaultArgs: ["--disable-extensions"],
  args: ["--force-renderer-accessibility", `--load-extension=${dir}`, `--allowlisted-extension-id=${id}`, "--disable-features=DisableLoadExtensionCommandLineSwitch"],
  env: { ...process.env, LD_LIBRARY_PATH: [libs, process.env.LD_LIBRARY_PATH].filter(Boolean).join(":") },
});
try {
  const page = await (await browser.newContext()).newPage();
  await page.goto("data:text/html,<title>probe</title><button>x</button>");
  await new Promise((r) => setTimeout(r, 6000));
  const session = await browser.newBrowserCDPSession();
  const { targetInfos } = await session.send("Target.getTargets");
  const extension = targetInfos.filter((t) => t.url.startsWith("chrome-extension://"));
  const out = { version: browser.version(), targets: targetInfos.map((t) => `${t.type} ${t.url.slice(0, 60)}`), extensionTargets: extension.map((t) => `${t.type} ${t.url}`) };
  for (const t of extension.filter((x) => x.type === "service_worker")) {
    const { sessionId } = await session.send("Target.attachToTarget", { targetId: t.targetId, flatten: true });
    const r = await session.send("Runtime.evaluate", { expression: "JSON.stringify({automation: typeof chrome.automation, getDesktop: chrome.automation && typeof chrome.automation.getDesktop})", returnByValue: true }, sessionId).catch((e) => ({ error: String(e) }));
    out.serviceWorker = r.result?.value ?? r.error ?? r;
  }
  console.log(JSON.stringify(out, null, 1));
} finally { await browser.close(); }
