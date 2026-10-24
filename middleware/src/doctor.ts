import { spawnSync } from "node:child_process";
import { BundleMissing, findBundle, layout, platformId, readManifest } from "./bundle.ts";
import { pickTree } from "./extension.ts";
import { readPins } from "./pins.ts";
import { extensionVerdict, readPlaywright, type PlaywrightChromium } from "./playwright-chromium.ts";
import { buildFor, percent, readSupported, SOURCE_KEYS, type SupportedVersions } from "./supported.ts";

export interface DoctorOptions {
  /** Where the team's `@playwright/test` is resolved from: the directory the command is run in. */
  from?: string;
  env?: NodeJS.ProcessEnv;
  platform?: string;
  playwright?: PlaywrightChromium | null;
  /** Starts a browser to ask its version; the tests give it a made-up one. */
  version?: (executable: string) => { status: number | null; out: string };
  supported?: SupportedVersions;
  log?: (line: string) => void;
}

/**
 * Says what the middleware will run in, and whether that is measured: the team's Playwright, the Chromium its `browsers.json` names and whether it is installed, whether that build is on the
 * supported list (and its figures if it is), and the tree source the automatic pick takes. It exits 0 for a build that is not listed, because that build runs (its report says "agreement not
 * measured"); it fails for what stops a run: no Playwright, no Chromium installed, no runtime bundle, no Python.
 */
export function doctor(options: DoctorOptions = {}): number {
  const log = options.log ?? ((line: string) => console.log(line));
  const pins = readPins();
  let failed = 0;
  const fail = (line: string) => { failed += 1; log(`FAIL ${line}`); };
  log(`package ${pins.version}, platform ${platformId()}`);
  checkPlaywright(options, log, fail);
  checkBundle(findBundle(pins.version, options.env ?? process.env), pins.version, log, fail);
  return failed ? 1 : 0;
}

type Log = (line: string) => void;

function checkPlaywright(options: DoctorOptions, log: Log, fail: Log): void {
  const playwright = options.playwright === undefined ? readPlaywright(...(options.from ? [options.from] : [])) : options.playwright;
  if (!playwright) { fail("Playwright: @playwright/test is not installed here, or its browsers.json could not be read. Run: npm i -D @playwright/test"); return; }
  reportPlaywright(playwright, options.supported ?? readSupported(), { env: options.env ?? process.env, platform: options.platform ?? process.platform, log, fail });
  if (playwright.fullInstalled && playwright.executablePath) checkStarts(playwright.executablePath, options.version ?? browserVersion, log, fail);
}

function checkBundle(bundle: string | null, version: string, log: Log, fail: Log): void {
  if (!bundle) { fail(new BundleMissing(version).message); return; }
  const manifest = readManifest(bundle);
  log(`bundle ${bundle}\nNVDA ${manifest.nvda.release} (${manifest.nvda.commit})  Chromium ${manifest.chromiumTables} mapping tables  Python ${manifest.python}  commit ${manifest.commit}`);
  const out = spawnSync(layout(bundle).python, ["-I", "-c", "import sys; print(sys.version.split()[0])"], { encoding: "utf8" });
  if (out.status === 0) log(`ok   python: ${out.stdout.trim()}`); else fail(`python: ${(out.stdout || out.stderr || String(out.error)).trim().split("\n")[0]}`);
}

function browserVersion(executable: string): { status: number | null; out: string } {
  const run = spawnSync(executable, ["--version"], { encoding: "utf8" });
  return { status: run.status, out: (run.stdout || run.stderr || String(run.error ?? "")).trim().split("\n")[0] ?? "" };
}

/** The browser Playwright installed starts: a minimal host without the libraries it needs is found here, and not by every test failing at launch (Playwright's `--with-deps` installs them). */
function checkStarts(executable: string, version: (executable: string) => { status: number | null; out: string }, log: Log, fail: Log): void {
  const { status, out } = version(executable);
  if (status === 0) log(`ok   chromium starts: ${out}`); else fail(`chromium does not start: ${out}. On Linux, npx playwright install --with-deps chromium installs the libraries it needs`);
}

interface Where { env: NodeJS.ProcessEnv; platform: string; log: Log; fail: Log }

function reportPlaywright(pw: PlaywrightChromium, supported: SupportedVersions, { env, platform, log, fail }: Where): void {
  log(`Playwright ${pw.version}`);
  log(`Chromium ${pw.chromium.build} (revision ${pw.chromium.revision}): ${pw.fullInstalled ? "installed" : "NOT installed"}`);
  log(`headless shell ${pw.headlessShell ? `${pw.headlessShell.build}: ${pw.shellInstalled ? "installed" : "NOT installed"}` : "none (Playwright before 1.49 has none)"}`);
  if (!pw.fullInstalled && !pw.shellInstalled) fail("Chromium: neither the browser nor the headless shell is installed. Run: npx playwright install chromium");
  const listed = buildFor(supported, pw.chromium.build);
  if (listed) {
    log(`supported: yes, Chromium ${listed.chromium} is on the list (Playwright ${listed.playwright.join(", ")})`);
    for (const key of SOURCE_KEYS) {
      const f = listed.measured[key];
      log(f ? `  ${key}: ${percent(f.agreement)} of ${f.units} units, ${f.date} (${f.figure})` : `  ${key}: not measured`);
    }
  } else {
    log(`supported: no. Chromium ${pw.chromium.build} is not on the list, so a report says "agreement not measured for Chromium ${pw.chromium.build}". It runs all the same.`);
  }
  const pick = pickTree(platform, env, extensionVerdict(pw));
  log(`tree source: ${pick.source} for a launch left to Playwright (${pick.why})`);
}
