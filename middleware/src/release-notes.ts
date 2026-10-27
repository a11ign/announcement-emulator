// The measured agreement of a release, and the Playwright versions it supports, as the section of the release's notes that carries them (ADR 0047 Decision 6, A11-232).
//
//     node middleware/src/release-notes.ts <version> [--root <repository root>] [--changelog <CHANGELOG.md>]
//
// The org's release workflow (a11ign/toolchain, release-per-merge.yml) cuts a package's Release with its CHANGELOG.md entry for the version as the notes. `middleware/release/after-version.sh` runs this after
// `changeset version`, which appends the section to that entry: so the notes of the Release, the CHANGELOG.md on the tag and the one in the npm tarball all carry the rate, with no notes feature in the workflow.
// The list is read through `loadSupported` and the types of supported.ts, and a field of a figure this file does not know is left out, never an error.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { loadSupported, percent, SOURCE_KEYS, type Figure, type SupportedBuild, type SupportedVersions } from "./supported.ts";

export const SECTION = "### Measured agreement";
/** Said on every release, whatever the figures: ADR 0047 Decision 2. Nothing in the notes says the speech is a screen reader's, that NV Access endorses it, or that it is compatible with one (docs/release-decisions.md section 1). */
export const ADVISORY = "The speech this package reports is a prediction. It is advisory and never evidence of what a screen reader says.";
const NOT_RECORDED = "not recorded", NOT_GIVEN = "not given";

export interface NotesInput {
  list: SupportedVersions;
  /** pins.env `NVDA_TAG`: the NVDA release whose source the prediction is built on. */
  nvda: string;
  /** The Edge version(s) the fleet readings behind a figure recorded (`figure` is the figure's path in the list), or none where they record none. */
  edgeOf: (figure: string) => string[];
}

const cell = (text: string | number) => String(text).replace(/\|/g, "\\|");
const row = (cells: (string | number)[]) => `| ${cells.map(cell).join(" | ")} |`;
const table = (head: string[], rows: (string | number)[][]) => [row(head), row(head.map(() => "---")), ...rows.map(row)];

const population = (figure: Figure) => figure.population ? `${figure.population.pages}, ${figure.population.heldOut ? "held out" : "not held out"}` : NOT_GIVEN;
const ceiling = (figure: Figure) => figure.ceiling ? percent(figure.ceiling.agreement) : NOT_GIVEN;

/** The sources of a build that have a figure, in the list's fixed order. */
const figuresOf = (build: SupportedBuild): [string, Figure][] => SOURCE_KEYS.flatMap((key) => (build.measured?.[key] ? [[key, build.measured[key]] as [string, Figure]] : []));

const playwrightLines = (list: SupportedVersions) => list.builds.map((b) => `- Playwright ${b.playwright.join(", ")}: Chromium ${b.chromium}`);

function agreementTable(input: NotesInput): string[] {
  const rows = input.list.builds.flatMap((build) => figuresOf(build).map(([source, figure]) => [
    build.chromium, build.playwright.join(", "), source, percent(figure.agreement), figure.units, figure.date, population(figure), ceiling(figure),
    input.edgeOf(figure.figure).join(", ") || NOT_RECORDED,
  ]));
  return table(["Chromium", "Playwright", "Tree source", "Agreement", "Units", "Measured", "Pages", "Fleet against itself", "Fleet's Edge"], rows);
}

/** The rate of each announcement shape of one figure: the measured rate per announcement type. */
function shapeTable(build: SupportedBuild, source: string, figure: Figure): string[] {
  if (!figure.shapes) return [];
  const rows = Object.entries(figure.shapes).map(([shape, f]) => [shape, percent(f.agreement), f.units, f.lowConfidence ? "low confidence" : ""]);
  return [`##### Chromium ${build.chromium}, ${source}, by announcement shape`, "", ...table(["Shape", "Agreement", "Units", ""], rows), ""];
}

/**
 * The section: what is measured and against what, the Playwright versions the release supports, the rate of every build and tree source with its units, date, pages and ceiling where the figure has them, the rate
 * of each announcement shape where it has them, and what is not measured.
 */
