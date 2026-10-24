import { readFileSync } from "node:fs";
import type { TreeSource } from "./extension.ts";

/** What the headline rate was measured on: how many pages, whether they were held out (chosen and frozen before the emulator or the fleet read them), and the units compared, which are the units of the rate. */
export interface Population { pages: number; heldOut: boolean; units: number }
/** The ceiling the oracle puts on the rate: the fleet against itself on the same pages and channels. Agreement above it cannot be told from the oracle's own noise. */
export interface Ceiling { agreement: number; units: number }
/** The rate of one announcement shape (`"NAME + ROLE"`, the fleet's `q3/shapes.py`), over the units of that shape. `lowConfidence` is set when the list is filled (agreement/round.py), where the attribution shows the shape is weak. */
export interface ShapeFigure { agreement: number; units: number; lowConfidence: boolean }

/**
 * One measured reading of a build: the headline figure of `results/<round>/<build>/<source>-<os>/agreement.txt`. A figure written before a round measured the rest (A11-230's) has only the first four fields and reads as it
 * did; one a round wrote also says what it was measured on, what the oracle's own noise puts as the ceiling, and the rate of each shape.
 */
export interface Figure { agreement: number; units: number; date: string; figure: string; population?: Population; ceiling?: Ceiling; shapes?: Record<string, ShapeFigure> }

/** A Chromium build with a measured agreement rate, and the Playwright versions that ship that build. The build is what was measured, so it is the key. */
export interface SupportedBuild { chromium: string; playwright: string[]; measured: Record<string, Figure> }
export interface SupportedVersions { builds: SupportedBuild[] }

/** The readings a build can have: a tree source on an operating system. Windows has none, and says so by being "not measured". */
export const SOURCE_KEYS = ["extension-linux", "devtools-linux", "devtools-macos"] as const;

/** The list ships in the package (`supported-versions.json` beside `dist`). */
export function readSupported(url = new URL("../supported-versions.json", import.meta.url)): SupportedVersions {
  return JSON.parse(readFileSync(url, "utf8")) as SupportedVersions;
}

const OS: Record<string, string> = { linux: "linux", darwin: "macos", win32: "windows" };
export const sourceKey = (tree: TreeSource, platform: string = process.platform): string => `${tree}-${OS[platform] ?? platform}`;

export const buildFor = (list: SupportedVersions, chromium: string | null): SupportedBuild | undefined => list.builds.find((b) => b?.chromium === chromium);
export const buildOfPlaywright = (list: SupportedVersions, version: string): SupportedBuild | undefined => list.builds.find((b) => b.playwright.includes(version));

/** The list, or an empty one when it cannot be read or is not a list: the wording of a prediction must never fail a run. */
export function readSupportedSafely(url?: URL): SupportedVersions {
  try {
    const list = readSupported(url);
    return Array.isArray(list?.builds) ? list : { builds: [] };
  } catch {
    return { builds: [] };
  }
}

/** What a report says about the agreement of the Chromium it ran in. */
export interface Agreement {
  /** The sentence the report carries. */
  line: string;
  measured: boolean;
  chromium: string | null;
  source: string;
  playwright?: string[];
  agreement?: number;
  units?: number;
  date?: string;
  figure?: string;
  population?: Population;
  ceiling?: Ceiling;
  shapes?: Record<string, ShapeFigure>;
}

export const percent = (agreement: number) => `${(agreement * 100).toFixed(1)}%`;
const isRate = (x: unknown) => typeof x === "number" && x >= 0 && x <= 1;
const isCount = (x: unknown) => Number.isInteger(x) && (x as number) > 0;
const plural = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/** The sentence for a measured figure: the rate and its units, what they were measured on if the figure says, the date, what the oracle's own noise puts as the ceiling if the figure says, and where the figure is. */
function measuredLine(chromium: string, build: SupportedBuild, tree: TreeSource, figure: Figure): string {
  const { population, ceiling: noise } = figure;      // a part of the figure that is not well formed is left out of the sentence: the wording of a prediction must never fail a run
  const on = population && isCount(population.pages) && typeof population.heldOut === "boolean" ? ` on ${plural(population.pages, `${population.heldOut ? "held-out" : "not held-out"} page`)}` : "";
  const ceiling = noise && isRate(noise.agreement) ? `; the fleet agrees with itself on ${percent(noise.agreement)}` : "";
  return `agreement measured for Chromium ${chromium} (Playwright ${(build.playwright ?? []).join(", ")}), ${tree}: ${percent(figure.agreement)} of ${figure.units} units${on}, ${figure.date}${ceiling} (${figure.figure})`;
}

/** What a measured rate says of one announcement, by its shape. */
export interface ShapeRate { shape: string; measured: boolean; agreement?: number; units?: number; lowConfidence?: boolean }

/**
 * The measured rate of the shape of one predicted utterance (`shape` is the runtime's: the tokens `q3/shapes.py` gives it, joined as the figure's keys are). Nothing for a run whose figure has no shapes (an unlisted build, or a
 * figure written before a round measured them): such a run does not claim a rate by shape. A shape the round never saw reads `measured: false`.
 */
