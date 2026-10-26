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

/** What `rates.json` (agreement/round.py) and the by-shape table of `agreement.txt` say about a figure that the list also says, one line each where they differ. A figure a round did not write has neither and is not held to them. */
interface Rates { pages: number; heldOut: boolean; headline: { agreed: number; units: number }; ceiling: { agreed: number; units: number }; shapes: Record<string, { agreed: number; units: number; lowConfidence: boolean }> }
const near = (a: number, agreed: number, units: number) => Math.abs(a - agreed / units) <= 0.0005 + 1e-9;      // the list holds a rate to the tenth of a percent (the headline) or to three decimals (a shape)

type Round = Required<Pick<Figure, "population" | "ceiling" | "shapes">> & Figure;

const populationDisagreements = (f: Round, path: string, rates: Rates): string[] => [
  ...(f.population.pages !== rates.pages ? [`population.pages ${f.population.pages} is not ${rates.pages}`] : []),
  ...(f.population.heldOut !== rates.heldOut ? [`population.heldOut ${f.population.heldOut} is not ${rates.heldOut}`] : []),
  ...(f.population.heldOut !== path.includes("/held-out/") || path.includes("/held-out/") === path.includes("/fitted/") ? [`the figure path ${path} does not say whether the pages were held out`] : []),
  ...(f.units !== rates.headline.units ? [`units ${f.units} is not ${rates.headline.units}`] : []),
];

const ceilingDisagreements = (f: Round, rates: Rates): string[] =>
  f.ceiling.units !== rates.ceiling.units || !near(f.ceiling.agreement, rates.ceiling.agreed, rates.ceiling.units) ? [`ceiling ${f.ceiling.agreement} of ${f.ceiling.units} is not ${rates.ceiling.agreed} of ${rates.ceiling.units}`] : [];

function shapeDisagreements(f: Round, rates: Rates): string[] {
  const withUnits = Object.entries(rates.shapes).filter(([k, v]) => v.units > 0 && k !== "");
  const same = Object.keys(f.shapes).sort().join("|") === withUnits.map(([k]) => k).sort().join("|");
  return [
    ...(same ? [] : ["the shapes are not the shapes of rates.json"]),
    ...withUnits.flatMap(([shape, v]) => {
      const listed = f.shapes[shape];
      return listed && (listed.units !== v.units || !near(listed.agreement, v.agreed, v.units) || listed.lowConfidence !== v.lowConfidence)
        ? [`shape ${shape}: ${listed.agreement} of ${listed.units} (${listed.lowConfidence}) is not ${v.agreed} of ${v.units} (${v.lowConfidence})`] : [];
    }),
  ];
}

/** The by-shape table of an agreement.txt (the ten commonest): each line's counts are the list's for the shape. */
function tableDisagreements(f: Round, agreementTxt: string): string[] {
  const table = agreementTxt.split("agreement by shape").at(-1)!.split("\n").map((l) => l.split(" | ")).filter((c) => c.length === 3);
  if (!table.length) return ["agreement.txt has no by-shape table"];
  return table.flatMap((cells) => {
    const counts = /^\s*(\d+) \/ (\d+)\s/.exec(cells[0]!), label = /(?:\d+\.\d%|n\/a)\s{2}(\S.*)$/.exec(cells[2]!)?.[1]?.trim();
    const listed = label ? f.shapes[label] : undefined;
    if (!counts || !label || !listed) return [`agreement.txt names a shape the list does not: ${label}`];
    return listed.units !== Number(counts[2]) || !near(listed.agreement, Number(counts[1]), Number(counts[2])) ? [`shape ${label}: the list says ${listed.agreement} of ${listed.units}, agreement.txt ${counts[1]} of ${counts[2]}`] : [];
  });
}

export function figureDisagreements(figure: Figure, path: string, rates: Rates, agreementTxt: string): string[] {
  if (!figure.population || !figure.ceiling || !figure.shapes) return ["a round's figure has a population, a ceiling and shapes"];
  const f = figure as Round;
  return [...populationDisagreements(f, path, rates), ...ceilingDisagreements(f, rates), ...shapeDisagreements(f, rates), ...tableDisagreements(f, agreementTxt)];
}

