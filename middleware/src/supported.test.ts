import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { agreementFor, buildFor, buildOfPlaywright, problemsIn, loadSupported, readSupported, sourceKey, withListError, type SupportedVersions } from "./supported.ts";

const figure = (agreement: number, units: number, key: string) => ({ agreement, units, date: "2026-10-26", figure: `middleware/results/playwright-versions/156.0.8078.4/${key}/` });
const list: SupportedVersions = { builds: [
  { chromium: "156.0.8078.4", playwright: ["1.64.0", "1.64.1"], measured: { "extension-linux": figure(0.912, 1131, "extension-linux"), "devtools-macos": figure(0.804, 1131, "devtools-macos") } },
  { chromium: "153.0.8010.12", playwright: ["1.63.0"], measured: { "devtools-linux": figure(0.85, 1100, "devtools-linux") } },
] };

test("a listed build with a figure for the source says its rate, the units, the date and where the figure is", () => {
  const a = agreementFor(list, "156.0.8078.4", "extension", "linux");
  assert.equal(a.line, "agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.0, 1.64.1), extension: 91.2% of 1131 units, 2026-10-26 (middleware/results/playwright-versions/156.0.8078.4/extension-linux/)");
  assert.deepEqual([a.measured, a.agreement, a.units, a.playwright], [true, 0.912, 1131, ["1.64.0", "1.64.1"]]);
});

test("the figure is the one of the source and the platform the run used", () => {
  assert.match(agreementFor(list, "156.0.8078.4", "devtools", "darwin").line, /, devtools: 80\.4% of 1131 units/);
  assert.match(agreementFor(list, "153.0.8010.12", "devtools", "linux").line, /Chromium 153\.0\.8010\.12 \(Playwright 1\.63\.0\), devtools: 85\.0% of 1100 units/);
});

test("a build that is not listed says exactly that its agreement is not measured, and the run goes on", () => {
  const a = agreementFor(list, "152.0.7999.1", "extension", "linux");
  assert.equal(a.line, "agreement not measured for Chromium 152.0.7999.1");
  assert.equal(a.measured, false);
});

test("a listed build with no figure for this source and platform reads the same way", () => {
  assert.equal(agreementFor(list, "153.0.8010.12", "extension", "linux").line, "agreement not measured for Chromium 153.0.8010.12");
  assert.equal(agreementFor(list, "156.0.8078.4", "devtools", "win32").line, "agreement not measured for Chromium 156.0.8078.4");
});

test("a run that never learned its browser's build says so", () => {
  assert.equal(agreementFor(list, null, "extension", "linux").line, "agreement not measured for Chromium (build unknown)");
});

test("the empty list measures nothing", () => {
  assert.equal(agreementFor({ builds: [] }, "156.0.8078.4", "devtools", "linux").line, "agreement not measured for Chromium 156.0.8078.4");
});

test("the list is read by build, and by the Playwright versions that ship it", () => {
  assert.equal(buildFor(list, "153.0.8010.12")?.playwright[0], "1.63.0");
  assert.equal(buildOfPlaywright(list, "1.64.1")?.chromium, "156.0.8078.4");
  assert.equal(buildOfPlaywright(list, "1.62.0"), undefined);
});

test("a source is named by its tree and operating system", () => {
  assert.equal(sourceKey("extension", "linux"), "extension-linux");
  assert.equal(sourceKey("devtools", "darwin"), "devtools-macos");
  assert.equal(sourceKey("extension", "win32"), "extension-windows");
});

test("the list the package ships has the schema, whatever it holds", () => {
  assert.deepEqual(problemsIn(readSupported()), []);
});

test("the schema accepts a good list and names what is wrong with a bad one", () => {
  assert.deepEqual(problemsIn(list), []);
  const bad = { builds: [
    { chromium: "156", playwright: [], measured: { "extension-mac": { agreement: 1.2, units: 0, date: "26 October", figure: "" } } },
    { chromium: "153.0.8010.12", playwright: ["1.63"], measured: {} },
    { chromium: "153.0.8010.12", playwright: ["1.63.0"] },
  ] } as unknown as SupportedVersions;
  const problems = problemsIn(bad);
  for (const wanted of ["builds[0].chromium is not a Chromium build", "builds[0].playwright is not a list", "builds[0].measured.extension-mac is not one of", "builds[0].measured.extension-mac.agreement", "builds[0].measured.extension-mac.units",
    "builds[0].measured.extension-mac.date", "builds[0].measured.extension-mac.figure", "builds[1].playwright", "builds[2].measured is missing", "Chromium 153.0.8010.12 is listed twice"]) {
    assert.ok(problems.some((p) => p.includes(wanted)), `${wanted}\n${problems.join("\n")}`);
  }
  assert.deepEqual(problemsIn({} as SupportedVersions), ["builds is not an array"]);
});

test("the list ships in the package, beside pins.json", () => {
  const root = join(import.meta.dirname, "..");
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as { files: string[] };
  assert.ok(pkg.files.includes("supported-versions.json"));
  assert.ok(existsSync(join(root, "supported-versions.json")));
});

test("a list that cannot be read, or fails its schema, is said so and is not taken for a build that is merely not measured", () => {
  const missing = loadSupported(new URL("file:///no/such/list.json"));
  assert.deepEqual(missing.list, { builds: [] });
  assert.match(missing.error!, /^could not be read: /);
  const line = withListError(agreementFor(missing.list, "156.0.8078.4", "extension", "linux"), missing.error).line;
  assert.match(line, /^agreement not measured for Chromium 156\.0\.8078\.4 \(the package's supported-versions\.json could not be read: /);
  assert.equal(withListError(agreementFor(list, "152.0.7999.1", "extension", "linux"), null).line, "agreement not measured for Chromium 152.0.7999.1");
});

test("the list the package ships loads without error", () => {
  assert.deepEqual(loadSupported().error, null);
});

test("an entry with no figures never throws in a report: the build reads as not measured", () => {
  const broken = { builds: [{ chromium: "156.0.8078.4", playwright: ["1.64.1"] }] } as unknown as SupportedVersions;
  assert.equal(agreementFor(broken, "156.0.8078.4", "extension", "linux").line, "agreement not measured for Chromium 156.0.8078.4");
  assert.equal(agreementFor({ builds: [null] } as unknown as SupportedVersions, "156.0.8078.4", "extension", "linux").measured, false);
});

test("the list ships in the package, beside pins.json", () => {
  const root = join(import.meta.dirname, "..");
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as { files: string[] };
  assert.ok(pkg.files.includes("supported-versions.json"));
  assert.ok(existsSync(join(root, "supported-versions.json")));
});
