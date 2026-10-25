import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { agreementFor, buildFor, buildOfPlaywright, percent, problemsIn, loadSupported, readSupported, shapeRateFor, sourceKey, withListError, type Figure, type SupportedVersions } from "./supported.ts";

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

/** A figure as a round writes it (A11-234): what it was measured on, the fleet's own noise as the ceiling, and the rate of each shape. */
const round = (over: Partial<Figure> = {}): Figure => ({
  ...figure(0.831, 249, "extension-linux"),
  population: { pages: 6, heldOut: true, units: 249 },
  ceiling: { agreement: 0.952, units: 249 },
  shapes: { "NAME + ROLE": { agreement: 0.86, units: 57, lowConfidence: false }, "NAME": { agreement: 0.682, units: 22, lowConfidence: true } },
  ...over,
});
const rounds = (over: Partial<Figure> = {}): SupportedVersions => ({ builds: [{ chromium: "156.0.8078.4", playwright: ["1.64.0", "1.64.1"], measured: { "extension-linux": round(over) } }] });

test("a figure that says what it was measured on and the fleet's own noise puts both in the sentence, with the date, before where the figure is", () => {
  const a = agreementFor(rounds(), "156.0.8078.4", "extension", "linux");
  assert.equal(a.line, "agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.0, 1.64.1), extension: 83.1% of 249 units on 6 held-out pages, 2026-10-26; the fleet agrees with itself on 95.2% (middleware/results/playwright-versions/156.0.8078.4/extension-linux/)");
  assert.deepEqual([a.population, a.ceiling], [{ pages: 6, heldOut: true, units: 249 }, { agreement: 0.952, units: 249 }]);
});

test("pages that were not held out say so, and one page is not 'pages'", () => {
  assert.match(agreementFor(rounds({ population: { pages: 6, heldOut: false, units: 249 } }), "156.0.8078.4", "extension", "linux").line, /of 249 units on 6 not held-out pages, 2026-10-26;/);
  assert.match(agreementFor(rounds({ population: { pages: 1, heldOut: true, units: 249 } }), "156.0.8078.4", "extension", "linux").line, /on 1 held-out page, 2026-10-26;/);
});

