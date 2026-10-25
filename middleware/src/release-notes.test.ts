import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { ADVISORY, edgeVersions, pinValue, readNotesInput, renderNotes, SECTION, withNotes, type NotesInput } from "./release-notes.ts";
import type { Figure, SupportedVersions } from "./supported.ts";

const REPOSITORY = fileURLToPath(new URL("../..", import.meta.url));
const RELEASE_NOTES = fileURLToPath(new URL("./release-notes.ts", import.meta.url));

const figure = (agreement: number, units: number, key: string, more: Partial<Figure> = {}): Figure =>
  ({ agreement, units, date: "2026-10-26", figure: `middleware/results/round/156.0.8078.4/${key}/`, ...more });

const LIST: SupportedVersions = { builds: [
  { chromium: "156.0.8078.4", playwright: ["1.64.0", "1.64.1"], measured: {
    "extension-linux": figure(0.912, 1131, "extension-linux", {
      population: { pages: 12, heldOut: true, units: 1131 }, ceiling: { agreement: 0.995, units: 1131 },
      shapes: { "NAME + ROLE": { agreement: 0.95, units: 600, lowConfidence: false }, NAME: { agreement: 0.5, units: 40, lowConfidence: true } },
    }),
    "devtools-macos": figure(0.804, 960, "devtools-macos"),
  } },
  { chromium: "153.0.8010.12", playwright: ["1.63.0"], measured: { "devtools-linux": figure(0.85, 1100, "devtools-linux") } },
] };
const EDGE: Record<string, string[]> = { "middleware/results/round/156.0.8078.4/extension-linux/": ["156.0.4314.42"] };
const input = (list = LIST, edge = EDGE): NotesInput => ({ list, nvda: "release-2026.1.1", edgeOf: (f) => edge[f] ?? [] });

test("the notes name every supported Playwright version, with the Chromium build each ships", () => {
  const notes = renderNotes(input());
  assert.match(notes, /^- Playwright 1\.64\.0, 1\.64\.1: Chromium 156\.0\.8078\.4$/m);
  assert.match(notes, /^- Playwright 1\.63\.0: Chromium 153\.0\.8010\.12$/m);
});

test("every build's rate is given for each tree source, with its units and its date", () => {
  const notes = renderNotes(input());
  assert.match(notes, /^\| 156\.0\.8078\.4 \| 1\.64\.0, 1\.64\.1 \| extension-linux \| 91\.2% \| 1131 \| 2026-10-26 \|/m);
  assert.match(notes, /^\| 156\.0\.8078\.4 \| 1\.64\.0, 1\.64\.1 \| devtools-macos \| 80\.4% \| 960 \| 2026-10-26 \|/m);
  assert.match(notes, /^\| 153\.0\.8010\.12 \| 1\.63\.0 \| devtools-linux \| 85\.0% \| 1100 \| 2026-10-26 \|/m);
});

