import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

// The first test of a worker can begin before the runtime has reached its browser, and what it did before then is not seen (run.json says by how much, `treeSourceUpAfterFirstTestStartedMs`): this one gives the next a browser that is up.
test("a page open while the browser comes up", async ({ page }) => {
  await page.goto("/index.html");
  await page.waitForTimeout(1500);
});

// A suite that opens contexts of its own. Playwright's `page` fixture is itself one (`browser.newContext()`), so this is every suite. The tree comes through the browser's DevTools port, which serves every context the suite opens
// (A11-229: the one tree source; an extension would not run in these contexts, which Playwright makes off the record), so this one is announced like the fixture's page.
test("a context the suite opens itself is announced like the page the fixture gives it", async ({ browser, page }) => {
  await page.goto("/signup.html");
  await page.getByLabel("Full name").focus();
  await expect(page.getByLabel("Full name")).toBeFocused();

  const context = await browser.newContext({ baseURL: "http://127.0.0.1:4173" });
  const own = await context.newPage();
  await own.goto("/basket.html");
  await own.getByRole("button", { name: "Add a mug" }).focus();
  await expect(own.getByRole("button", { name: "Add a mug" })).toBeFocused();
  await context.close();
});
