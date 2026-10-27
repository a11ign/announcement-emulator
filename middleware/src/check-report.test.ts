import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const script = join(import.meta.dirname, "..", "sample-suite", "check-report.mjs");
const b64 = (text: string) => Buffer.from(text).toString("base64");

const LABEL = "predicted NVDA speech: advisory, not a reading of NVDA, never evidence (a11ign ADR 0047, Decision 2)";

/** A report of tests that have the two labelled attachments, with the run summary of a worker that read `snapshots` trees and ran in `chromium`. */
function report(tests: { title: string; data: Record<string, unknown>; text?: string }[], snapshots = 0, chromium: string | null = null) {
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
  writeFileSync(run, JSON.stringify({ workers: [{ snapshots, startup: { chromium } }] }));
  return { report: reportPath, run };
}

/** What a run that read no tree produces: nothing predicted. */
const noTreeRun = (snapshots: number) => report([{ title: "a page that loads", data: {} }], snapshots);

const check = (...args: string[]) => spawnSync("node", [script, ...args], { encoding: "utf8" });

test("a run that read no tree fails the report check: macOS gives a tree through the DevTools port too, so there is no platform that predicts nothing", () => {
  const { report, run } = noTreeRun(0);
  const result = check(report, run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /a page load was predicted for 0 of 1 tests: fewer than three in five/);
  assert.match(result.stderr, /no sweep was made/);
});

test("the options that went with the extension are refused, so that a check file written for it does not pass for what it no longer checks", () => {
  const { report, run } = noTreeRun(0);
  for (const gone of ["--expect-no-tree", "--lower-fidelity"]) {
    const result = check(gone, report, run);
    assert.equal(result.status, 2, gone);
    assert.match(result.stderr, new RegExp(`unknown option ${gone}`));
  }
});

const speech = [{ cause: "load", text: "A page, document" }];
const sweep = [{ trigger: "load" }];

test("a run through the DevTools port passes when most tests have a page load, a sweep is made and one wanted flag is raised", () => {
  const ok = { treeSource: "devtools", predictedSpeech: speech, sweeps: sweep };
  const { report: path, run } = report([
    { title: "the cookie panel opens", data: { ...ok, flags: [{ flag: "silent-dialog" }] }, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n` },
    { title: "a page", data: ok, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n` },
  ], 5);
  const result = check(path, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /a page load for 2 of 2 tests, tree through the DevTools port/);
});

test("a flag the suite is not built to raise is counted and printed and does not fail the run, but an output that does not say where its tree came from does", () => {
  const ok = { treeSource: "devtools", predictedSpeech: speech, sweeps: sweep };
  const text = `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n`;
  const flagged = check(...Object.values(report([{ title: "the cookie panel opens", data: { ...ok, flags: [{ flag: "silent-dialog" }] }, text }, { title: "a page", data: { ...ok, flags: [{ flag: "unheard-error" }] }, text }], 5)));
  assert.equal(flagged.status, 0, flagged.stderr); assert.match(flagged.stdout, /1 flag\(s\) the suite is not built to raise for that test: a page: unheard-error/);
  const unsaid = check(...Object.values(report([{ title: "a page", data: { ...ok, treeSource: "extension" } }], 5)));
  assert.equal(unsaid.status, 1); assert.match(unsaid.stderr, /does not say its tree came through the DevTools port/);
});

