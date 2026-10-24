import { test, expect } from "@playwright/test";

test("the home page links to sign-up", async ({ page }) => {
  await page.goto("/index.html");
  await page.getByRole("main").getByRole("link", { name: "Create an account" }).click();
  await expect(page).toHaveURL(/signup\.html$/);
  await expect(page.getByRole("heading", { name: "Create an account" })).toBeVisible();
});

test("the shop switches section without loading a page", async ({ page }) => {
  await page.goto("/spa.html");
  await page.getByRole("link", { name: "Boots" }).click();
  await expect(page.getByRole("heading", { name: "Boots" })).toBeVisible();
  await expect(page).toHaveTitle("Boots - Shop");
});
