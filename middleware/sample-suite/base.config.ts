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
    // contexts the suite opens itself (`browser.newContext()`): the DevTools tree serves them, an extension does not run in them (A11-229)
    { name: "contexts", testDir: "./tests/contexts" },
    // pages written for the faults the agreement measurement attributed to the middleware (A11-234): one test for each, recorded and replayed in middleware/runtime
    { name: "misses", testDir: "./tests/misses" },
    // the window the fleet's Edge reports (innerWidth x innerHeight, as emu/session.mjs sets it), so that what is on the screen when a stop is read is what was on its screen
    { name: "corpus", testDir: "./tests/corpus", timeout: 180_000, use: { viewport: { width: 1008, height: 729 } } },
    // the same walk on table- and list-heavy pages (A11-229, step 2: results/tree-source-structure/rule.md)
    { name: "structure", testDir: "./tests/structure", timeout: 180_000, use: { viewport: { width: 1008, height: 729 } } },
    // the structure project's pages at the pace of a test that waits for the page: the cost of reading the tree is measured with it (A11-229, step 2: results/devtools-source/cost)
    { name: "paced", testDir: "./tests/paced", timeout: 300_000, use: { viewport: { width: 1008, height: 729 } } },
    // the five pages the structure measurement left out for their size, 705 to 1,770 tab stops (A11-229, step 2): the middleware predicted nothing for them
    { name: "large", testDir: "./tests/large", timeout: 900_000, use: { viewport: { width: 1008, height: 729 } } },
    // two small local pages that carry the fields the DevTools tree source was found to lack; their recordings are the fixtures it is held to (A11-229, step 1)
    { name: "fields", testDir: "./tests/fields" },
  ],
};
