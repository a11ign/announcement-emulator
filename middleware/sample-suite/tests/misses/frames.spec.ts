import { test, expect } from "@playwright/test";

// A11-234: a page with a frame inside a frame. The structure sweep lists the frames as NVDA's quick navigation does: each with the first line of what it holds.
test("a page of nested frames is opened and tabbed into", async ({ page }) => {
  await page.goto("/misses/frames.html");
  await expect(page.frameLocator('iframe[title="Billing address"]').frameLocator('iframe[title="Card details"]').getByLabel("Card number")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.frameLocator('iframe[title="Billing address"]').frameLocator('iframe[title="Card details"]').getByLabel("Card number")).toBeFocused();
});

// A frame below the fold (`loading="lazy"`) is not drawn, and the browser does not tell its accessibility tree until the page is scrolled to it. A passive reader sends the page nothing, so what it lists is what the test's own scrolling showed.
test("a frame below the fold that the test never scrolls to", async ({ page }) => {
  await page.goto("/misses/frames-lazy.html");
  await expect(page.frameLocator('iframe[title="Opening hours"]').getByRole("heading", { name: "Delivery notes" })).toBeVisible();
  await page.keyboard.press("Tab");
  await page.waitForTimeout(500);
});

test("a frame below the fold that the test scrolls to", async ({ page }) => {
  await page.goto("/misses/frames-lazy.html");
  await expect(page.frameLocator('iframe[title="Opening hours"]').getByRole("heading", { name: "Delivery notes" })).toBeVisible();
  await page.locator('iframe[title="Prices"]').scrollIntoViewIfNeeded();
  await expect(page.frameLocator('iframe[title="Prices"]').getByRole("heading", { name: "Card details" })).toBeVisible();
  await page.waitForTimeout(500);
});
