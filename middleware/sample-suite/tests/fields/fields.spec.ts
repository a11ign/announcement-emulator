import { test, expect } from "@playwright/test";

// A11-229, step 1: two small pages that carry every field the DevTools tree source was found to lack (results/tree-source-structure/comparison.txt): table indices and header cells, positions in a set,
// `clickable`, a field's typed value and the description words. The runtime's recordings of these tests (middleware/runtime/fixtures/structure) are what test_axtree.py holds the DevTools conversion to.
test("a page of tables is opened and tabbed through", async ({ page }) => {
  await page.goto("/fields/tables.html");
  await expect(page.getByRole("heading", { name: "Tables" })).toBeVisible();
  for (let i = 0; i < 3; i += 1) await page.keyboard.press("Tab");
  await page.waitForTimeout(500);
});

test("a page of lists and widgets is opened, tabbed through, and a field typed into", async ({ page }) => {
  await page.goto("/fields/lists.html");
  await expect(page.getByRole("heading", { name: "Lists and widgets" })).toBeVisible();
  await page.getByLabel("Your name").click();
  await page.keyboard.type("Ada");
  await expect(page.getByLabel("Your name")).toHaveValue("Ada");
  await page.waitForTimeout(500);
});

test("a page of elements with and without click handlers is opened", async ({ page }) => {
  await page.goto("/fields/clickable.html");
  await expect(page.getByRole("heading", { name: "Click handlers" })).toBeVisible();
  await page.waitForTimeout(500);
});
