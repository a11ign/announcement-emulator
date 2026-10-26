import { test, expect } from "@playwright/test";
import pages from "../structure/pages.json" with { type: "json" };

// A keyboard walk at the pace of a test that waits for the page: Tab, wait, Tab, as one that asserts after each key would. The structure project's walk presses Tab as fast as Playwright can, so the middleware reads the page
// a few times for a hundred keys; here it is told of a change between nearly every key, which is what the cost of reading the tree (A11-229, results/devtools-source/cost) is measured by. The pages are the structure project's.
const STOPS = 40;
const PAUSE_MS = 300;
const TYPED = "123456";
const TEXT_FIELD = 'input:not([type]), input[type="text"], input[type="search"], input[type="email"], input[type="url"], input[type="tel"], input[type="number"], textarea';

for (const { address } of pages) {
  test(`paced walk of ${address}`, async ({ page }) => {
    await page.goto(address, { waitUntil: "load" });
    await page.waitForTimeout(2500);
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

    let stops = 0;
    for (let i = 0; i < STOPS; i += 1) {
      await page.keyboard.press("Tab");
      await page.waitForTimeout(PAUSE_MS);
      if (await page.evaluate(() => document.activeElement !== document.body)) stops += 1;
    }
    expect(stops).toBeGreaterThan(0);

    const field = page.locator(TEXT_FIELD).filter({ visible: true }).first();
    if (await field.count()) {
      await field.click();
      await page.keyboard.type(TYPED, { delay: PAUSE_MS });
    }
  });
}
