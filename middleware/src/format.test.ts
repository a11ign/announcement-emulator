import { test } from "node:test";
import assert from "node:assert/strict";
import { LAG_MS, annotationsFor, assign, attachments, describe, evidenceFieldsIn, type Window } from "./format.ts";
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
