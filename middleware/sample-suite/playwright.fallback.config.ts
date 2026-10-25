import { defineConfig } from "@playwright/test";
import { withAnnouncements } from "@a11ign/announcement-emulator";
import { config } from "./base.config";

// A setup the extension cannot serve: the team runs Playwright's headless shell (`channel: "chromium-headless-shell"`), which loads no extension. The channel is the team's own, so the middleware does not
// change it and, left at `auto`, tries the extension there and finds out at run time that it posts no tree. One worker, because the switch is the worker's. The tests do not change, and the runs of this
// config are held by `check-report.mjs --expect-fallback`. Run it on a platform where `auto` picks the extension (not macOS), with ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT set low (2) to keep it short.
export default defineConfig(withAnnouncements({
  ...config,
  workers: 1,
  fullyParallel: false,
  use: { ...config.use, channel: "chromium-headless-shell" },
  projects: [{ name: "fallback", testDir: "./tests/fallback" }],
}));
