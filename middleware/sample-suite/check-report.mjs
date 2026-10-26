// Reads the JSON report of a run of this suite and checks what the middleware put in it (A11-208's acceptance): every test has the two attachments, every attachment says what it is, and the
// flags are on the tests whose pages have what the flags look for and on none of the others.
//   node check-report.mjs [--expect-no-tree | --lower-fidelity] [--expect-unmeasured <build> | --expect-measured <build>] [--expect-shape-rates] [test-results/report.json [test-results/announcement-emulator/run.json]]
// --expect-no-tree is for a platform where Chrome gives the extension no desktop tree (macOS, Q7): the tests are still held to carrying the two labelled attachments, and the run summary is held to saying what the write-up says:
// nothing was read (no snapshot, no desktop tree) and so nothing was predicted or flagged. If such a platform starts to give a tree, this fails, and the write-up is out of date.
// --expect-unmeasured <build> holds every test, and the run summary of every worker, to the Chromium <build> the team's Playwright installed and to the sentence "agreement not measured for Chromium <build>": the build
// is not on the supported list (A11-230). --expect-measured <build> holds them to the sentence of a listed build, "agreement measured for Chromium <build> (Playwright ...), <source>: <rate>% of <units> units[ on <pages> held-out pages], <date>[; the fleet
// agrees with itself on <ceiling>%] (<figure>)": the part in brackets is there when the figure says what it was measured on and what the oracle's own noise puts as the ceiling (A11-234).
// --expect-shape-rates holds every predicted utterance to what the figure says of its shape (A11-234): where the build's figure has the rates of shapes, each utterance carries its shape's rate in the json (`shapeRate`) and in the text
// (`[NAME + ROLE: 86.0% of 57]`, `, low confidence` where the figure marks the shape weak, or `[shape not measured]`); where it has none (a build that is not measured, or a figure from before shapes), no utterance carries one.
// Any other option is refused (exit 2), so that a misspelt one cannot turn a check off.
// --lower-fidelity is for a run whose tree came through the DevTools port (macOS, and the same on Linux for comparison): the tests are held to carrying the two labelled attachments, to saying where their tree came
// from, and, over the suite, to a page load predicted for most tests, a sweep and at least one of the flags. Which flags are raised for a quick test depends on how soon the browser's answer comes: one may
// be missing, and one the extension's run does not raise may appear (counted and printed, not a failure).
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const valueOf = (flag) => { const at = args.indexOf(flag); return at < 0 ? null : args.splice(at, 2)[1]; };
const unmeasured = valueOf("--expect-unmeasured"), measured = valueOf("--expect-measured");
const expectNoTree = args.includes("--expect-no-tree"), lowerFidelity = args.includes("--lower-fidelity"), expectShapeRates = args.includes("--expect-shape-rates");
const KNOWN = ["--expect-no-tree", "--lower-fidelity", "--expect-shape-rates"];
const unknown = args.filter((a) => a.startsWith("--") && !KNOWN.includes(a));
if (unknown.length) { console.error(`unknown option ${unknown.join(", ")}; known: ${KNOWN.join(", ")}, --expect-unmeasured <build>, --expect-measured <build>`); process.exit(2); }
const [reportPath, runPath] = args.filter((a) => !a.startsWith("--"));
const expectedBuild = unmeasured ?? measured;
const report = JSON.parse(readFileSync(reportPath ?? "test-results/report.json", "utf8"));
const EXPECTED = {
  "the toolbar buttons can be reached by keyboard": ["focus-without-name"],
  "the cookie panel opens": ["silent-dialog"],
  "an empty email is refused": ["unheard-error"],
  "an empty email is refused and the field is focused": ["unheard-error"],
};
// A flag a test may or may not raise, by what the tree read after the focus move had in it (A11-234): the field that takes the focus has its error message in the tree if the page had shown it by the time the tree was read,
// and then the words are in the speech and the flag is rightly not raised (NVDA says an invalid field's error message). Which tree is read depends on how quickly the browser answered.
const MAY_BE_ABSENT = { "an empty email is refused and the field is focused": ["unheard-error"] };
// What a test must have heard, whatever its tree source: a part of each wording its pages predict. A test of two contexts has the speech of both (the fixture's page and the one the test opened itself).
const HEARD = { "a context the suite opens itself is announced like the page the fixture gives it": ["Full name", "Add a mug"] };
// Tests that raise no flag and are not held to the flags: the contexts project's. Any other test is, so renaming one cannot silently stop the flag check.
const FLAGLESS = new Set([...Object.keys(HEARD), "a page open while the browser comes up"]);
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
let speech = 0, sweeps = 0, flags = 0, loads = 0, expectedFlags = 0, rated = 0, weak = 0;
const extra = [];      // flags the extension's run does not raise: a test quicker than the read of a tree loses its last events, and a flag made of what is missing is false. Counted and shown; not a failure.
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
  if (expectedBuild) {
    const line = data.agreement?.line ?? "";
    const wanted = unmeasured ? `agreement not measured for Chromium ${unmeasured}` : null;
    if (wanted && line !== wanted) problems.push(`${title}: the agreement line is "${line}", wanted "${wanted}"`);
    if (measured && !line.startsWith(`agreement measured for Chromium ${measured} (Playwright `)) problems.push(`${title}: the agreement line is "${line}", wanted a measured one for Chromium ${measured}`);
    if (!body.split("\n").includes(line)) problems.push(`${title}: the text does not carry the agreement line`);
  }
  if (expectShapeRates) {
    const byShape = data.agreement?.measured && data.agreement.shapes;
    for (const u of data.predictedSpeech) {
      if (!byShape) { if (u.shapeRate || u.lowConfidence) problems.push(`${title}: "${u.text}" carries a rate by shape, and the build's figure has none`); continue; }
      const r = u.shapeRate;
      if (!r) { problems.push(`${title}: "${u.text}" carries no rate for its shape`); continue; }
      const note = r.measured ? `${r.shape}: ${(r.agreement * 100).toFixed(1)}% of ${r.units}${r.lowConfidence ? ", low confidence" : ""}` : "shape not measured";
      if (!body.includes(`[${note}]`)) problems.push(`${title}: the text does not carry "[${note}]"`);
      if (Boolean(u.lowConfidence) !== Boolean(r.lowConfidence)) problems.push(`${title}: "${u.text}" is ${r.lowConfidence ? "" : "not "}low confidence in its rate, and ${u.lowConfidence ? "" : "not "}flagged`);
      rated += 1; if (r.lowConfidence) weak += 1;
    }
  }
  const said = data.predictedSpeech.map((s) => s.text).join(" | ").toLowerCase();
  for (const part of expectNoTree ? [] : HEARD[title] ?? []) if (!said.includes(part.toLowerCase()) && !cold(results.at(-1))) problems.push(`${title}: nothing predicted contains "${part}"`);
  speech += data.predictedSpeech.length; sweeps += data.sweeps.length; flags += data.flags.length;
  if (expectNoTree) { if (data.flags.length || data.predictedSpeech.length || data.sweeps.length) problems.push(`${title}: something was predicted, flagged or swept where the write-up says no tree is read`); continue; }
  if (lowerFidelity) {
    if (data.treeSource !== "devtools") problems.push(`${title}: the output does not say its tree came through the DevTools port (${data.treeSource})`);
    if (!/lower fidelity/.test(body)) problems.push(`${title}: the text does not say the tree is of lower fidelity`);
    const want = EXPECTED[title] ?? [], got = data.flags.map((f) => f.flag);
    for (const f of got) if (want.includes(f)) expectedFlags += 1; else extra.push(`${title}: ${f}`);
    if (data.predictedSpeech.some((s) => s.cause === "load")) loads += 1;
    continue;
  }
  if (cold(result)) { skipped.push(title); continue; }
  const got = data.flags.map((f) => f.flag).sort(), want = (EXPECTED[title] ?? []).slice().sort(), optional = MAY_BE_ABSENT[title] ?? [];
  if (JSON.stringify(got) !== JSON.stringify(want) && JSON.stringify(got) !== JSON.stringify(want.filter((f) => !optional.includes(f)))) problems.push(`${title}: flags ${JSON.stringify(got)}, wanted ${JSON.stringify(want)}`);
  if (!data.predictedSpeech.some((s) => s.cause === "load")) problems.push(`${title}: no page load was predicted`);
  if (!data.sweeps.length) problems.push(`${title}: no sweep`);
}
if (lowerFidelity) {
  if (loads < Math.ceil(tests.length * 0.6)) problems.push(`a page load was predicted for ${loads} of ${tests.length} tests: fewer than three in five`);
  if (tests.some((t) => !FLAGLESS.has(t.title)) && !expectedFlags) problems.push("none of the flags the sample suite is built to raise was raised");
  if (!sweeps) problems.push("no sweep was made");
}
if (expectedBuild) {
  if (!workers.length) problems.push("no run summary: cannot say which Chromium the workers ran in");
  workers.forEach((w, i) => { if (w.startup?.chromium !== expectedBuild) problems.push(`worker ${i}: ran in Chromium ${w.startup?.chromium}, wanted ${expectedBuild}`); });
}
if (expectNoTree) {
  if (!workers.length) problems.push("no run summary: cannot say whether a tree was read");
  workers.forEach((w, i) => { if (w.snapshots || w.startup?.desktopChildrenWhenUp) problems.push(`worker ${i}: read ${w.snapshots} snapshots (desktop children ${w.startup?.desktopChildrenWhenUp}), but the write-up says this platform gives no tree`); });
}
console.log(`${tests.length} tests, ${speech} predicted utterances, ${sweeps} sweeps, ${flags} flags` + (expectNoTree ? "; no tree was read, as the write-up says of this platform" : "") + (lowerFidelity ? `; a page load for ${loads} of ${tests.length} tests, tree through the DevTools port` + (extra.length ? `; ${extra.length} flag(s) the extension's run does not raise: ${extra.join("; ")}` : "") : "") + (expectedBuild ? `; Chromium ${expectedBuild}, agreement ${unmeasured ? "not measured" : "measured"}` : "") + (expectShapeRates ? `; a rate by shape on ${rated} utterances (${weak} low confidence)` : "") + (skipped.length ? `; not held to what they should have heard, because they began before the browser's extension was up: ${skipped.join("; ")}` : ""));
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
