// Reads the JSON report of a run of this suite and checks what the middleware put in it (A11-208's acceptance): every test has the two attachments, every attachment says what it is, and the
// flags are on the tests whose pages have what the flags look for and on none of the others.
//   node check-report.mjs [test-results/report.json]
import { readFileSync } from "node:fs";

const report = JSON.parse(readFileSync(process.argv[2] ?? "test-results/report.json", "utf8"));
const EXPECTED = {
  "the toolbar buttons can be reached by keyboard": ["focus-without-name"],
  "the cookie panel opens": ["silent-dialog"],
  "an empty email is refused": ["unheard-error"],
  "an empty email is refused and the field is focused": ["unheard-error"],
};
const tests = [];
(function walk(suite) { for (const s of suite.suites ?? []) walk(s); for (const spec of suite.specs ?? []) for (const t of spec.tests) tests.push({ title: spec.title, results: t.results }); })({ suites: report.suites });

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
  const got = data.flags.map((f) => f.flag).sort(), want = (EXPECTED[title] ?? []).slice().sort();
  if (JSON.stringify(got) !== JSON.stringify(want)) problems.push(`${title}: flags ${JSON.stringify(got)}, wanted ${JSON.stringify(want)}`);
  if (!data.predictedSpeech.some((s) => s.cause === "load")) problems.push(`${title}: no page load was predicted`);
  if (!data.sweeps.length) problems.push(`${title}: no sweep`);
}
console.log(`${tests.length} tests, ${speech} predicted utterances, ${sweeps} sweeps, ${flags} flags`);
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