export function shapeRateFor(agreement: Agreement | undefined, shape: unknown): ShapeRate | null {
  if (!agreement?.measured || !agreement.shapes || !Array.isArray(shape) || !shape.every((t) => typeof t === "string")) return null;
  const key = shape.join(" + "), found = agreement.shapes[key];
  if (!found || !isRate(found.agreement) || !isCount(found.units)) return { shape: key, measured: false };
  return { shape: key, measured: true, agreement: found.agreement, units: found.units, ...(found.lowConfidence ? { lowConfidence: true } : {}) };
}

/**
 * The agreement of the build a run used, for the tree source it used. A listed build with a figure for this source and platform says its rate; every other case says "not measured" and the run
 * goes on: an unlisted version still gets predicted speech.
 */
export function agreementFor(list: SupportedVersions, chromium: string | null, tree: TreeSource, platform: string = process.platform): Agreement {
  const source = sourceKey(tree, platform);
  if (!chromium) return { line: "agreement not measured for Chromium (build unknown)", measured: false, chromium, source };
  const build = buildFor(list, chromium), figure = build?.measured?.[source];
  if (!build || !figure) return { line: `agreement not measured for Chromium ${chromium}`, measured: false, chromium, source };
  return { line: measuredLine(chromium, build, tree, figure), measured: true, chromium, source, playwright: build.playwright, ...figure };
}

const SHAPE_KEY = /^[A-Z]+( \+ [A-Z]+)*$/;

const populationProblems = (where: string, p: Population, units: number): string[] => [
  ...(isCount(p.pages) ? [] : [`${where}.pages is not a count`]),
  ...(typeof p.heldOut === "boolean" ? [] : [`${where}.heldOut is not true or false`]),
  ...(p.units === units ? [] : [`${where}.units is not the units of the rate (${units})`]),
];

const shapeProblems = (where: string, shapes: Record<string, ShapeFigure>): string[] => Object.entries(shapes).flatMap(([key, f]) => [
  ...(SHAPE_KEY.test(key) ? [] : [`${where}.${key} is not a shape (NAME + ROLE)`]),
  ...(isRate(f?.agreement) ? [] : [`${where}.${key}.agreement is not a rate between 0 and 1`]),
  ...(isCount(f?.units) ? [] : [`${where}.${key}.units is not a count`]),
  ...(typeof f?.lowConfidence === "boolean" ? [] : [`${where}.${key}.lowConfidence is not true or false`]),
]);

const figureProblems = (where: string, f: Figure): string[] => [
  ...(isRate(f.agreement) ? [] : [`${where}.agreement is not a rate between 0 and 1`]),
  ...(isCount(f.units) ? [] : [`${where}.units is not a count`]),
  ...(/^\d{4}-\d{2}-\d{2}$/.test(f.date ?? "") ? [] : [`${where}.date is not YYYY-MM-DD`]),
  ...(f.figure && typeof f.figure === "string" ? [] : [`${where}.figure is not a path`]),
  ...(f.population === undefined ? [] : populationProblems(`${where}.population`, f.population, f.units)),
  ...(f.ceiling === undefined ? [] : [...(isRate(f.ceiling.agreement) ? [] : [`${where}.ceiling.agreement is not a rate between 0 and 1`]), ...(isCount(f.ceiling.units) ? [] : [`${where}.ceiling.units is not a count`])]),
  ...(f.shapes === undefined ? [] : f.shapes && typeof f.shapes === "object" && !Array.isArray(f.shapes) ? shapeProblems(`${where}.shapes`, f.shapes) : [`${where}.shapes is not a table of shapes`]),
];

const buildProblems = (at: string, b: SupportedBuild): string[] => [
  ...(/^\d+\.\d+\.\d+\.\d+$/.test(b.chromium ?? "") ? [] : [`${at}.chromium is not a Chromium build (a.b.c.d)`]),
  ...(Array.isArray(b.playwright) && b.playwright.length && b.playwright.every((v) => /^\d+\.\d+\.\d+$/.test(v)) ? [] : [`${at}.playwright is not a list of Playwright versions`]),
  ...(b.measured && typeof b.measured === "object" ? Object.entries(b.measured).flatMap(([key, f]) => [
    ...((SOURCE_KEYS as readonly string[]).includes(key) ? [] : [`${at}.measured.${key} is not one of ${SOURCE_KEYS.join(", ")}`]),
    ...figureProblems(`${at}.measured.${key}`, f),
  ]) : [`${at}.measured is missing`]),
];

/** What is wrong with a list, one line each: the schema the package's test holds `supported-versions.json` to. */
export function problemsIn(list: SupportedVersions): string[] {
  if (!Array.isArray(list?.builds)) return ["builds is not an array"];
  const builds = list.builds.map((b) => b.chromium);
  const twice = builds.filter((c, i) => builds.indexOf(c) !== i).map((c) => `Chromium ${c} is listed twice`);
  return [...list.builds.flatMap((b, i) => buildProblems(`builds[${i}]`, b)), ...twice];
}
