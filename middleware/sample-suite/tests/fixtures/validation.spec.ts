import { test, expect } from "@playwright/test";

test("an empty email is refused and the field is focused", async ({ page }) => {
  await page.goto("/validation-focus.html");
  await page.getByRole("button", { name: "Subscribe" }).click();
  await expect(page.getByText("Enter an email address")).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeFocused();
});

test("an empty email is refused", async ({ page }) => {
  await page.goto("/validation-silent.html");
  await page.getByRole("button", { name: "Subscribe" }).click();
  await expect(page.getByText("Enter an email address")).toBeVisible();
});

test("an empty email is refused with an alert", async ({ page }) => {
  await page.goto("/validation-alert.html");
  await page.getByRole("button", { name: "Subscribe" }).click();
  await expect(page.getByText("Enter an email address")).toBeVisible();
});
