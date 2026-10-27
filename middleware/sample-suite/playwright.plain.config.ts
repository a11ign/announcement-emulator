import { defineConfig } from "@playwright/test";
import { config } from "./base.config";

// The same suite with no middleware. `npx foresay test --config playwright.plain.config.ts` attaches it without changing this file.
export default defineConfig(config);
