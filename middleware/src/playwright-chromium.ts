import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** A browser build Playwright ships: the revision it downloads and the Chromium build that revision is. */
export interface ShippedBrowser { revision: string; build: string }

/** What the team's own Playwright says about the Chromium it installs, read once and shared by the config, the reporter and `doctor`. */
export interface PlaywrightChromium {
  /** `@playwright/test`'s version. */
  version: string;
  /** The full Chromium (`npx playwright install chromium`), from `playwright-core/browsers.json`. */
  chromium: ShippedBrowser;
  /** The headless shell, which Playwright 1.49 and later runs for a headless launch with no channel; null where `browsers.json` has none. */
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
 * The team's Playwright, resolved from the first of `from` that has one: by default the working directory (the directory of the config when Playwright is run from it), then where this package is
 * installed (a monorepo run from its root with `-c e2e/playwright.config.ts` has `@playwright/test` beside the package, not at the root). The Chromium that matters is the one the team's
 * `@playwright/test` installs. Null when none can be read; nothing here may break a run.
 */
export function readPlaywright(...from: string[]): PlaywrightChromium | null {
  for (const dir of from.length ? from : [process.cwd(), dirname(fileURLToPath(import.meta.url))]) {
    const found = readPlaywrightFrom(dir);
    if (found) return found;
  }
  return null;
}

function readPlaywrightFrom(from: string): PlaywrightChromium | null {
  try {
    const { version, corePackage } = locatePlaywright(from);
    const browsers = (JSON.parse(readFileSync(join(dirname(corePackage), "browsers.json"), "utf8")) as BrowsersJson).browsers;
    const chromium = shipped(browsers, "chromium");
    if (!chromium) return null;
    const headlessShell = shipped(browsers, "chromium-headless-shell");
    const executablePath = executablePathOf(createRequire(corePackage)(dirname(corePackage)));
    return { version, chromium, headlessShell, executablePath, ...installedAt(executablePath, headlessShell) };
  } catch {
    return null;
  }
}

/** The team's `@playwright/test` and the `playwright-core` it brings, found by the way Node would resolve them from the team's directory. */
function locatePlaywright(from: string): { version: string; corePackage: string } {
  const testPackage = createRequire(join(from, "noop.js")).resolve("@playwright/test/package.json");
  const version = (JSON.parse(readFileSync(testPackage, "utf8")) as { version: string }).version;
  const corePackage = createRequire(createRequire(testPackage).resolve("playwright/package.json")).resolve("playwright-core/package.json");
  return { version, corePackage };
}

function installedAt(executablePath: string | null, headlessShell: ShippedBrowser | null): { fullInstalled: boolean; shellInstalled: boolean } {
  const root = executablePath ? browsersRoot(executablePath) : null;
  return {
    fullInstalled: !!executablePath && existsSync(executablePath),
    shellInstalled: !!root && !!headlessShell && existsSync(join(root, `chromium_headless_shell-${headlessShell.revision}`)),
  };
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
