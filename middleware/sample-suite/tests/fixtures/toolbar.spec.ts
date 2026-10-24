import { test, expect } from "@playwright/test";

test("the toolbar buttons can be reached by keyboard", async ({ page }) => {
  await page.goto("/unnamed-control.html");
  await page.keyboard.press("Tab");
  await expect(page.locator("#save")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#icon")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#labelled")).toBeFocused();
});
