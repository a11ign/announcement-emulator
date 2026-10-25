import type { PlaywrightTestConfig } from "@playwright/test";

// The suite's configuration as a team has it. Nothing here mentions a screen reader.
export const config: PlaywrightTestConfig = {
  testDir: "./tests",
  fullyParallel: true,
  workers: process.env.WORKERS ? Number(process.env.WORKERS) : 2,
  reporter: [["html", { open: "never" }], ["json", { outputFile: "test-results/report.json" }]],
  webServer: { command: "node serve.mjs", url: "http://127.0.0.1:4173/index.html", reuseExistingServer: true },
  use: { baseURL: "http://127.0.0.1:4173" },
  projects: [
    { name: "fixtures", testDir: "./tests/fixtures" },
    // contexts the suite opens itself (`browser.newContext()`), with the tree source left to the middleware
    { name: "contexts", testDir: "./tests/contexts" },
    // the window the fleet's Edge reports (innerWidth x innerHeight, as emu/session.mjs sets it), so that what is on the screen when a stop is read is what was on its screen
    { name: "corpus", testDir: "./tests/corpus", timeout: 180_000, use: { viewport: { width: 1008, height: 729 } } },
  ],
};
