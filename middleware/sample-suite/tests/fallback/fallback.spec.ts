import { test, expect } from "@playwright/test";

// Run with playwright.fallback.config.ts: a config that disables extensions, so the companion extension does not load and posts no tree. The first test holds a page open for longer than the runtime
// waits for the extension (ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT, set low by whoever runs this), so the runtime reads the trees through the DevTools port from then on; the second is opened after that.
test.describe.configure({ mode: "serial" });

test("a page that outlives the wait for the extension", async ({ page }) => {
  await page.goto("/index.html");
  await page.waitForTimeout(Number(process.env.FALLBACK_HOLD_MS ?? 5000));
});

test("a page opened after the runtime switched to the DevTools port gets its predicted speech", async ({ page }) => {
  await page.goto("/signup.html");
  await page.getByLabel("Email address").focus();
  await expect(page.getByLabel("Email address")).toBeFocused();
  await page.waitForTimeout(500);
});
