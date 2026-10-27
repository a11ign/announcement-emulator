import { test } from "node:test";
import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { doctor } from "./doctor.ts";
import type { PlaywrightChromium } from "./playwright-chromium.ts";
import type { SupportedVersions } from "./supported.ts";

/** A bundle that `findBundle` finds and whose Python starts. */
function bundle(): string {
  const dir = mkdtempSync(join(tmpdir(), "ae-doctor-"));
  mkdirSync(join(dir, "python", "bin"), { recursive: true });
  writeFileSync(join(dir, "python", "bin", "python3"), "#!/bin/sh\necho 3.13.16\n");
  chmodSync(join(dir, "python", "bin", "python3"), 0o755);
  writeFileSync(join(dir, "bundle.json"), JSON.stringify({ name: "b", platform: "linux-x64", nvda: { release: "release-2026.1.1", commit: "5d92106f" }, chromiumTables: "155.0.8059.84", python: "3.13.16", commit: "abc" }));
  return dir;
}

const pw = (over: Partial<PlaywrightChromium> = {}): PlaywrightChromium => ({
  version: "1.63.0", chromium: { revision: "1243", build: "153.0.8010.12" }, headlessShell: { revision: "1243", build: "153.0.8010.12" }, executablePath: "/x/chromium-1243/chrome", fullInstalled: true, shellInstalled: true, ...over,
});
const listed: SupportedVersions = { builds: [{ chromium: "153.0.8010.12", playwright: ["1.63.0"], measured: { "devtools-linux": { agreement: 0.85, units: 1100, date: "2026-10-26", figure: "middleware/results/playwright-versions/153.0.8010.12/devtools-linux/" } } }] };

function run(over: Parameters<typeof doctor>[0] = {}) {
  const lines: string[] = [];
  const code = doctor({ env: { ANNOUNCEMENT_EMULATOR_BUNDLE: bundle() }, playwright: pw(), supported: { builds: [] }, version: () => ({ status: 0, out: "Chromium 153.0.8010.12" }), log: (l) => lines.push(l), ...over });
  return { code, text: lines.join("\n") };
}

test("doctor prints the team's Playwright and Chromium, which of the browser and the headless shell are installed, and that a listed build is on the list with its figures", () => {
  const { code, text } = run({ supported: listed });
  assert.equal(code, 0);
  assert.match(text, /^Playwright 1\.63\.0$/m);
  assert.match(text, /^Chromium 153\.0\.8010\.12 \(revision 1243\): installed$/m);
  assert.match(text, /^headless shell 153\.0\.8010\.12: installed$/m);
  assert.match(text, /^supported: yes, Chromium 153\.0\.8010\.12 is on the list \(Playwright 1\.63\.0\)$/m);
  assert.match(text, /^ {2}devtools-linux: 85\.0% of 1100 units, 2026-10-26 \(middleware\/results\/playwright-versions\/153\.0\.8010\.12\/devtools-linux\/\)$/m);
  assert.match(text, /^ {2}devtools-macos: not measured$/m);
  assert.doesNotMatch(text, /extension/);
});

test("a build that is not on the list is not a failure: doctor says its agreement is not measured and exits 0", () => {
  const { code, text } = run();
  assert.equal(code, 0);
  assert.match(text, /supported: no\. Chromium 153\.0\.8010\.12 is not on the list, so a report says "agreement not measured for Chromium 153\.0\.8010\.12"\. It runs all the same\./);
});

test("with the headless shell only, doctor says which is missing and still exits 0: the tree comes through the DevTools port, which the headless shell serves", () => {
  const { code, text } = run({ playwright: pw({ fullInstalled: false }) });
  assert.equal(code, 0);
  assert.match(text, /^Chromium 153\.0\.8010\.12 \(revision 1243\): NOT installed$/m);
  assert.match(text, /^headless shell 153\.0\.8010\.12: installed$/m);
  assert.match(text, /^tree source: the DevTools port, on every platform and in whichever browser a launch gives$/m);
});

test("with no Chromium at all doctor fails and says the command that fixes it", () => {
  const { code, text } = run({ playwright: pw({ fullInstalled: false, shellInstalled: false }) });
  assert.equal(code, 1);
  assert.match(text, /^FAIL Chromium: neither the browser nor the headless shell is installed\. Run: npx playwright install chromium$/m);
});

test("with no Playwright doctor fails and says how to install it", () => {
  const { code, text } = run({ playwright: null });
  assert.equal(code, 1);
  assert.match(text, /FAIL Playwright: .*npm i -D @playwright\/test/);
});

test("doctor says the tree comes through the DevTools port, and names no other source", () => {
  const { text } = run();
  assert.match(text, /^tree source: the DevTools port, on every platform and in whichever browser a launch gives$/m);
  assert.doesNotMatch(text, /extension|automatic pick|lower fidelity/i);
});

test("doctor no longer runs a browser of the bundle's: it checks the bundle's Python and names the Chromium its tables came from", () => {
  const { text } = run();
  assert.match(text, /Chromium 155\.0\.8059\.84 mapping tables/);
  assert.match(text, /^ok {3}python: 3\.13\.16$/m);
  assert.doesNotMatch(text, /chrome --version|ok {3}chrome/);
});

test("a supported-versions list that is broken fails doctor and says the package is to be reinstalled", () => {
  const broken = run({ supported: undefined, supportedUrl: new URL("file:///no/such/list.json") });
  assert.equal(broken.code, 1);
  assert.match(broken.text, /^FAIL the package's supported-versions\.json could not be read: .*Reinstall the package$/m);
  const sound = run({ supported: undefined });
  assert.equal(sound.code, 0, "the list the package ships is sound");
  assert.doesNotMatch(sound.text, /supported-versions\.json/);
});

test("without a bundle doctor fails and says what to run, after saying what it knows of Playwright", () => {
  const { code, text } = run({ env: { ANNOUNCEMENT_EMULATOR_BUNDLE: join(tmpdir(), "no-such-bundle") } });
  assert.equal(code, 1);
  assert.match(text, /^Playwright 1\.63\.0$/m);
  assert.match(text, /npx announcement-emulator install/);
});

test("doctor starts the browser Playwright installed, and fails with the command that installs its libraries when it does not start", () => {
  assert.match(run().text, /^ok {3}chromium starts: Chromium 153\.0\.8010\.12$/m);
  const broken = run({ version: () => ({ status: 127, out: "error while loading shared libraries: libnss3.so" }) });
  assert.equal(broken.code, 1);
  assert.match(broken.text, /^FAIL chromium does not start: error while loading shared libraries: libnss3\.so\. On Linux, npx playwright install --with-deps chromium/m);
});

test("doctor does not start a browser that is not installed", () => {
  let started = 0;
  run({ playwright: pw({ fullInstalled: false }), version: () => { started += 1; return { status: 0, out: "" }; } });
  assert.equal(started, 0);
});
