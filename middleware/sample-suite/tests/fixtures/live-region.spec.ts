import { test, expect } from "@playwright/test";

test("adding a mug updates the basket count", async ({ page }) => {
  await page.goto("/basket.html");
  await page.getByRole("button", { name: "Add a mug" }).click();
  await expect(page.getByRole("status")).toHaveText("1 item in your basket");
  await page.getByRole("button", { name: "Add a mug" }).click();
  await expect(page.getByRole("status")).toHaveText("2 items in your basket");
});
