// Reads the JSON report of a run of this suite and checks what the middleware put in it (A11-208's acceptance): every test has the two attachments, every attachment says what it is, and the
// flags are on the tests whose pages have what the flags look for and on none of the others.
//   node check-report.mjs [--expect-no-tree] [test-results/report.json [test-results/announcement-emulator/run.json]]
// --expect-no-tree is for a platform where Chrome gives the extension no desktop tree (macOS, Q7): the tests are still held to carrying the two labelled attachments, and the run summary is held to saying what the write-up says:
// nothing was read (no snapshot, no desktop tree) and so nothing was predicted or flagged. If such a platform starts to give a tree, this fails, and the write-up is out of date.
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const expectNoTree = args.includes("--expect-no-tree");
const [reportPath, runPath] = args.filter((a) => !a.startsWith("--"));
const report = JSON.parse(readFileSync(reportPath ?? "test-results/report.json", "utf8"));
const EXPECTED = {
  "the toolbar buttons can be reached by keyboard": ["focus-without-name"],
  "the cookie panel opens": ["silent-dialog"],
  "an empty email is refused": ["unheard-error"],
  "an empty email is refused and the field is focused": ["unheard-error"],
};
const tests = [];
(function walk(suite) { for (const s of suite.suites ?? []) walk(s); for (const spec of suite.specs ?? []) for (const t of spec.tests) tests.push({ title: spec.title, results: t.results }); })({ suites: report.suites });

// A test that began before the extension of its worker's browser was up is not held to what it should have heard: it did what it did before anything was listening (run.json says when that was).
let workers = [];
try { workers = JSON.parse(readFileSync(runPath ?? "test-results/announcement-emulator/run.json", "utf8")).workers; } catch { /* no run summary: every test is held to it */ }
const startup = workers.map((w) => w.startup);
const firstStart = {};
for (const { results } of tests) { const r = results.at(-1); firstStart[r.parallelIndex] = Math.min(firstStart[r.parallelIndex] ?? Infinity, Date.parse(r.startTime)); }
const cold = (r) => { const up = startup[r.parallelIndex]?.extensionUpAfterFirstTestStartedMs; return typeof up === "number" && Date.parse(r.startTime) < firstStart[r.parallelIndex] + up; };
const skipped = [];

const problems = [];
let speech = 0, sweeps = 0, flags = 0;
for (const { title, results } of tests) {
  const result = results.at(-1);
  const byName = Object.fromEntries(result.attachments.map((a) => [a.name, a]));
  const text = byName["predicted NVDA speech"], json = byName["predicted-nvda-speech.json"];
  if (!text || !json) { problems.push(`${title}: no predicted-speech attachments`); continue; }
  const body = Buffer.from(text.body, "base64").toString();
  if (!/^PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE/.test(body)) problems.push(`${title}: the text does not say it is a prediction`);
  const data = JSON.parse(Buffer.from(json.body, "base64").toString());
  if (!/^predicted NVDA speech: advisory, not a reading of NVDA, never evidence/.test(data.label)) problems.push(`${title}: the json does not say it is a prediction`);
  for (const banned of ["transcript", "structure", "interaction", "focusOrder"]) if (JSON.stringify(data).includes(`"${banned}"`)) problems.push(`${title}: a field is named ${banned}`);
  speech += data.predictedSpeech.length; sweeps += data.sweeps.length; flags += data.flags.length;
  if (expectNoTree) { if (data.flags.length || data.predictedSpeech.length || data.sweeps.length) problems.push(`${title}: something was predicted, flagged or swept where the write-up says no tree is read`); continue; }
  if (cold(result)) { skipped.push(title); continue; }
  const got = data.flags.map((f) => f.flag).sort(), want = (EXPECTED[title] ?? []).slice().sort();
  if (JSON.stringify(got) !== JSON.stringify(want)) problems.push(`${title}: flags ${JSON.stringify(got)}, wanted ${JSON.stringify(want)}`);
  if (!data.predictedSpeech.some((s) => s.cause === "load")) problems.push(`${title}: no page load was predicted`);
  if (!data.sweeps.length) problems.push(`${title}: no sweep`);
}
if (expectNoTree) {
  if (!workers.length) problems.push("no run summary: cannot say whether a tree was read");
  workers.forEach((w, i) => { if (w.snapshots || w.startup?.desktopChildrenWhenUp) problems.push(`worker ${i}: read ${w.snapshots} snapshots (desktop children ${w.startup?.desktopChildrenWhenUp}), but the write-up says this platform gives no tree`); });
}
console.log(`${tests.length} tests, ${speech} predicted utterances, ${sweeps} sweeps, ${flags} flags` + (expectNoTree ? "; no tree was read, as the write-up says of this platform" : "") + (skipped.length ? `; not held to what they should have heard, because they began before the browser's extension was up: ${skipped.join("; ")}` : ""));
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
