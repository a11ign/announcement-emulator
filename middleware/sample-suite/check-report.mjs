// Reads the JSON report of a run of this suite and checks what the middleware put in it (A11-208's acceptance): every test has the two attachments, every attachment says what it is, and the
// flags are on the tests whose pages have what the flags look for and on none of the others.
//   node check-report.mjs [--expect-no-tree | --devtools-tree | --expect-fallback] [--expect-unmeasured <build> | --expect-measured <build>] [test-results/report.json [test-results/announcement-emulator/run.json]]
// --expect-no-tree is for a platform where Chrome gives the extension no desktop tree (macOS, Q7): the tests are still held to carrying the two labelled attachments, and the run summary is held to saying what the write-up says:
// nothing was read (no snapshot, no desktop tree) and so nothing was predicted or flagged. If such a platform starts to give a tree, this fails, and the write-up is out of date.
// --expect-unmeasured <build> holds every test, and the run summary of every worker, to the Chromium <build> the team's Playwright installed and to the sentence "agreement not measured for Chromium <build>": the build
// is not on the supported list (A11-230). --expect-measured <build> holds them to the sentence of a listed build, "agreement measured for Chromium <build> (Playwright ...), <source>: <rate>% of <units> units, <date>".
// --devtools-tree is for a run whose tree came through the DevTools port (macOS, and the same on Linux for comparison): the tests are held to carrying the two labelled attachments, to saying where their tree came
// from and why, and the rate that source was measured at, and, over the suite, to a page load predicted for most tests, a sweep and at least one of the flags.
// --expect-fallback is for a run that was left to pick, whose extension posted no tree (A11-229): every test says its tree came through the DevTools port because the extension posted none, and that the
// runtime switched; the run summary says when; and every test that began after the switch has its page load predicted. What ran before the switch is lost, and is not held to anything.
// A run that is not given one of these is held to the extension: every test says its tree is the extension's, and why. Which flags are raised for a quick test depends on how soon the browser's answer comes: one may
// be missing, and one the extension's run does not raise may appear (counted and printed, not a failure).
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const valueOf = (flag) => { const at = args.indexOf(flag); return at < 0 ? null : args.splice(at, 2)[1]; };
const unmeasured = valueOf("--expect-unmeasured"), measured = valueOf("--expect-measured");
const expectNoTree = args.includes("--expect-no-tree"), devtoolsTree = args.includes("--devtools-tree"), expectFallback = args.includes("--expect-fallback");
const [reportPath, runPath] = args.filter((a) => !a.startsWith("--"));
const expectedBuild = unmeasured ?? measured;
const report = JSON.parse(readFileSync(reportPath ?? "test-results/report.json", "utf8"));
const EXPECTED = {
  "the toolbar buttons can be reached by keyboard": ["focus-without-name"],
  "the cookie panel opens": ["silent-dialog"],
  "an empty email is refused": ["unheard-error"],
  "an empty email is refused and the field is focused": ["unheard-error"],
};
// What a test must have heard, whatever its tree source: a part of each wording the test's pages predict. A test of two contexts has the speech of both (the fixture's page and the one the test opened itself).
const HEARD = {
  "a context the suite opens itself is announced like the page the fixture gives it": ["Full name", "Add a mug"],
  "a page opened after the runtime switched to the DevTools port gets its predicted speech": ["Email address"],
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
// With a fallback: the tests that began after the runtime switched to the DevTools port, which are held to their page load.
const switched = (r) => { const at = startup[r.parallelIndex]?.fellBackAfterFirstTestStartedMs; return typeof at === "number" && Date.parse(r.startTime) >= firstStart[r.parallelIndex] + at; };
let afterSwitch = 0;

const problems = [];
let speech = 0, sweeps = 0, flags = 0, loads = 0, expectedFlags = 0;
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
  const said = data.predictedSpeech.map((s) => s.text).join(" | ").toLowerCase();
  for (const part of expectNoTree ? [] : HEARD[title] ?? []) if (!said.includes(part.toLowerCase()) && !cold(result) && !(expectFallback && !switched(result))) problems.push(`${title}: nothing predicted contains "${part}"`);
  speech += data.predictedSpeech.length; sweeps += data.sweeps.length; flags += data.flags.length;
  if (expectNoTree) { if (data.flags.length || data.predictedSpeech.length || data.sweeps.length) problems.push(`${title}: something was predicted, flagged or swept where the write-up says no tree is read`); continue; }
  const says = (source, why) => {
    if (data.treeSource !== source) problems.push(`${title}: the output says its tree came from ${data.treeSource}, wanted ${source}`);
    if (!data.treeSourceWhy) problems.push(`${title}: the output does not say why its tree came from there`);
    if (!body.split("\n").some((l) => l.startsWith(`tree: the ${source === "devtools" ? "DevTools port's" : "companion extension's"} accessibility tree (${data.treeSourceWhy})`))) problems.push(`${title}: the text does not say where its tree came from and why`);
    if (!/agreed with a real NVDA on|was not measured on/.test(data.treeSourceAgreement ?? "")) problems.push(`${title}: the output does not say how well its tree source was measured to agree`);
    if (why && !why.test(data.treeSourceWhy ?? "")) problems.push(`${title}: the reason is "${data.treeSourceWhy}", wanted one that matches ${why}`);
    if (/lower fidelity/.test(body)) problems.push(`${title}: the text still calls the tree lower fidelity`);
  };
  if (devtoolsTree) {
    says("devtools");
    const want = EXPECTED[title] ?? [], got = data.flags.map((f) => f.flag);
    for (const f of got) if (want.includes(f)) expectedFlags += 1; else extra.push(`${title}: ${f}`);
    if (data.predictedSpeech.some((s) => s.cause === "load")) loads += 1;
    continue;
  }
  if (expectFallback) {
    says("devtools", /posted no tree/);
    if (data.treeSourceFellBack !== true) problems.push(`${title}: the output does not record the fallback`);
    if (switched(result)) { afterSwitch += 1; if (!data.predictedSpeech.some((s) => s.cause === "load")) problems.push(`${title}: began after the switch to the DevTools port and no page load was predicted`); }
    if (data.predictedSpeech.some((s) => s.cause === "load")) loads += 1;
    continue;
  }
  says("extension");
  if (cold(result)) { skipped.push(title); continue; }
  const got = data.flags.map((f) => f.flag).sort(), want = (EXPECTED[title] ?? []).slice().sort();
  if (JSON.stringify(got) !== JSON.stringify(want)) problems.push(`${title}: flags ${JSON.stringify(got)}, wanted ${JSON.stringify(want)}`);
  if (!data.predictedSpeech.some((s) => s.cause === "load")) problems.push(`${title}: no page load was predicted`);
  if (!data.sweeps.length) problems.push(`${title}: no sweep`);
}
if (devtoolsTree) {
  if (loads < Math.ceil(tests.length * 0.6)) problems.push(`a page load was predicted for ${loads} of ${tests.length} tests: fewer than three in five`);
  if (tests.some((t) => EXPECTED[t.title]) && !expectedFlags) problems.push("none of the flags the sample suite is built to raise was raised");
  if (!sweeps) problems.push("no sweep was made");
}
if (expectFallback) {
  if (!workers.length) problems.push("no run summary: cannot say when the runtime switched");
  workers.forEach((w, i) => { if (typeof w.startup?.fellBackAfterFirstTestStartedMs !== "number") problems.push(`worker ${i}: the run summary does not say when the runtime switched to the DevTools port`); });
  if (!loads) problems.push("no page load was predicted in the whole run: the fallback gave no speech");
}
if (expectedBuild) {
  if (!workers.length) problems.push("no run summary: cannot say which Chromium the workers ran in");
  workers.forEach((w, i) => { if (w.startup?.chromium !== expectedBuild) problems.push(`worker ${i}: ran in Chromium ${w.startup?.chromium}, wanted ${expectedBuild}`); });
}
if (expectNoTree) {
  if (!workers.length) problems.push("no run summary: cannot say whether a tree was read");
  workers.forEach((w, i) => { if (w.snapshots || w.startup?.desktopChildrenWhenUp) problems.push(`worker ${i}: read ${w.snapshots} snapshots (desktop children ${w.startup?.desktopChildrenWhenUp}), but the write-up says this platform gives no tree`); });
}
console.log(`${tests.length} tests, ${speech} predicted utterances, ${sweeps} sweeps, ${flags} flags` + (expectNoTree ? "; no tree was read, as the write-up says of this platform" : "") + (devtoolsTree ? `; a page load for ${loads} of ${tests.length} tests, tree through the DevTools port` + (extra.length ? `; ${extra.length} flag(s) the extension's run does not raise: ${extra.join("; ")}` : "") : "") + (expectFallback ? `; the extension posted no tree and the runtime switched to the DevTools port (${afterSwitch} test(s) began after the switch, a page load for ${loads} of ${tests.length})` : "") + (expectedBuild ? `; Chromium ${expectedBuild}, agreement ${unmeasured ? "not measured" : "measured"}` : "") + (skipped.length ? `; not held to what they should have heard, because they began before the browser's extension was up: ${skipped.join("; ")}` : ""));
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
