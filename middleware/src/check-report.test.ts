import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const script = join(import.meta.dirname, "..", "sample-suite", "check-report.mjs");
const b64 = (text: string) => Buffer.from(text).toString("base64");

/** A report of one test that has the two labelled attachments and nothing predicted: what a run on a platform with no desktop tree produces. */
function noTreeRun(snapshots: number) {
  const dir = mkdtempSync(join(tmpdir(), "ae-check-"));
  const data = { label: "predicted NVDA speech: advisory, not a reading of NVDA, never evidence", predictedSpeech: [], sweeps: [], flags: [] };
  const result = {
    parallelIndex: 0,
    startTime: "2026-10-24T00:00:00.000Z",
    attachments: [
      { name: "predicted NVDA speech", body: b64("PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n") },
      { name: "predicted-nvda-speech.json", body: b64(JSON.stringify(data)) },
    ],
  };
  const report = join(dir, "report.json"), run = join(dir, "run.json");
  writeFileSync(report, JSON.stringify({ suites: [{ specs: [{ title: "a page that loads", tests: [{ results: [result] }] }] }] }));
  writeFileSync(run, JSON.stringify({ workers: [{ snapshots, startup: { extensionUpAfterFirstTestStartedMs: null, desktopChildrenWhenUp: null } }] }));
  return { report, run };
}

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
