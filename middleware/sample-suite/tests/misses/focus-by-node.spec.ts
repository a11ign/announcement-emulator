import { test, expect } from "@playwright/test";

// A11-234: links whose accessible name is longer than their text: a visually hidden span written with no space before it (as Companies House writes it), and text that CSS generates (as GOV.UK's
// external links do). The page's own listener can only guess a name from the element's attributes and text, so the runtime has to find the link in the tree by the DOM node the browser says has the focus.
test("the links that open a new window can be tabbed through", async ({ page }) => {
  await page.goto("/misses/new-window-links.html");
  for (const name of [/Read the guidance on accuracy/, /Advanced search/, /Tell us what you think/, /^Home$/]) {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name })).toBeFocused();
  }
  await page.waitForTimeout(300);      // a test goes on to do something after its last stop; a page closed in the same millisecond is not read
});
