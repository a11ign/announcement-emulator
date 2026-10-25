import { defineConfig } from "@playwright/test";
import { config } from "./base.config";

// The suite with no middleware, in the same browser the middleware runs in (Playwright's own full Chromium, headless in the new mode: `channel: "chromium"`) but without the extension, the flags or the runtime:
// what the cost of the middleware is measured against.
export default defineConfig({ ...config, use: { ...config.use, channel: "chromium" } });
