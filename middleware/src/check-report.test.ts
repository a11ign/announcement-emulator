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
function report(tests: { title: string; data: Record<string, unknown>; text?: string; startTime?: string }[], snapshots = 0, chromium: string | null = null, startup: Record<string, unknown> = {}) {
  const dir = mkdtempSync(join(tmpdir(), "ae-check-"));
  const specs = tests.map(({ title, data, text, startTime }) => ({
    title,
    tests: [{ results: [{ parallelIndex: 0, startTime: startTime ?? "2026-10-24T00:00:00.000Z", attachments: [
      { name: "predicted NVDA speech", body: b64(text ?? "PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n") },
      { name: "predicted-nvda-speech.json", body: b64(JSON.stringify({ label: LABEL, predictedSpeech: [], sweeps: [], flags: [], ...data })) },
    ] }] }],
  }));
  const reportPath = join(dir, "report.json"), run = join(dir, "run.json");
  writeFileSync(reportPath, JSON.stringify({ suites: [{ specs }] }));
  writeFileSync(run, JSON.stringify({ workers: [{ snapshots, startup: { extensionUpAfterFirstTestStartedMs: null, desktopChildrenWhenUp: null, chromium, ...startup } }] }));
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
const WHY = "macOS gives the extension no desktop tree", RATE = "the devtools tree agreed with a real NVDA on 83.6% of 1,026 units on macOS, Chrome 155, six pages (A11-229)";
const lower = `tree: the DevTools port's accessibility tree (${WHY}); ${RATE}\n`;
const viaDevtools = { treeSource: "devtools", treeSourceWhy: WHY, treeSourceAgreement: RATE };

test("with --devtools-tree a run through the DevTools port passes when most tests have a page load, a sweep is made and one wanted flag is raised", () => {
  const ok = { ...viaDevtools, predictedSpeech: speech, sweeps: sweep };
  const { report: path, run } = report([
    { title: "the cookie panel opens", data: { ...ok, flags: [{ flag: "silent-dialog" }] }, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}` },
    { title: "a page", data: ok, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}` },
  ], 5);
  const result = check("--devtools-tree", path, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /a page load for 2 of 2 tests, tree through the DevTools port/);
});

