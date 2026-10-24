import { test, expect } from "@playwright/test";

test("a name typed key by key is kept", async ({ page }) => {
  await page.goto("/signup.html");
  await page.getByLabel("Full name").click();
  await page.keyboard.type("Ada");
  await expect(page.getByLabel("Full name")).toHaveValue("Ada");
});

test("a name filled in one step is kept", async ({ page }) => {
  await page.goto("/signup.html");
  await page.getByLabel("Full name").fill("Ada Lovelace");
  await expect(page.getByLabel("Full name")).toHaveValue("Ada Lovelace");
});