export function renderNotes(input: NotesInput): string {
  const { list, nvda } = input;
  if (!list.builds.length) throw new Error("the supported-versions list names no Chromium build, so there is no Playwright version to put in the notes");
  const shapes = list.builds.flatMap((build) => figuresOf(build).flatMap(([source, figure]) => shapeTable(build, source, figure)));
  return [
    SECTION, "",
    ADVISORY, "",
    `Agreement is the share of the fleet's real NVDA announcements that the predicted speech matches, measured for each Chromium build that a supported Playwright version ships. NVDA release: ${nvda}, the source the prediction is built on. A unit is one announcement compared. What is not listed here is not measured.`, "",
    "#### Supported Playwright versions", "", ...playwrightLines(list), "",
    "#### Agreement by build and tree source", "", ...agreementTable(input), "",
    ...shapes,
    "Windows: not measured. No reading of the DevTools tree on Windows has been taken.", "",
  ].join("\n");
}

const SECTION_AT = new RegExp(`^${SECTION}$`, "m");

/** The changelog with `notes` at the end of the entry for `version`, replacing the section a run before it left. The entry runs from its `## <version>` heading to the next `## ` heading. */
export function withNotes(changelog: string, version: string, notes: string): string {
  const lines = changelog.split("\n");
  const start = lines.findIndex((line) => line.startsWith("## ") && line.slice(3).trim() === version);
  if (start < 0) throw new Error(`CHANGELOG.md has no entry for ${version}; changeset version wrote none`);
  const next = lines.findIndex((line, i) => i > start && line.startsWith("## "));
  const end = next < 0 ? lines.length : next;
  const entry = lines.slice(start, end).join("\n");
  const kept = (SECTION_AT.test(entry) ? entry.slice(0, entry.search(SECTION_AT)) : entry).trimEnd();
  return [...lines.slice(0, start), `${kept}\n\n${notes.trimEnd()}\n`, ...lines.slice(end)].join("\n");
}

/** `NAME=value` of pins.env, a plain shell assignment file. */
export function pinValue(pinsEnv: string, name: string): string {
  const found = new RegExp(`^${name}=(\\S+)`, "m").exec(pinsEnv);
  if (!found) throw new Error(`pins.env has no ${name}`);
  return found[1]!;
}

/** The fleet readings behind a figure sit in the `fleet-readings.json` of the nearest directory above it that has one (middleware/results/<round>/fleet-readings.json). The Edge versions they recorded; none where no file or no version is there. */
export function edgeVersions(root: string, figure: string): string[] {
  for (let dir = resolve(root, figure); dir !== dirname(dir) && dir.startsWith(resolve(root)); dir = dirname(dir)) {
    const file = join(dir, "fleet-readings.json");
    if (!existsSync(file)) continue;
    const readings = JSON.parse(readFileSync(file, "utf8")) as { environment?: { browserVersion?: unknown } }[];
    return [...new Set(readings.flatMap((r) => (typeof r.environment?.browserVersion === "string" ? [r.environment.browserVersion] : [])))];
  }
  return [];
}

/** What the repository at `root` says: the list the package ships, pins.env, and the fleet readings under middleware/results. A list that cannot be read fails the release rather than describing no builds. */
export function readNotesInput(root: string): NotesInput {
  const { list, error } = loadSupported(pathToFileURL(join(root, "middleware", "supported-versions.json")));
  if (error) throw new Error(`middleware/supported-versions.json ${error}`);
  return { list, nvda: pinValue(readFileSync(join(root, "pins.env"), "utf8"), "NVDA_TAG"), edgeOf: (figure) => edgeVersions(root, figure) };
}

function main(argv: string[]) {
  const option = (name: string, fallback: string) => { const at = argv.indexOf(name); return at >= 0 ? argv[at + 1]! : fallback; };
  const version = argv[0];
  if (!version || version.startsWith("--")) throw new Error("usage: release-notes.ts <version> [--root <repository root>] [--changelog <CHANGELOG.md>]");
  const root = resolve(option("--root", "."));
  const changelog = resolve(root, option("--changelog", "middleware/CHANGELOG.md"));
  writeFileSync(changelog, withNotes(readFileSync(changelog, "utf8"), version, renderNotes(readNotesInput(root))));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main(process.argv.slice(2));
