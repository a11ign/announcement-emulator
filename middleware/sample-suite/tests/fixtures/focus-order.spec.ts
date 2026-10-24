import { test, expect } from "@playwright/test";

test("the sign-up form can be tabbed through", async ({ page }) => {
  await page.goto("/signup.html");
  for (const name of ["Home", "Basket"]) {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name })).toBeFocused();
  }
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Full name")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email address")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Send me news")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Create account" })).toBeFocused();
});

test("clicking a field puts focus in it", async ({ page }) => {
  await page.goto("/signup.html");
  await page.getByLabel("Email address").click();
  await expect(page.getByLabel("Email address")).toBeFocused();
});
