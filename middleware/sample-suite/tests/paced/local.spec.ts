import { test, expect } from "@playwright/test";

// The two small local pages of the sample suite walked at the pace of a test that waits for the page (A11-229, step 2): a form filled in key by key, and a live region that changes while the focus is on its button.
// There is no network in it, so the middleware's incremental reads of the tree can be recorded from it (middleware/runtime/fixtures/incremental) and run in CI.
const PAUSE_MS = 300;

test("a form is filled in key by key", async ({ page }) => {
  await page.goto("/signup.html");
  await page.waitForTimeout(PAUSE_MS);
  for (const [key, text] of [["Tab", ""], ["Tab", ""], ["Tab", "Ada"], ["Tab", ""], ["Tab", "ada@example.com"], ["Tab", ""]] as const) {
    await page.keyboard.press(key);
    await page.waitForTimeout(PAUSE_MS);
    if (text) await page.keyboard.type(text, { delay: 100 });
  }
  await page.keyboard.press("Shift+Tab");
  await page.waitForTimeout(PAUSE_MS);
  await page.keyboard.press("Space");
  await page.waitForTimeout(PAUSE_MS);
  await expect(page.getByLabel("Send me news")).toBeChecked();
});

test("a basket counts while the focus stays on its button", async ({ page }) => {
  await page.goto("/basket.html");
  await page.waitForTimeout(PAUSE_MS);
  await page.keyboard.press("Tab");
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("Enter");
    await page.waitForTimeout(PAUSE_MS);
  }
  await expect(page.getByRole("status")).toHaveText("3 items in your basket");
});