test("a run in which most tests have no page load fails", () => {
  const { report: path, run } = report([{ title: "a", data: { treeSource: "devtools" }, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n` }], 0);
  const result = check(path, run);
  assert.equal(result.status, 1); assert.match(result.stderr, /fewer than three in five/);
});

const PREDICTION = "PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n";
const devtoolsData = { treeSource: "devtools", predictedSpeech: speech, sweeps: sweep };
const devtoolsRun = (agreement: string, chromium: string | null = "156.0.8078.4", line?: string) => report([{ title: "the cookie panel opens", data: { ...devtoolsData, flags: [{ flag: "silent-dialog" }], agreement: { line: line ?? agreement } },
  text: `${PREDICTION}${agreement}\n` }], 5, chromium);

test("with --expect-unmeasured a run in a build that is not listed passes when every test says exactly so, and the worker ran in that build", () => {
  const line = "agreement not measured for Chromium 156.0.8078.4";
  const { report: path, run } = devtoolsRun(line);
  const result = check("--expect-unmeasured", "156.0.8078.4", path, run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Chromium 156\.0\.8078\.4, agreement not measured/);
});

test("with --expect-unmeasured a test that says another build, another wording or carries the line only in its json fails", () => {
  const other = devtoolsRun("agreement not measured for Chromium 153.0.8010.12");
  assert.match(check("--expect-unmeasured", "156.0.8078.4", other.report, other.run).stderr, /wanted "agreement not measured for Chromium 156\.0\.8078\.4"/);
  const measured = devtoolsRun("agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.1), devtools: 80.4% of 10 units, 2026-10-26 (x)");
  assert.equal(check("--expect-unmeasured", "156.0.8078.4", measured.report, measured.run).status, 1);
  const jsonOnly = report([{ title: "a", data: { ...devtoolsData, agreement: { line: "agreement not measured for Chromium 156.0.8078.4" } }, text: `${PREDICTION}` }], 5, "156.0.8078.4");
  assert.match(check("--expect-unmeasured", "156.0.8078.4", jsonOnly.report, jsonOnly.run).stderr, /does not carry the agreement line/);
});

test("with --expect-unmeasured a worker that ran in another Chromium than the one wanted fails: the suite ran in a browser of the bundle's or the wrong Playwright's", () => {
  const { report: path, run } = devtoolsRun("agreement not measured for Chromium 156.0.8078.4", "155.0.8059.84");
  const result = check("--expect-unmeasured", "156.0.8078.4", path, run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /worker 0: ran in Chromium 155\.0\.8059\.84, wanted 156\.0\.8078\.4/);
});

test("with --expect-measured a listed build's sentence passes and an unmeasured one fails", () => {
  const good = devtoolsRun("agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.0, 1.64.1), devtools: 80.4% of 1131 units, 2026-10-26 (middleware/results/x/)");
  assert.equal(check("--expect-measured", "156.0.8078.4", good.report, good.run).status, 0);
  const bad = devtoolsRun("agreement not measured for Chromium 156.0.8078.4");
  const result = check("--expect-measured", "156.0.8078.4", bad.report, bad.run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /wanted a measured one for Chromium 156\.0\.8078\.4/);
});

const FIGURE = "middleware/results/agreement-round-1/held-out/156.0.8078.4/devtools-linux/";
const ROUND_LINE = `agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.1), devtools: 83.1% of 249 units on 6 held-out pages, 2026-10-26; the fleet agrees with itself on 95.2% (${FIGURE})`;

test("with --expect-measured the sentence a round's figure makes, with its population, date and ceiling, passes", () => {
  const good = devtoolsRun(ROUND_LINE);
  const result = check("--expect-measured", "156.0.8078.4", good.report, good.run);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Chromium 156\.0\.8078\.4, agreement measured/);
});

/** A run of one test whose one utterance has the rate the figure gives its shape; `text` is the utterance's line, as the report writes it. */
interface Shaped { rate?: Record<string, unknown>; text: string; line?: string; row?: Record<string, unknown>; measured?: boolean }
function shaped({ rate, text, line = ROUND_LINE, row = {}, measured = true }: Shaped) {
  const utterance = { cause: "load", text: "Save, button", ...(rate ? { shapeRate: rate } : {}), ...row };
  return report([{ title: "the cookie panel opens", data: { ...devtoolsData, flags: [{ flag: "silent-dialog" }], predictedSpeech: [utterance], agreement: { line, measured, shapes: measured ? { "NAME + ROLE": {} } : undefined } },
    text: `${PREDICTION}${line}\n\n${text}\n` }], 5, "156.0.8078.4");
}
const checkRates = (r: { report: string; run: string }) => check("--expect-shape-rates", r.report, r.run);
const NOT_MEASURED = "agreement not measured for Chromium 156.0.8078.4";

test("with --expect-shape-rates an utterance that carries its shape's rate in the text and in the json passes, weak or not measured as well", () => {
  const ok = checkRates(shaped({ rate: { shape: "NAME + ROLE", measured: true, agreement: 0.86, units: 57 }, text: "+0.10s  load    Save, button  [NAME + ROLE: 86.0% of 57]" }));
  assert.equal(ok.status, 0, ok.stderr); assert.match(ok.stdout, /a rate by shape on 1 utterances \(0 low confidence\)/);
  const weak = checkRates(shaped({ rate: { shape: "NAME", measured: true, agreement: 0.682, units: 22, lowConfidence: true }, text: "+0.10s  load    Save, button  [NAME: 68.2% of 22, low confidence]", row: { lowConfidence: true } }));
  assert.equal(weak.status, 0, weak.stderr); assert.match(weak.stdout, /\(1 low confidence\)/);
  const unseen = checkRates(shaped({ rate: { shape: "ROLE + NAME", measured: false }, text: "+0.10s  load    Save, button  [shape not measured]" }));
  assert.equal(unseen.status, 0, unseen.stderr);
});

test("with --expect-shape-rates an utterance with no rate, a rate the text does not carry, or a weak one that is not flagged fails", () => {
  assert.match(checkRates(shaped({ text: "+0.10s  load    Save, button" })).stderr, /"Save, button" carries no rate for its shape/);
  assert.match(checkRates(shaped({ rate: { shape: "NAME + ROLE", measured: true, agreement: 0.86, units: 57 }, text: "+0.10s  load    Save, button" })).stderr, /the text does not carry "\[NAME \+ ROLE: 86\.0% of 57\]"/);
  const unflagged = checkRates(shaped({ rate: { shape: "NAME", measured: true, agreement: 0.682, units: 22, lowConfidence: true }, text: "+0.10s  load    Save, button  [NAME: 68.2% of 22, low confidence]" }));
  assert.equal(unflagged.status, 1); assert.match(unflagged.stderr, /is low confidence in its rate, and not flagged/);
});

test("with --expect-shape-rates a run whose figure has no shapes is held to carrying none", () => {
  const none = checkRates(shaped({ text: "+0.10s  load    Save, button", line: NOT_MEASURED, measured: false }));
  assert.equal(none.status, 0, none.stderr);
  const claimed = checkRates(shaped({ rate: { shape: "NAME + ROLE", measured: false }, text: "+0.10s  load    Save, button  [shape not measured]", line: NOT_MEASURED, measured: false }));
  assert.equal(claimed.status, 1); assert.match(claimed.stderr, /carries a rate by shape, and the build's figure has none/);
});

test("an option check-report does not know is refused, and the flag check is not skipped for a suite whose tests were renamed", () => {
  const { report: path, run } = noTreeRun(0);
  const misspelt = check("--expect-no-tre", path, run);
  assert.equal(misspelt.status, 2);
  assert.match(misspelt.stderr, /unknown option --expect-no-tre/);
  const viaPort = report([{ title: "a test nobody listed", data: { treeSource: "devtools", predictedSpeech: speech, sweeps: sweep }, text: `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n` }], 5);
  assert.match(check(viaPort.report, viaPort.run).stderr, /none of the flags the sample suite is built to raise was raised/);
});

test("a test that opens a context of its own is held to the speech of both its pages, and a project of tests that raise no flag does not fail the flag check", () => {
  const title = "a context the suite opens itself is announced like the page the fixture gives it";
  const text = `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE\n`;
  const both = report([{ title, data: { treeSource: "devtools", predictedSpeech: [{ cause: "load", text: "Full name, edit" }, { cause: "focus", text: "Add a mug, button" }], sweeps: sweep }, text }], 5);
  const ok = check(both.report, both.run);
  assert.equal(ok.status, 0, ok.stderr);
  const one = report([{ title, data: { treeSource: "devtools", predictedSpeech: [{ cause: "load", text: "Full name, edit" }], sweeps: sweep }, text }], 5);
  const result = check(one.report, one.run);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /nothing predicted contains "Add a mug"/);
});

test("an option that takes a build and is given none is refused, and does not turn the build check off", () => {
  const { report: path, run } = noTreeRun(0);
  const last = check("--expect-measured", ...[]);
  assert.equal(last.status, 2); assert.match(last.stderr, /--expect-measured needs a value/);
  const swallowed = check("--expect-unmeasured", "--expect-shape-rates", path, run);
  assert.equal(swallowed.status, 2); assert.match(swallowed.stderr, /--expect-unmeasured needs a value/);
});
