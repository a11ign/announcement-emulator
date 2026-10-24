import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, dirname, join } from "node:path";

/** A browser build Playwright ships: the revision it downloads and the Chromium build that revision is. */
export interface ShippedBrowser { revision: string; build: string }

/** What the team's own Playwright says about the Chromium it installs, read once and shared by the config, the reporter and `doctor`. */
export interface PlaywrightChromium {
  /** `@playwright/test`'s version. */
  version: string;
  /** The full Chromium (`npx playwright install chromium`), from `playwright-core/browsers.json`. */
  chromium: ShippedBrowser;
  /** The headless shell, which Playwright 1.49 and later runs for a headless launch with no channel; null where `browsers.json` has none. It loads no extension. */
  headlessShell: ShippedBrowser | null;
  /** Where the full Chromium is looked for (`chromium.executablePath()`), and whether it and the headless shell are there. */
  executablePath: string | null;
  fullInstalled: boolean;
  shellInstalled: boolean;
}

interface BrowsersJson { browsers: { name: string; revision: string; browserVersion?: string }[] }

const shipped = (browsers: BrowsersJson["browsers"], name: string): ShippedBrowser | null => {
  const entry = browsers.find((b) => b.name === name);
  return entry?.browserVersion ? { revision: entry.revision, build: entry.browserVersion } : null;
};

/**
 * The team's Playwright, resolved from `from` (the directory of the config, which is the working directory when Playwright loads it) and not from this package: the Chromium that matters is
 * the one the team's `@playwright/test` installs. Null when it cannot be read; nothing here may break a run.
 */
export function readPlaywright(from = process.cwd()): PlaywrightChromium | null {
  try {
    const here = createRequire(join(from, "noop.js"));
    const testPackage = here.resolve("@playwright/test/package.json");
    const version = (JSON.parse(readFileSync(testPackage, "utf8")) as { version: string }).version;
    const corePackage = createRequire(createRequire(testPackage).resolve("playwright/package.json")).resolve("playwright-core/package.json");
    const browsers = (JSON.parse(readFileSync(join(dirname(corePackage), "browsers.json"), "utf8")) as BrowsersJson).browsers;
    const chromium = shipped(browsers, "chromium");
    if (!chromium) return null;
    const executablePath = executablePathOf(createRequire(corePackage)(dirname(corePackage)));
    const root = executablePath ? browsersRoot(executablePath) : null;
    const headlessShell = shipped(browsers, "chromium-headless-shell");
    return {
      version, chromium, headlessShell, executablePath,
      fullInstalled: !!executablePath && existsSync(executablePath),
      shellInstalled: !!root && !!headlessShell && existsSync(join(root, `chromium_headless_shell-${headlessShell.revision}`)),
    };
  } catch {
    return null;
  }
}

function executablePathOf(core: { chromium?: { executablePath?: () => string } }): string | null {
  try { return core.chromium?.executablePath?.() || null; } catch { return null; }
}

/** The directory Playwright keeps its browsers in: the parent of the `chromium-<revision>` directory the full Chromium's path runs through. */
export function browsersRoot(executablePath: string): string | null {
  let dir = dirname(executablePath);
  while (dirname(dir) !== dir) {
    if (/^chromium-\d+$/.test(basename(dir))) return dirname(dir);
    dir = dirname(dir);
  }
  return null;
}

/** The part of a project's `use` that decides which browser it launches. */
export interface BrowserChoice { channel?: string; executablePath?: string; headless?: boolean }

export interface Verdict { ok: boolean; why: string }

/**
 * Whether the companion extension can be expected to load in the browser this launch gives. It loads in the full Chromium, which is Playwright's own for a launch the team has left to Playwright
 * (no channel, no executablePath) once `npx playwright install chromium` has run without `--only-shell`. It does not load in the headless shell, in the old headless mode, or in a branded browser.
 * Anything the team chose itself is not assumed to load it: the DevTools source runs there instead, and ANNOUNCEMENT_EMULATOR_TREE=extension still forces the other.
 */
export function extensionVerdict(playwright: PlaywrightChromium | null, launch: BrowserChoice = {}): Verdict {
  if (!playwright) return { ok: false, why: "the team's @playwright/test could not be read" };
  if (launch.executablePath) return { ok: false, why: "the launch sets its own executablePath, and nothing says that browser loads the extension" };
  if (launch.channel && launch.channel !== "chromium") return { ok: false, why: `the launch sets channel "${launch.channel}", and nothing says that browser loads the extension` };
  if (!playwright.fullInstalled) {
    return { ok: false, why: `Playwright's full Chromium ${playwright.chromium.build} is not installed (the headless shell loads no extension): run npx playwright install chromium, without --only-shell` };
  }
  if (launch.headless !== false && !playwright.headlessShell && launch.channel !== "chromium") {
    return { ok: false, why: `Playwright ${playwright.version} runs headless in the old headless mode, which loads no extension (1.49 and later can run the full Chromium headless)` };
  }
  return { ok: true, why: `Playwright ${playwright.version}'s full Chromium ${playwright.chromium.build}` };
}

/**
 * The channel to add to a launch so that it runs the full Chromium and not the headless shell: "chromium", for a launch left to Playwright that loads the extension and is headless. Headed
 * launches already run the full Chromium, and a launch the team has chosen is not changed.
 */
export function launchChannel(playwright: PlaywrightChromium | null, launch: BrowserChoice = {}): "chromium" | undefined {
  const left = !launch.channel && !launch.executablePath;
  return left && launch.headless !== false && !!playwright?.headlessShell && extensionVerdict(playwright, launch).ok ? "chromium" : undefined;
}