test("a figure a round wrote is the same as its rates.json and the by-shape table of its agreement.txt: the population, the ceiling and each shape", () => {
  for (const build of shipped.builds) {
    for (const [key, figure] of Object.entries(build.measured)) {
      if (!existsSync(join(repoRoot, figure.figure, "rates.json"))) continue;      // an earlier round's figure (A11-230's) has only the headline
      const rates = JSON.parse(readFileSync(join(repoRoot, figure.figure, "rates.json"), "utf8")) as Rates;
      assert.deepEqual(figureDisagreements(figure, figure.figure, rates, readFileSync(join(repoRoot, figure.figure, "agreement.txt"), "utf8")), [], `${build.chromium} ${key}`);
    }
  }
});

const sampleRates: Rates = { pages: 6, heldOut: true, headline: { agreed: 80, units: 100 }, ceiling: { agreed: 95, units: 100 }, shapes: { "NAME + ROLE": { agreed: 60, units: 70, lowConfidence: false }, "NAME + ROLE + LEVEL": { agreed: 20, units: 30, lowConfidence: true } } };
const sampleFigure: Figure = { agreement: 0.8, units: 100, date: "2026-10-26", figure: "middleware/results/agreement-round-1/held-out/156.0.8078.4/extension-linux/", population: { pages: 6, heldOut: true, units: 100 }, ceiling: { agreement: 0.95, units: 100 },
  shapes: { "NAME + ROLE": { agreement: 0.857, units: 70, lowConfidence: false }, "NAME + ROLE + LEVEL": { agreement: 0.667, units: 30, lowConfidence: true } } };
const sampleTxt = "agreement by shape (the 10 commonest)\n   60 / 70     85.7% |   69 / 70     98.6% |   70 / 70    100.0%  NAME + ROLE\n   20 / 30     66.7% |   30 / 30    100.0% |   30 / 30    100.0%  NAME + ROLE + LEVEL\n";

test("the check of a round's figure against its rates passes for a figure that matches, and names each thing that does not", () => {
  assert.deepEqual(figureDisagreements(sampleFigure, sampleFigure.figure, sampleRates, sampleTxt), []);
  const changed = (f: Partial<Figure>) => figureDisagreements({ ...sampleFigure, ...f }, sampleFigure.figure, sampleRates, sampleTxt);
  assert.match(changed({ population: { pages: 5, heldOut: true, units: 100 } }).join(), /population.pages 5 is not 6/);
  assert.match(changed({ population: { pages: 6, heldOut: false, units: 100 } }).join(), /heldOut false is not true/);
  assert.match(changed({ ceiling: { agreement: 0.9, units: 100 } }).join(), /ceiling 0.9 of 100/);
  assert.match(changed({ shapes: { ...sampleFigure.shapes, "NAME + ROLE": { agreement: 0.9, units: 70, lowConfidence: false } } }).join(), /shape NAME \+ ROLE: 0.9 of 70/);
  assert.match(changed({ shapes: { ...sampleFigure.shapes, "NAME + ROLE + LEVEL": { agreement: 0.667, units: 30, lowConfidence: false } } }).join(), /shape NAME \+ ROLE \+ LEVEL.*\(false\) is not 20 of 30 \(true\)/);
  assert.match(changed({ shapes: { "NAME + ROLE": sampleFigure.shapes!["NAME + ROLE"]! } }).join(), /the shapes are not the shapes of rates.json/);
  assert.match(changed({ units: 99 }).join(), /units 99 is not 100/);
  assert.match(figureDisagreements(sampleFigure, "middleware/results/agreement-round-1/fitted/156.0.8078.4/extension-linux/", sampleRates, sampleTxt).join(), /does not say whether the pages were held out/);
  assert.match(figureDisagreements(sampleFigure, sampleFigure.figure, sampleRates, sampleTxt.replace("85.7%", "80.0%").replace("60 / 70", "56 / 70")).join(), /agreement.txt 56 of 70/);
  assert.match(figureDisagreements(sampleFigure, sampleFigure.figure, sampleRates, "no table").join(), /no by-shape table/);
  assert.match(changed({ shapes: undefined }).join(), /has a population, a ceiling and shapes/);
});

// The demo job of middleware-spike.yml: one row for each platform and Playwright version, and what each row's reports are held to saying (check-report.mjs).
// The rows are the `mode` job's script (full mode has all of them): one JSON object each.
const rows = [...readFileSync(join(repoRoot, ".github", "workflows", "middleware-spike.yml"), "utf8").matchAll(/"platform": "([\w-]+)", "runner": "([\w-]+)", "playwright": "([\d.]+)", "agreement": "(\w+)", "other-agreement": "(\w+)", "chromium": "([\d.]+)"/g)]
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
