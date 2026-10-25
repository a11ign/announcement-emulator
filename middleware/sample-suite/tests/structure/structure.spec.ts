import { test, expect } from "@playwright/test";
import pages from "./pages.json" with { type: "json" };

// The same keyboard walk as tests/corpus/corpus.spec.ts, on the table- and list-heavy pages of the structure measurement (A11-229, results/tree-source-structure/rule.md). A test holds the two bodies equal.
// A keyboard walk of a real page, as a team's end-to-end test might do it: open it, Tab through it until focus comes round again, press Escape, and type into the first text field.
// The steps are the ones the fleet's focus probes take (screenreader-worker `probeFocusOrder`, `probeDialogEscape`, `probeTypedFeedback`, read at 5cfcc5a; the table is in
// results/agreement/rule.md), written as plain Playwright. Nothing here knows about a screen reader.
const MAX_STOPS = 150;
const CYCLE = 3;
const TYPED = "123456";
const TEXT_FIELD = 'input:not([type]), input[type="text"], input[type="search"], input[type="email"], input[type="url"], input[type="tel"], input[type="number"], textarea';

const cycled = (stops: string[]) => stops.length >= CYCLE * 2 && stops.slice(-CYCLE).every((stop, i) => stop === stops[i]);

for (const { address } of pages) {
  test(`keyboard walk of ${address}`, async ({ page }) => {
    await page.goto(address, { waitUntil: "load" });
    await page.waitForTimeout(2500);
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

    const stops: string[] = [];
    for (let i = 0; i < MAX_STOPS && !cycled(stops); i += 1) {
      await page.keyboard.press("Tab");
      stops.push(await page.evaluate(() => { const el = document.activeElement; return el && el !== document.body ? `${el.tagName}#${el.id}:${(el.textContent ?? "").trim().slice(0, 30)}` : ""; }));
    }
    expect(stops.filter(Boolean).length).toBeGreaterThan(0);

    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");

    const field = page.locator(TEXT_FIELD).filter({ visible: true }).first();
    if (await field.count()) {
      await field.click();
      await page.keyboard.type(TYPED);
      await expect(field).toHaveValue(new RegExp(TYPED));
    }
  });
}
