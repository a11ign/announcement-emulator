import { test } from "node:test";
import assert from "node:assert/strict";
import { LAG_MS, annotationsFor, assign, attachments, browserBuild, describe, evidenceFieldsIn, type Window } from "./format.ts";
import { agreementFor, type SupportedVersions } from "./supported.ts";
import { ANNOTATION, ATTACH_JSON, ATTACH_TEXT, LABEL } from "./label.ts";
import type { RuntimeRecord } from "./runtime.ts";

const speech = (t: number, page: number, text: string): RuntimeRecord => ({ kind: "speech", t, page, cause: "focus", text, utterances: [text], shape: ["NAME", "ROLE"], node: { role: "button", name: "Save" }, ms: 1 });
const w = (title: string, start: number, end: number): Window => ({ title, start, end });

test("a record that arrives after its test ended is that test's, and not the next one's", () => {
  const first = w("first", 1000, 2000), second = w("second", 2100, 3000);
  const late = speech(2050, 1, "late tail of the first");
  const records = [speech(1100, 1, "in the first"), late, speech(2200, 2, "in the second")];
  const { byWindow, unassigned } = assign(records, [first, second]);
  assert.deepEqual(byWindow.get(first)!.map((r) => r.text), ["in the first", "late tail of the first"]);
  assert.deepEqual(byWindow.get(second)!.map((r) => r.text), ["in the second"]);
  assert.equal(unassigned, 0);
});

test("a page belongs to the test its first record falls in, however late its later records are", () => {
  const first = w("first", 1000, 2000), second = w("second", 2100, 3000);
  const { byWindow } = assign([speech(1500, 7, "a"), speech(2050 + LAG_MS - 100, 7, "b")], [first, second]);
  assert.equal(byWindow.get(first)!.length, 2);
  assert.equal(byWindow.get(second)!.length, 0);
});

test("a record with no page, and a page that began outside every test, belong to none", () => {
  const only = w("only", 1000, 2000);
  const { byWindow, unassigned } = assign([{ kind: "error", t: 1500, message: "x" }, speech(9000, 3, "outside")], [only]);
  assert.equal(byWindow.get(only)!.length, 0);
  assert.equal(unassigned, 2);
});

test("every output says it is a prediction, and none carries an evidence field name", () => {
  const records: RuntimeRecord[] = [speech(1100, 1, "Save, button"), { kind: "sweep", t: 1200, page: 1, trigger: "load", url: "http://x/", lists: { headings: ["Hello, heading, level 1"] }, counts: { headings: 1 }, keys: 3, notDelivered: 3, ms: 30 },
    { kind: "flag", t: 1300, page: 1, flag: "silent-dialog", detail: "d", node: null }];
  const out = describe(w("t", 1000, 2000), records, null);
  assert.match(out.text, /^PREDICTED NVDA SPEECH/);
  assert.equal(out.json.label, LABEL);
  assert.deepEqual(evidenceFieldsIn(out.json), []);
  assert.deepEqual(attachments(out).map((a) => a.name), [ATTACH_TEXT, ATTACH_JSON]);
  assert.deepEqual(out.flags, [{ flag: "silent-dialog", detail: "d" }]);
  assert.deepEqual(annotationsFor(out.flags), [{ type: ANNOTATION, description: "silent-dialog: d" }]);
});

test("the guard finds an evidence field name wherever it is", () => {
  assert.deepEqual(evidenceFieldsIn({ a: [{ transcript: [] }], b: { structure: 1 } }).sort(), [".a[0].transcript", ".b.structure"]);
});

test("a test in which nothing was predicted says so", () => {
  assert.match(describe(w("t", 0, 1), [], null).text, /no speech was predicted/);
});

const listed: SupportedVersions = { builds: [{ chromium: "156.0.8078.4", playwright: ["1.64.0", "1.64.1"], measured: { "extension-linux": { agreement: 0.912, units: 1131, date: "2026-10-26", figure: "middleware/results/playwright-versions/156.0.8078.4/extension-linux/" } } }] };

test("a test's report says the agreement measured for the build its browser ran, in the text and in the json", () => {
  const agreement = agreementFor(listed, "156.0.8078.4", "extension", "linux");
  const out = describe(w("t", 0, 1), [], null, { tree: "extension", agreement });
  assert.match(out.text, /^agreement measured for Chromium 156\.0\.8078\.4 \(Playwright 1\.64\.0, 1\.64\.1\), extension: 91\.2% of 1131 units, 2026-10-26/m);
  assert.deepEqual(out.json.agreement, agreement);
});

test("a test run in a build that is not listed says its agreement is not measured, in the text and in the json, and still carries its speech", () => {
  const agreement = agreementFor(listed, "152.0.7999.1", "extension", "linux");
  const out = describe(w("t", 1000, 2000), [speech(1100, 1, "Save, button")], null, { tree: "extension", agreement });
  assert.match(out.text, /^agreement not measured for Chromium 152\.0\.7999\.1$/m);
  assert.equal((out.json.agreement as { line: string }).line, "agreement not measured for Chromium 152.0.7999.1");
  assert.match(out.text, /Save, button/);
});

test("the DevTools source says why it was used, beside its note that the tree is of lower fidelity", () => {
  const out = describe(w("t", 0, 1), [], null, { tree: "devtools", treeWhy: "the extension was not used: run npx playwright install chromium, without --only-shell" });
  assert.match(out.text, /lower fidelity than the extension's \(the extension was not used: run npx playwright install chromium, without --only-shell\)/);
  assert.equal(out.json.treeSourceWhy, "the extension was not used: run npx playwright install chromium, without --only-shell");
});

test("the emulator line names the Chromium the mapping tables were read from, and no browser of the bundle's", () => {
  const manifest = { name: "b", platform: "linux-x64", nvda: { release: "release-2026.1.1", commit: "5d92106f17e461dac62aa48257bbbf4183e033d0" }, chromiumTables: "155.0.8059.84", python: "3.13.16", commit: "abc" };
  assert.match(describe(w("t", 0, 1), [], manifest).text, /emulator: NVDA release-2026\.1\.1 \(5d92106f\), Chromium 155\.0\.8059\.84 mapping tables, bundle b/);
});

test("the build a worker ran in is the one its browser named when the runtime reached it", () => {
  const start = (what: string, browser?: string): RuntimeRecord => ({ kind: "start", t: 1, what, ...(browser ? { browser } : {}) });
  assert.equal(browserBuild([start("extension"), start("devtools", "156.0.8078.4")]), "156.0.8078.4");
  assert.equal(browserBuild([start("devtools")]), null);
  assert.equal(browserBuild([]), null);
});
