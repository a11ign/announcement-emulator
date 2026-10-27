// Reads the JSON report of a run of this suite and checks what the middleware put in it (A11-208's acceptance): every test has the two attachments, every attachment says what it is, and the
// flags are on the tests whose pages have what the flags look for and on none of the others.
//   node check-report.mjs [--expect-unmeasured <build> | --expect-measured <build>] [--expect-shape-rates] [test-results/report.json [test-results/announcement-emulator/run.json]]
// The tree is the DevTools port's on every platform (A11-229: there is no other source), so every test is held to saying so (`treeSource: "devtools"`), and the suite to a page load predicted for most tests, a sweep and
// at least one of the flags it is built to raise. Which flags are raised for a quick test depends on how soon the browser's answer comes: one may be missing, and one a test is not built to raise may appear (counted and
// printed, not a failure). A run that read nothing predicts no page load, and fails.
// --expect-unmeasured <build> holds every test, and the run summary of every worker, to the Chromium <build> the team's Playwright installed and to the sentence "agreement not measured for Chromium <build>": the build
// is not on the supported list (A11-230). --expect-measured <build> holds them to the sentence of a listed build, "agreement measured for Chromium <build> (Playwright ...), devtools: <rate>% of <units> units[ on <pages> held-out pages], <date>[; the fleet
// agrees with itself on <ceiling>%] (<figure>)": the part in brackets is there when the figure says what it was measured on and what the oracle's own noise puts as the ceiling (A11-234).
// --expect-shape-rates holds every predicted utterance to what the figure says of its shape (A11-234): where the build's figure has the rates of shapes, each utterance carries its shape's rate in the json (`shapeRate`) and in the text
// (`[NAME + ROLE: 86.0% of 57]`, `, low confidence` where the figure marks the shape weak, or `[shape not measured]`); where it has none (a build that is not measured, or a figure from before shapes), no utterance carries one.
// Any other option is refused (exit 2), so that a misspelt one cannot turn a check off, and neither can one that went with the extension (`--expect-no-tree`, `--lower-fidelity`).
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const valueOf = (flag) => {
  const at = args.indexOf(flag);
  if (at < 0) return null;
  const [, value] = args.splice(at, 2);
  if (value === undefined || value.startsWith("--")) { console.error(`${flag} needs a value`); process.exit(2); }      // an empty ${{ matrix.chromium }} must not turn the build check off
  return value;
};
const unmeasured = valueOf("--expect-unmeasured"), measured = valueOf("--expect-measured");
const expectShapeRates = args.includes("--expect-shape-rates");
const KNOWN = ["--expect-shape-rates"];
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
// What a test must have heard: a part of each wording its pages predict. A test of two contexts has the speech of both (the fixture's page and the one the test opened itself).
const HEARD = { "a context the suite opens itself is announced like the page the fixture gives it": ["Full name", "Add a mug"] };
// Tests that raise no flag and are not held to the flags: the contexts project's. Any other test is, so renaming one cannot silently stop the flag check.
const FLAGLESS = new Set([...Object.keys(HEARD), "a page open while the browser comes up"]);
const tests = [];
(function walk(suite) { for (const s of suite.suites ?? []) walk(s); for (const spec of suite.specs ?? []) for (const t of spec.tests) tests.push({ title: spec.title, results: t.results }); })({ suites: report.suites });

let workers = [];
try { workers = JSON.parse(readFileSync(runPath ?? "test-results/announcement-emulator/run.json", "utf8")).workers; } catch { /* no run summary: no worker is held to a build */ }

const problems = [];
let speech = 0, sweeps = 0, flags = 0, loads = 0, expectedFlags = 0, rated = 0, weak = 0;
const extra = [];      // flags a test is not built to raise: a test quicker than the read of a tree loses its last events, and a flag made of what is missing is false. Counted and shown; not a failure.
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
  for (const part of HEARD[title] ?? []) if (!said.includes(part.toLowerCase())) problems.push(`${title}: nothing predicted contains "${part}"`);
  speech += data.predictedSpeech.length; sweeps += data.sweeps.length; flags += data.flags.length;
  if (data.treeSource !== "devtools") problems.push(`${title}: the output does not say its tree came through the DevTools port (${data.treeSource})`);
  const want = EXPECTED[title] ?? [], got = data.flags.map((f) => f.flag);
  for (const f of got) if (want.includes(f)) expectedFlags += 1; else extra.push(`${title}: ${f}`);
  if (data.predictedSpeech.some((s) => s.cause === "load")) loads += 1;
}
if (loads < Math.ceil(tests.length * 0.6)) problems.push(`a page load was predicted for ${loads} of ${tests.length} tests: fewer than three in five`);
if (tests.some((t) => !FLAGLESS.has(t.title)) && !expectedFlags) problems.push("none of the flags the sample suite is built to raise was raised");
if (!sweeps) problems.push("no sweep was made");
if (expectedBuild) {
  if (!workers.length) problems.push("no run summary: cannot say which Chromium the workers ran in");
  workers.forEach((w, i) => { if (w.startup?.chromium !== expectedBuild) problems.push(`worker ${i}: ran in Chromium ${w.startup?.chromium}, wanted ${expectedBuild}`); });
}
console.log(`${tests.length} tests, ${speech} predicted utterances, ${sweeps} sweeps, ${flags} flags; a page load for ${loads} of ${tests.length} tests, tree through the DevTools port` + (extra.length ? `; ${extra.length} flag(s) the suite is not built to raise for that test: ${extra.join("; ")}` : "") + (expectedBuild ? `; Chromium ${expectedBuild}, agreement ${unmeasured ? "not measured" : "measured"}` : "") + (expectShapeRates ? `; a rate by shape on ${rated} utterances (${weak} low confidence)` : ""));
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