test("with --devtools-tree a flag the suite is not built to raise is counted and printed and does not fail the run, but an output that does not say where its tree came from does", () => {
  const ok = { ...viaDevtools, predictedSpeech: speech, sweeps: sweep };
  const text = `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}`;
  const flagged = check("--devtools-tree", ...Object.values(report([{ title: "the cookie panel opens", data: { ...ok, flags: [{ flag: "silent-dialog" }] }, text }, { title: "a page", data: { ...ok, flags: [{ flag: "unheard-error" }] }, text }], 5)));
  assert.equal(flagged.status, 0, flagged.stderr); assert.match(flagged.stdout, /1 flag\(s\) the extension's run does not raise: a page: unheard-error/);
  const unsaid = check("--devtools-tree", ...Object.values(report([{ title: "a page", data: { ...ok, treeSource: "extension" } }], 5)));
  assert.equal(unsaid.status, 1); assert.match(unsaid.stderr, /the output says its tree came from extension, wanted devtools/);
});

test("with --devtools-tree a run in which most tests have no page load fails", () => {
  const { report: path, run } = report([{ title: "a", data: viaDevtools, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n${lower}` }], 0);
  const result = check("--devtools-tree", path, run);
  assert.equal(result.status, 1); assert.match(result.stderr, /fewer than three in five/);
});

const PREDICTION = "PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n";
const lowerData = { ...viaDevtools, predictedSpeech: speech, sweeps: sweep };
const lowerOf = (agreement: string, chromium: string | null = "156.0.8078.4", line?: string) => report([{ title: "the cookie panel opens", data: { ...lowerData, flags: [{ flag: "silent-dialog" }], agreement: { line: line ?? agreement } },
  text: `${PREDICTION}${lower}${agreement}\n` }], 5, chromium);

test("with --expect-unmeasured a run in a build that is not listed passes when every test says exactly so, and the worker ran in that build", () => {
  const line = "agreement not measured for Chromium 156.0.8078.4";
  const { report: path, run } = lowerOf(line);
  const result = check("--devtools-tree", "--expect-unmeasured", "156.0.8078.4", path, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Chromium 156\.0\.8078\.4, agreement not measured/);
});

test("with --expect-unmeasured a test that says another build, another wording or carries the line only in its json fails", () => {
  const other = lowerOf("agreement not measured for Chromium 153.0.8010.12");
  assert.match(check("--devtools-tree", "--expect-unmeasured", "156.0.8078.4", other.report, other.run).stderr, /wanted "agreement not measured for Chromium 156\.0\.8078\.4"/);
  const measured = lowerOf("agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.1), devtools: 80.4% of 10 units, 2026-10-26 (x)");
  assert.equal(check("--devtools-tree", "--expect-unmeasured", "156.0.8078.4", measured.report, measured.run).status, 1);
  const jsonOnly = report([{ title: "a", data: { ...lowerData, agreement: { line: "agreement not measured for Chromium 156.0.8078.4" } }, text: `${PREDICTION}${lower}` }], 5, "156.0.8078.4");
  assert.match(check("--devtools-tree", "--expect-unmeasured", "156.0.8078.4", jsonOnly.report, jsonOnly.run).stderr, /does not carry the agreement line/);
});

test("with --expect-unmeasured a worker that ran in another Chromium than the one wanted fails: the suite ran in a browser of the bundle's or the wrong Playwright's", () => {
  const { report: path, run } = lowerOf("agreement not measured for Chromium 156.0.8078.4", "155.0.8059.84");
  const result = check("--devtools-tree", "--expect-unmeasured", "156.0.8078.4", path, run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /worker 0: ran in Chromium 155\.0\.8059\.84, wanted 156\.0\.8078\.4/);
});

test("with --expect-measured a listed build's sentence passes and an unmeasured one fails", () => {
  const good = lowerOf("agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.0, 1.64.1), devtools: 80.4% of 1131 units, 2026-10-26 (middleware/results/x/)");
  assert.equal(check("--devtools-tree", "--expect-measured", "156.0.8078.4", good.report, good.run).status, 0);
  const bad = lowerOf("agreement not measured for Chromium 156.0.8078.4");
  const result = check("--devtools-tree", "--expect-measured", "156.0.8078.4", bad.report, bad.run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /wanted a measured one for Chromium 156\.0\.8078\.4/);
});

const EXT_WHY = "the default where the browser gives the extension a desktop tree", EXT_RATE = "the extension tree agreed with a real NVDA on 82.1% of 1,138 units on Linux, Chrome 155, six pages (A11-229)";
const viaExtension = { treeSource: "extension", treeSourceWhy: EXT_WHY, treeSourceAgreement: EXT_RATE };
const extensionLine = `tree: the companion extension's accessibility tree (${EXT_WHY}); ${EXT_RATE}\n`;

test("without a flag a run is held to the extension: each test says its tree is the extension's, why, and the rate that source was measured at", () => {
  const good = report([{ title: "a page", data: { ...viaExtension, predictedSpeech: speech, sweeps: sweep }, text: `${PREDICTION}${extensionLine}` }], 5);
  assert.equal(check(good.report, good.run).status, 0);
  const viaPort = report([{ title: "a page", data: { ...viaDevtools, predictedSpeech: speech, sweeps: sweep }, text: `${PREDICTION}${lower}` }], 5);
  assert.match(check(viaPort.report, viaPort.run).stderr, /the output says its tree came from devtools, wanted extension/);
  const unsaid = report([{ title: "a page", data: { treeSource: "extension", predictedSpeech: speech, sweeps: sweep }, text: PREDICTION }], 5);
  const result = check(unsaid.report, unsaid.run);
  assert.match(result.stderr, /does not say why its tree came from there/);
  assert.match(result.stderr, /the text does not say where its tree came from and why/);
  assert.match(result.stderr, /does not say how well its tree source was measured to agree/);
});

const WHY_FELL = "the extension posted no tree within 5 s of the first page, so the trees are read through the DevTools port";
const fellData = { ...viaDevtools, treeSourceWhy: WHY_FELL, treeSourceFellBack: true, predictedSpeech: speech, sweeps: sweep };
const fellText = `${PREDICTION}tree: the DevTools port's accessibility tree (${WHY_FELL}); ${RATE}\n`;

test("with --expect-fallback a run whose extension posted no tree passes when every test says the runtime switched to the DevTools port, why, and the summary says when", () => {
  const { report: path, run } = report([{ title: "a page", data: fellData, text: fellText }, { title: "another", data: fellData, text: fellText }], 5, null, { fellBackAfterFirstTestStartedMs: 4000 });
  const result = check("--expect-fallback", path, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /the extension posted no tree and the runtime switched to the DevTools port/);
});

test("with --expect-fallback a run that did not switch fails: the output says the extension's tree, or records no fallback, or the summary has no switch time", () => {
  const extension = report([{ title: "a page", data: { ...viaExtension, predictedSpeech: speech, sweeps: sweep }, text: `${PREDICTION}${extensionLine}` }], 5, null, { fellBackAfterFirstTestStartedMs: 4000 });
  assert.match(check("--expect-fallback", extension.report, extension.run).stderr, /the output says its tree came from extension, wanted devtools/);
  const unrecorded = report([{ title: "a page", data: { ...fellData, treeSourceFellBack: undefined }, text: fellText }], 5, null, { fellBackAfterFirstTestStartedMs: 4000 });
  assert.match(check("--expect-fallback", unrecorded.report, unrecorded.run).stderr, /does not record the fallback/);
  const untimed = report([{ title: "a page", data: fellData, text: fellText }], 5);
  assert.match(check("--expect-fallback", untimed.report, untimed.run).stderr, /does not say when the runtime switched/);
  const forced = report([{ title: "a page", data: { ...fellData, treeSourceWhy: "ANNOUNCEMENT_EMULATOR_TREE=devtools" }, text: fellText }], 5, null, { fellBackAfterFirstTestStartedMs: 4000 });
  assert.match(check("--expect-fallback", forced.report, forced.run).stderr, /wanted one that matches/);
});

test("with --expect-fallback a test that began after the switch is held to its page load, and one that began before it is not", () => {
  const silent = { ...fellData, predictedSpeech: [] };
  const at = (seconds: number) => `2026-10-24T00:00:${String(seconds).padStart(2, "0")}.000Z`;
  const tests = (silentAt: number) => [{ title: "first", data: fellData, text: fellText }, { title: "silent", data: silent, text: fellText, startTime: at(silentAt) }];
  const after = report(tests(10), 5, null, { fellBackAfterFirstTestStartedMs: 4000 });
  assert.match(check("--expect-fallback", after.report, after.run).stderr, /silent: began after the switch to the DevTools port and no page load was predicted/);
  const before = report(tests(2), 5, null, { fellBackAfterFirstTestStartedMs: 4000 });
  assert.equal(check("--expect-fallback", before.report, before.run).status, 0);
});

test("a test that opens a context of its own is held to the speech of both its pages: the fixture's and the one it opened", () => {
  const title = "a context the suite opens itself is announced like the page the fixture gives it";
  const said = (...texts: string[]) => report([{ title, data: { ...viaExtension, predictedSpeech: texts.map((text) => ({ cause: "focus", text })).concat(speech), sweeps: sweep }, text: `${PREDICTION}${extensionLine}` }], 5);
  const both = said("Full name, edit, blank", "Add a mug, button");
  assert.equal(check(both.report, both.run).status, 0);
  const one = said("Full name, edit, blank");
  const result = check(one.report, one.run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /nothing predicted contains "Add a mug"/);
});

test("an option check-report does not know is refused, and the flag check is not skipped for a suite whose tests were renamed", () => {
  const { report: path, run } = noTreeRun(0);
  const misspelt = check("--expect-fallbak", path, run);
  assert.equal(misspelt.status, 2);
  assert.match(misspelt.stderr, /unknown option --expect-fallbak/);
  const renamed = report([{ title: "a test nobody listed", data: { ...viaExtension, predictedSpeech: speech, sweeps: sweep }, text: `${PREDICTION}${extensionLine}` }], 5);
  assert.equal(check(renamed.report, renamed.run).status, 0, "the extension's run is held to its flags, and a test with none expected passes");
  const viaPort = report([{ title: "a test nobody listed", data: { ...viaDevtools, predictedSpeech: speech, sweeps: sweep }, text: `${PREDICTION}${lower}` }], 5);
  assert.match(check("--devtools-tree", viaPort.report, viaPort.run).stderr, /none of the flags the sample suite is built to raise was raised/);
});
