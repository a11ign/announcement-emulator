import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const script = join(import.meta.dirname, "..", "sample-suite", "check-report.mjs");
const b64 = (text: string) => Buffer.from(text).toString("base64");

const LABEL = "predicted NVDA speech: advisory, not a reading of NVDA, never evidence (a11ign ADR 0047, Decision 2)";

/** A report of tests that have the two labelled attachments, with the run summary of a worker that read `snapshots` trees. */
function report(tests: { title: string; data: Record<string, unknown>; text?: string }[], snapshots = 0) {
  const dir = mkdtempSync(join(tmpdir(), "ae-check-"));
  const specs = tests.map(({ title, data, text }) => ({
    title,
    tests: [{ results: [{ parallelIndex: 0, startTime: "2026-10-24T00:00:00.000Z", attachments: [
      { name: "predicted NVDA speech", body: b64(text ?? "PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n") },
      { name: "predicted-nvda-speech.json", body: b64(JSON.stringify({ label: LABEL, predictedSpeech: [], sweeps: [], flags: [], ...data })) },
    ] }] }],
  }));
  const reportPath = join(dir, "report.json"), run = join(dir, "run.json");
  writeFileSync(reportPath, JSON.stringify({ suites: [{ specs }] }));
  writeFileSync(run, JSON.stringify({ workers: [{ snapshots, startup: { extensionUpAfterFirstTestStartedMs: null, desktopChildrenWhenUp: null } }] }));
  return { report: reportPath, run };
}

/** What a run on a platform with no desktop tree produces: nothing predicted. */
const noTreeRun = (snapshots: number) => report([{ title: "a page that loads", data: {} }], snapshots);

const check = (...args: string[]) => spawnSync("node", [script, ...args], { encoding: "utf8" });

test("without --expect-no-tree a run that read no tree fails the report check: the flags and the page load it should have predicted are missing", () => {
  const { report, run } = noTreeRun(0);
  const result = check(report, run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /no page load was predicted/);
});

test("with --expect-no-tree a run that read no tree passes: it is what the write-up says of macOS", () => {
  const { report, run } = noTreeRun(0);
  const result = check("--expect-no-tree", report, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /no tree was read, as the write-up says/);
});

test("with --expect-no-tree a run that did read a tree fails: the write-up would be out of date", () => {
  const { report, run } = noTreeRun(17);
  const result = check("--expect-no-tree", report, run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /read 17 snapshots/);
});

const speech = [{ cause: "load", text: "A page, document" }];
const sweep = [{ trigger: "load" }];
const lower = "tree: the DevTools port's accessibility tree, lower fidelity than the extension's\n";

test("with --lower-fidelity a run through the DevTools port passes when most tests have a page load, a sweep is made and one wanted flag is raised", () => {
  const ok = { treeSource: "devtools", predictedSpeech: speech, sweeps: sweep };
  const { report: path, run } = report([
    { title: "the cookie panel opens", data: { ...ok, flags: [{ flag: "silent-dialog" }] }, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}` },
    { title: "a page", data: ok, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}` },
  ], 5);
  const result = check("--lower-fidelity", path, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /a page load for 2 of 2 tests, tree through the DevTools port/);
});

test("with --lower-fidelity a flag the suite is not built to raise is counted and printed and does not fail the run, but an output that does not say where its tree came from does", () => {
  const ok = { treeSource: "devtools", predictedSpeech: speech, sweeps: sweep };
  const text = `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}`;
  const flagged = check("--lower-fidelity", ...Object.values(report([{ title: "the cookie panel opens", data: { ...ok, flags: [{ flag: "silent-dialog" }] }, text }, { title: "a page", data: { ...ok, flags: [{ flag: "unheard-error" }] }, text }], 5)));
  assert.equal(flagged.status, 0, flagged.stderr); assert.match(flagged.stdout, /1 flag\(s\) the extension's run does not raise: a page: unheard-error/);
  const unsaid = check("--lower-fidelity", ...Object.values(report([{ title: "a page", data: { ...ok, treeSource: "extension" } }], 5)));
  assert.equal(unsaid.status, 1); assert.match(unsaid.stderr, /does not say its tree came through the DevTools port/);
});

test("with --lower-fidelity a run in which most tests have no page load fails", () => {
  const { report: path, run } = report([{ title: "a", data: { treeSource: "devtools" }, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}` }], 0);
  const result = check("--lower-fidelity", path, run);
  assert.equal(result.status, 1); assert.match(result.stderr, /fewer than three in five/);
});
