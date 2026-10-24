// What the middleware adds to the sample suite's run (A11-208, question 6): the same project run with it and without it, several times, at one or more worker counts.
//   BASELINE_CHROME=<the bundle's chrome> [BASELINE_LIBS=<its libs>] node cost.mjs [--project fixtures] [--runs 3] [--workers 1,2,4] [--out cost.json]
// Each run is `playwright test`; its wall time is the process's, its tests' time is the sum of the JSON report's durations, and the middleware's own counts are in test-results/announcement-emulator/run.json.
import { spawnSync } from "node:child_process";
import { readFileSync, rmSync, writeFileSync } from "node:fs";

const arg = (name, fallback) => { const at = process.argv.indexOf(`--${name}`); return at >= 0 ? process.argv[at + 1] : fallback; };
const project = arg("project", "fixtures"), runs = Number(arg("runs", "3")), workerCounts = arg("workers", "2").split(",").map(Number), out = arg("out", "cost.json");
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

function once(config, workers, env) {
  rmSync("test-results", { recursive: true, force: true }); rmSync("playwright-report", { recursive: true, force: true });
  const start = performance.now();
  const run = spawnSync("npx", ["playwright", "test", `--config=${config}`, `--project=${project}`, `--workers=${workers}`], { env: { ...process.env, ...env }, encoding: "utf8" });
  const wall = performance.now() - start;
  const report = JSON.parse(readFileSync("test-results/report.json", "utf8"));
  const durations = [];
  (function walk(s) { for (const c of s.suites ?? []) walk(c); for (const spec of s.specs ?? []) for (const t of spec.tests) durations.push(t.results.at(-1).duration); })({ suites: report.suites });
  let middleware = null;
  try { middleware = JSON.parse(readFileSync("test-results/announcement-emulator/run.json", "utf8")); } catch { /* the run without the middleware has none */ }
  return { wall, ok: run.status === 0, tests: durations.length, testsMs: durations.reduce((a, b) => a + b, 0), reportMs: report.stats.duration, middleware };
}

const rows = [];
for (const workers of workerCounts) {
  for (const [label, config, env] of [["without", "playwright.baseline.config.ts", {}], ["with", "playwright.config.ts", {}], ["with, no sweeps", "playwright.config.ts", { ANNOUNCEMENT_EMULATOR_SWEEPS: "0" }]]) {
    const results = Array.from({ length: runs }, () => once(config, workers, env));
    rows.push({ label, workers, results });
    const w = results.map((r) => Math.round(r.wall));
    console.log(`${String(workers).padStart(2)} workers  ${label.padEnd(16)} wall ms ${w.join(" ")}  median ${median(w)}  tests ${results[0].tests}  ok ${results.every((r) => r.ok)}`);
  }
}
writeFileSync(out, JSON.stringify(rows, null, 1));
