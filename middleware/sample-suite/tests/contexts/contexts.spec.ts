import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

// The first test of a worker begins before the browser's side of the middleware is up and is not held to what it should have heard (check-report.mjs): this one gives the next a browser that is up.
test("a page open while the browser comes up", async ({ page }) => {
  await page.goto("/index.html");
  await page.waitForTimeout(1500);
});

// A suite that opens contexts of its own. Playwright's `page` fixture is itself one (`browser.newContext()`), so this is every suite: the tree source has to serve it. An extension does not run in the contexts Playwright
// makes (they are off the record), so this is the case the DevTools source is for (A11-229).
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
