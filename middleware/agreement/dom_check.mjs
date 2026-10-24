// What the page-selection rule asks of a live page, read from its DOM only (no accessibility tree, no screen reader):
//   node dom_check.mjs <address> <chrome executable>        prints {"address", "tabStops", "textFields", "title"} as JSON
// Tab stops are the visible, enabled elements the keyboard can reach: links with an href, buttons, inputs that are not hidden, selects, textareas, and anything with a tabindex of 0 or more.
import { chromium } from "@playwright/test";

const [address, executablePath] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath, headless: true, args: ["--no-sandbox"] });
try {
  const page = await (await browser.newContext({ viewport: { width: 1008, height: 729 } })).newPage();
  await page.goto(address, { waitUntil: "load", timeout: 60_000 });
  await page.waitForTimeout(2500);
  const counts = await page.evaluate(() => {
    const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
    const stops = [...document.querySelectorAll('a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]')].filter((el) => !el.disabled && !(el.tabIndex < 0) && visible(el));
    const fields = [...document.querySelectorAll('input:not([type]), input[type="text"], input[type="search"], input[type="email"], input[type="url"], input[type="tel"], input[type="number"], textarea, [contenteditable="true"]')].filter((el) => !el.disabled && !el.readOnly && visible(el));
    return { tabStops: stops.length, textFields: fields.length, title: document.title };
  });
  console.log(JSON.stringify({ address, ...counts }));
} finally { await browser.close(); }
