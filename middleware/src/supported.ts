import { readFileSync } from "node:fs";
import type { TreeSource } from "./extension.ts";

/** One measured reading of a build: the headline figure of `results/playwright-versions/<build>/<source>-<os>/agreement.txt`. */
export interface Figure { agreement: number; units: number; date: string; figure: string }

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

/** The list the package ships, and what is wrong with it if it cannot be used: a missing or corrupt list is a broken package, and is said so (in the console, in `run.json` and in each report's sentence), not reported as a build that is merely not measured. */
export interface SupportedRead { list: SupportedVersions; error: string | null }

/** Reads the list without ever throwing, so that a broken list cannot fail a test run, and without hiding it: a list that is unreadable or fails its schema reads as empty, with `error` saying why. */
export function loadSupported(url?: URL): SupportedRead {
  try {
    const list = readSupported(url);
    const problems = problemsIn(list);
    return problems.length ? { list: { builds: [] }, error: `invalid: ${problems.slice(0, 3).join("; ")}` } : { list, error: null };
  } catch (error) {
    return { list: { builds: [] }, error: `could not be read: ${(error as Error).message}` };
  }
}

/** A report's sentence when the list was unusable: it still says the agreement is not measured, and also that the package's list is the reason. */
export function withListError(agreement: Agreement, error: string | null): Agreement {
  return error ? { ...agreement, line: `${agreement.line} (the package's supported-versions.json ${error})` } : agreement;
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
}

export const percent = (agreement: number) => `${(agreement * 100).toFixed(1)}%`;

/**
 * The agreement of the build a run used, for the tree source it used. A listed build with a figure for this source and platform says its rate; every other case says "not measured" and the run
 * goes on: an unlisted version still gets predicted speech.
 */
export function agreementFor(list: SupportedVersions, chromium: string | null, tree: TreeSource, platform: string = process.platform): Agreement {
  const source = sourceKey(tree, platform);
  if (!chromium) return { line: "agreement not measured for Chromium (build unknown)", measured: false, chromium, source };
  const build = buildFor(list, chromium), figure = build?.measured?.[source];
  if (!build || !figure) return { line: `agreement not measured for Chromium ${chromium}`, measured: false, chromium, source };
  const versions = (build.playwright ?? []).join(", ");
  return {
    line: `agreement measured for Chromium ${chromium} (Playwright ${versions}), ${tree}: ${percent(figure.agreement)} of ${figure.units} units, ${figure.date} (${figure.figure})`,
    measured: true, chromium, source, playwright: build.playwright, ...figure,
  };
}

const figureProblems = (where: string, f: Figure): string[] => [
  ...(typeof f.agreement === "number" && f.agreement >= 0 && f.agreement <= 1 ? [] : [`${where}.agreement is not a rate between 0 and 1`]),
  ...(Number.isInteger(f.units) && f.units > 0 ? [] : [`${where}.units is not a count`]),
  ...(/^\d{4}-\d{2}-\d{2}$/.test(f.date ?? "") ? [] : [`${where}.date is not YYYY-MM-DD`]),
  ...(f.figure && typeof f.figure === "string" ? [] : [`${where}.figure is not a path`]),
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
