import { test, expect } from "@playwright/test";

test("the delete dialog opens and closes", async ({ page }) => {
  await page.goto("/dialog.html");
  await page.getByRole("button", { name: "Delete account" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});

test("the cookie panel opens", async ({ page }) => {
  await page.goto("/silent-dialog.html");
  await page.getByRole("button", { name: "Cookie settings" }).click();
  await expect(page.getByRole("dialog", { name: "Cookie settings" })).toBeVisible();
});
