// Is the companion extension up in a browser launched the way the middleware launches it, and does it have chrome.automation? (A11-208, the macOS probe.)
//   EXTENSION_DIR=<a prepared copy of the extension> EXTENSION_ID=<id> node probe-extension.mjs      (in the Chromium the project's Playwright installed: `npx playwright install chromium`)
// Prints one JSON object: the browser's version and the targets it has, among them the extension's service worker if it is up. What that worker sees of the tree is in the run summary (`desktopChildrenWhenUp`).
import { chromium } from "@playwright/test";

const { EXTENSION_DIR: dir, EXTENSION_ID: id } = process.env;
const browser = await chromium.launch({
  channel: "chromium", headless: true, ignoreDefaultArgs: ["--disable-extensions"],
  args: ["--force-renderer-accessibility", `--load-extension=${dir}`, `--allowlisted-extension-id=${id}`, "--disable-features=DisableLoadExtensionCommandLineSwitch"],
});
try {
  const page = await (await browser.newContext()).newPage();
  await page.goto("data:text/html,<title>probe</title><button>x</button>");
  await new Promise((r) => setTimeout(r, 6000));
  const session = await browser.newBrowserCDPSession();
  const { targetInfos } = await session.send("Target.getTargets");
  const extension = targetInfos.filter((t) => t.url.startsWith("chrome-extension://"));
  const out = { version: browser.version(), targets: targetInfos.map((t) => `${t.type} ${t.url.slice(0, 60)}`), extensionTargets: extension.map((t) => `${t.type} ${t.url}`) };
  console.log(JSON.stringify(out, null, 1));
} finally { await browser.close(); }
