import { defineConfig } from "@playwright/test";
import { config } from "./base.config";

// The suite with no middleware, in the same browser the middleware runs in (whichever one a launch left to Playwright gets: the middleware names none) but without the flags or the runtime:
// what the cost of the middleware is measured against.
export default defineConfig(config);
