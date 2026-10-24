import { test, expect } from "@playwright/test";

// A11-234: links to the page's own address. NVDA says "same page" for a link whose address is the document's, ignoring the fragment (nvda `utils/urlUtils.py` isSamePageURL).
test("the links to this page can be tabbed through", async ({ page }) => {
  await page.goto("/misses/same-page.html");
  for (const name of ["Top", "Details", "This page", "This page, questions", "A path in the fragment", "Step two", "Another page"]) {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name, exact: true })).toBeFocused();
  }
});

// The document's address changes without a load (pushState): the links are "same page" or not by the address it has now.
test("the links of a page whose address changes under it", async ({ page }) => {
  await page.goto("/misses/same-page-route.html");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Go to step two" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/step=2/);
  for (const name of ["Step one", "Step two", "Step two, questions", "Another page"]) {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name, exact: true })).toBeFocused();
  }
});