test("a figure with a population and no ceiling, or the other way round, says only what it has", () => {
  const noCeiling = agreementFor(rounds({ ceiling: undefined }), "156.0.8078.4", "extension", "linux").line;
  assert.match(noCeiling, /of 249 units on 6 held-out pages, 2026-10-26 \(middleware/); assert.doesNotMatch(noCeiling, /agrees with itself/);
  const noPopulation = agreementFor(rounds({ population: undefined }), "156.0.8078.4", "extension", "linux").line;
  assert.match(noPopulation, /of 249 units, 2026-10-26; the fleet agrees with itself on 95\.2% \(middleware/); assert.doesNotMatch(noPopulation, / pages?,/);
});

test("a part of a figure that is not well formed is left out of the sentence, and the sentence is still said", () => {
  const broken = rounds({ population: { pages: "six", heldOut: 1, units: 249 } as unknown as Figure["population"], ceiling: { agreement: 2, units: 1 } });
  assert.equal(agreementFor(broken, "156.0.8078.4", "extension", "linux").line, "agreement measured for Chromium 156.0.8078.4 (Playwright 1.64.0, 1.64.1), extension: 83.1% of 249 units, 2026-10-26 (middleware/results/playwright-versions/156.0.8078.4/extension-linux/)");
});

test("the rate of a shape is the figure's for that shape, with the marker the list gives a weak one", () => {
  const a = agreementFor(rounds(), "156.0.8078.4", "extension", "linux");
  assert.deepEqual(shapeRateFor(a, ["NAME", "ROLE"]), { shape: "NAME + ROLE", measured: true, agreement: 0.86, units: 57 });
  assert.deepEqual(shapeRateFor(a, ["NAME"]), { shape: "NAME", measured: true, agreement: 0.682, units: 22, lowConfidence: true });
});

test("a shape the round never saw is not measured, and so is one whose entry is not a rate", () => {
  const a = agreementFor(rounds(), "156.0.8078.4", "extension", "linux");
  assert.deepEqual(shapeRateFor(a, ["ROLE", "NAME", "LEVEL"]), { shape: "ROLE + NAME + LEVEL", measured: false });
  const bad = agreementFor(rounds({ shapes: { NAME: { agreement: "high", units: 3, lowConfidence: false } as never } }), "156.0.8078.4", "extension", "linux");
  assert.deepEqual(shapeRateFor(bad, ["NAME"]), { shape: "NAME", measured: false });
});

test("a run claims no rate by shape where its figure has none: a figure from before shapes, a build that is not listed, or no figure at all", () => {
  assert.equal(shapeRateFor(agreementFor(list, "156.0.8078.4", "extension", "linux"), ["NAME", "ROLE"]), null);
  assert.equal(shapeRateFor(agreementFor(rounds(), "152.0.7999.1", "extension", "linux"), ["NAME", "ROLE"]), null);
  assert.equal(shapeRateFor(undefined, ["NAME", "ROLE"]), null);
  assert.equal(shapeRateFor(agreementFor(rounds(), "156.0.8078.4", "extension", "linux"), undefined), null);
});

test("the schema accepts a figure a round wrote and names what is wrong with its population, ceiling and shapes", () => {
  assert.deepEqual(problemsIn(rounds()), []);
  const bad = rounds({ population: { pages: 0, heldOut: "yes", units: 100 } as unknown as Figure["population"], ceiling: { agreement: 1.5, units: 0 }, shapes: { "name + role": { agreement: 2, units: 0, lowConfidence: "no" } as never, "NAME +": { agreement: 0.5, units: 1, lowConfidence: false } } });
  const problems = problemsIn(bad);
  for (const wanted of ["measured.extension-linux.population.pages is not a count", "population.heldOut is not true or false", "population.units is not the units of the rate (249)", "ceiling.agreement is not a rate", "ceiling.units is not a count",
    "shapes.name + role is not a shape", "shapes.name + role.agreement is not a rate", "shapes.name + role.units is not a count", "shapes.name + role.lowConfidence is not true or false", "shapes.NAME + is not a shape"]) {
    assert.ok(problems.some((p) => p.includes(wanted)), `${wanted}\n${problems.join("\n")}`);
  }
  assert.ok(problemsIn(rounds({ shapes: [] as never })).some((p) => p.includes("shapes is not a table of shapes")));
});

test("a population or a ceiling that is null is named by the schema and does not throw", () => {
  const problems = problemsIn(rounds({ population: null as never, ceiling: null as never }));
  assert.ok(problems.some((p) => p.includes("population is not a population")), problems.join("\n"));
  assert.ok(problems.some((p) => p.includes("ceiling is not a ceiling")), problems.join("\n"));
});

test("the list ships in the package, beside pins.json", () => {
  const root = join(import.meta.dirname, "..");
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as { files: string[] };
  assert.ok(pkg.files.includes("supported-versions.json"));
  assert.ok(existsSync(join(root, "supported-versions.json")));
});

const repoRoot = join(import.meta.dirname, "..", "..");
const shipped = readSupported();

test("every figure the list ships is in the repository, and its agreement.txt gives the same rate and units", () => {
  for (const build of shipped.builds) {
    for (const [key, figure] of Object.entries(build.measured)) {
      const file = join(repoRoot, figure.figure, "agreement.txt");
      assert.ok(figure.figure.includes(`/${build.chromium}/${key}/`), `${build.chromium} ${key}: the figure path names its build and reading (${figure.figure})`);
      assert.ok(existsSync(file), `${build.chromium} ${key}: ${file} exists`);
      // the headline is the last block's "all channels" line: every channel, the first fleet capture against the first passive run (middleware/results/playwright-versions/rule.md)
      const lines = readFileSync(file, "utf8").split("\n").filter((l) => l.startsWith("all channels: "));
      const headline = /^all channels: (\d+) of (\d+) units agreed = ([\d.]+)%$/.exec(lines.at(-1) ?? "");
      assert.ok(headline, `${build.chromium} ${key}: agreement.txt has a headline line`);
      assert.equal(Number(headline![2]), figure.units, `${build.chromium} ${key}: units`);
      assert.equal(`${headline![3]}%`, percent(figure.agreement), `${build.chromium} ${key}: the rate agreement.txt prints`);
      assert.ok(Math.abs(Number(headline![1]) / Number(headline![2]) - figure.agreement) <= 0.0005 + 1e-9, `${build.chromium} ${key}: the fraction is the one agreement.txt counts (to the tenth of a percent it prints)`);
      assert.ok(existsSync(join(repoRoot, figure.figure, "misses.json")), `${build.chromium} ${key}: misses.json, with a cause for each miss`);
    }
  }
});

// The demo job of middleware-spike.yml: one row for each platform and Playwright version, and what each row's reports are held to saying (check-report.mjs).
const rows = [...readFileSync(join(repoRoot, ".github", "workflows", "middleware-spike.yml"), "utf8").matchAll(/- \{ platform: ([\w-]+), runner: ([\w-]+), playwright: "([\d.]+)", agreement: (\w+), other-agreement: (\w+), chromium: "([\d.]+)"/g)]
  .map(([, platform, , playwright, agreement, otherAgreement, chromium]) => ({ platform: platform!, playwright: playwright!, agreement: agreement!, otherAgreement: otherAgreement!, chromium: chromium! }));

test("the sample suite's CI rows are held to the list: a listed version's rows expect a measured sentence, every other version's the not-measured one", () => {
  assert.ok(rows.length >= 4, "the matrix is read");
  for (const row of rows) {
    const listed = buildOfPlaywright(shipped, row.playwright);
    assert.equal(row.agreement, listed?.measured[row.platform === "darwin-arm64" ? "devtools-macos" : "extension-linux"] ? "measured" : "unmeasured", `${row.platform} Playwright ${row.playwright}`);
    if (listed) assert.equal(row.chromium, listed.chromium, `${row.platform} Playwright ${row.playwright} runs the build the list names`);
  }
});

test("the third run of a row is the platform's other source: devtools on Linux (measured when the default is), the extension on macOS (never a figure there)", () => {
  for (const row of rows) {
    const listed = buildOfPlaywright(shipped, row.playwright);
    const wanted = row.platform === "darwin-arm64" ? "unmeasured" : listed?.measured["devtools-linux"] ? "measured" : "unmeasured";
    assert.equal(row.otherAgreement, wanted, `${row.platform} Playwright ${row.playwright}`);
  }
});

test("each listed build is run in CI on both platforms by its newest Playwright, and one version that is not listed holds the not-measured wording", () => {
  for (const build of shipped.builds) {
    const newest = build.playwright.at(-1)!;
    for (const platform of ["linux-x64", "darwin-arm64"]) assert.ok(rows.some((r) => r.platform === platform && r.playwright === newest && r.chromium === build.chromium), `${build.chromium}: Playwright ${newest} on ${platform}`);
  }
  assert.ok(rows.some((r) => r.platform === "linux-x64" && !buildOfPlaywright(shipped, r.playwright)), "a Linux row runs a Playwright that is not on the list");
  for (const row of rows) {
    const listed = buildOfPlaywright(shipped, row.playwright);
    if (listed) assert.equal(row.playwright, listed.playwright.at(-1), `${row.playwright} is listed, so only the newest Playwright of its build (${listed.chromium}) has a row`);
  }
});