test("a figure's population and ceiling are given where it has them, and its shapes are a table of the rate per announcement type", () => {
  const notes = renderNotes(input());
  assert.match(notes, /\| extension-linux \| 91\.2% \| 1131 \| 2026-10-26 \| 12, held out \| 99\.5% \|/);
  assert.match(notes, /\| devtools-macos \| 80\.4% \| 960 \| 2026-10-26 \| not given \| not given \|/);
  assert.match(notes, /^##### Chromium 156\.0\.8078\.4, extension-linux, by announcement shape$/m);
  assert.match(notes, /^\| NAME \+ ROLE \| 95\.0% \| 600 \| {2}\|$/m);
  assert.match(notes, /^\| NAME \| 50\.0% \| 40 \| low confidence \|$/m);
  assert.equal(notes.match(/by announcement shape/g)?.length, 1);      // a figure with no shapes has no table
});

test("the Edge version is the one the fleet readings recorded, and 'not recorded' where they record none", () => {
  const notes = renderNotes(input());
  assert.match(notes, /\| extension-linux \|[^\n]*\| 99\.5% \| 156\.0\.4314\.42 \|$/m);
  assert.match(notes, /\| devtools-macos \|[^\n]*\| not recorded \|$/m);
  assert.match(notes, /\| devtools-linux \|[^\n]*\| not recorded \|$/m);
  assert.doesNotMatch(renderNotes(input(LIST, {})), /156\.0\.4314\.42/);
});

test("the notes name the NVDA release, say Windows is not measured, and say the speech is a prediction, advisory and never evidence", () => {
  const notes = renderNotes(input());
  assert.match(notes, /NVDA release: release-2026\.1\.1/);
  assert.match(notes, /^Windows: not measured\./m);
  assert.ok(notes.includes(ADVISORY));
  assert.match(ADVISORY, /prediction.*advisory.*never evidence/);
  assert.ok(notes.startsWith(`${SECTION}\n`));
});

test("the notes never say the speech is NVDA's, that NV Access endorses it, or that it is compatible", () => {
  const notes = renderNotes(input());
  assert.doesNotMatch(notes, /NVDA[- ]compatible|compatible with NVDA|\bis NVDA\b|endorse|affiliat|official|logo/i);
});

test("a list with no build, or a figure part this file does not know, is handled: the first fails the release, the second is left out", () => {
  assert.throws(() => renderNotes(input({ builds: [] })), /names no Chromium build/);
  const extra = { ...figure(0.9, 10, "extension-linux"), somethingNew: { a: 1 } } as Figure;
  const notes = renderNotes(input({ builds: [{ chromium: "156.0.8078.4", playwright: ["1.64.1"], measured: { "extension-linux": extra } }] }));
  assert.match(notes, /\| extension-linux \| 90\.0% \| 10 \|/);
  assert.doesNotMatch(notes, /somethingNew/);
});

const CHANGELOG = "# pkg\n\n## 0.2.0\n\n### Minor Changes\n\n- b: second\n\n## 0.1.0\n\n### Minor Changes\n\n- a: first\n";

test("the section ends the entry of its own version and no other, and a second run replaces it", () => {
  const once = withNotes(CHANGELOG, "0.2.0", `${SECTION}\n\nfirst\n`);
  assert.equal(once, "# pkg\n\n## 0.2.0\n\n### Minor Changes\n\n- b: second\n\n### Measured agreement\n\nfirst\n\n## 0.1.0\n\n### Minor Changes\n\n- a: first\n");
  assert.equal(withNotes(once, "0.2.0", `${SECTION}\n\nsecond\n`).split(SECTION).length, 2);
  assert.match(withNotes(once, "0.2.0", `${SECTION}\n\nsecond\n`), /### Measured agreement\n\nsecond\n\n## 0\.1\.0/);
  assert.match(withNotes(CHANGELOG, "0.1.0", `${SECTION}\n\nlast\n`), /- a: first\n\n### Measured agreement\n\nlast\n$/);
  assert.throws(() => withNotes(CHANGELOG, "0.3.0", SECTION), /no entry for 0\.3\.0/);
});

test("pins.env's NVDA release is read, and a name it lacks is an error", () => {
  assert.equal(pinValue("A=1\nNVDA_TAG=release-2026.1.1\nNVDA_REV=5d92  # tag\n", "NVDA_TAG"), "release-2026.1.1");
  assert.throws(() => pinValue("A=1\n", "NVDA_TAG"), /no NVDA_TAG/);
});

test("this repository's own list renders: every Playwright version it lists is in the notes, with the Edge version its fleet readings recorded", () => {
  const { list, nvda, edgeOf } = readNotesInput(REPOSITORY);
  const notes = renderNotes({ list, nvda, edgeOf });
  assert.ok(list.builds.length > 0);
  for (const build of list.builds) {
    for (const version of build.playwright) assert.ok(notes.includes(version), version);
    assert.ok(notes.includes(build.chromium), build.chromium);
  }
  for (const f of list.builds.flatMap((b) => Object.values(b.measured))) for (const edge of edgeOf(f.figure)) assert.ok(notes.includes(edge), `${f.figure}: ${edge}`);
  assert.ok(notes.includes("156.0.4314.42"), "the fleet's Edge, as middleware/results/playwright-versions/fleet-readings.json records it");
  assert.ok(notes.includes(`NVDA release: ${nvda}`));
});

test("the Edge version is searched above the figure only, and a directory with no readings gives none", () => {
  const root = mkdtempSync(join(tmpdir(), "ae-notes-"));
  mkdirSync(join(root, "middleware", "results", "r", "b", "s"), { recursive: true });
  assert.deepEqual(edgeVersions(root, "middleware/results/r/b/s/"), []);
  writeFileSync(join(root, "middleware", "results", "r", "fleet-readings.json"), JSON.stringify([{ environment: { browserVersion: "1.2.3.4" } }, { environment: { browserVersion: "1.2.3.4" } }, { environment: { browserVersion: null } }, {}]));
  assert.deepEqual(edgeVersions(root, "middleware/results/r/b/s/"), ["1.2.3.4"]);
});

test("run as a command it appends the section to the entry of the version, in a copy of the repository's list", () => {
  const root = mkdtempSync(join(tmpdir(), "ae-notes-cli-"));
  mkdirSync(join(root, "middleware"), { recursive: true });
  cpSync(join(REPOSITORY, "pins.env"), join(root, "pins.env"));
  cpSync(join(REPOSITORY, "middleware", "supported-versions.json"), join(root, "middleware", "supported-versions.json"));
  mkdirSync(join(root, "middleware", "results", "playwright-versions"), { recursive: true });
  cpSync(join(REPOSITORY, "middleware", "results", "playwright-versions", "fleet-readings.json"), join(root, "middleware", "results", "playwright-versions", "fleet-readings.json"));
  writeFileSync(join(root, "middleware", "CHANGELOG.md"), CHANGELOG);
  execFileSync(process.execPath, [RELEASE_NOTES, "0.2.0", "--root", root], { stdio: "pipe" });
  const changelog = readFileSync(join(root, "middleware", "CHANGELOG.md"), "utf8");
  assert.match(changelog, /- b: second\n\n### Measured agreement\n\n/);
  assert.match(changelog, /\n## 0\.1\.0\n/);
  assert.ok(changelog.includes("Playwright 1.64.0, 1.64.1"));
});
