import { defineConfig } from "@playwright/test";
import { config } from "./base.config";

// The suite with no middleware, in the same Chrome (BASELINE_CHROME, the one the bundle holds) but without the extension, the flags or the runtime: what the cost of the middleware is measured against.
export default defineConfig({
  ...config,
  use: { ...config.use, launchOptions: { executablePath: process.env.BASELINE_CHROME, env: { ...process.env, LD_LIBRARY_PATH: [process.env.BASELINE_LIBS, process.env.LD_LIBRARY_PATH].filter(Boolean).join(":") } as Record<string, string> } },
});
