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
    { name: "corpus", testDir: "./tests/corpus", timeout: 600_000 },
  ],
};
