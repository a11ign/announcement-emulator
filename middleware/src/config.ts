import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { PlaywrightTestConfig, ReporterDescription } from "@playwright/test";
import { BundleMissing, findBundle, layout } from "./bundle.ts";
import { browserArgs, type TreeOption } from "./extension.ts";
import { readPins } from "./pins.ts";
import { extensionVerdict, launchChannel, readPlaywright, type BrowserChoice, type PlaywrightChromium, type Verdict } from "./playwright-chromium.ts";
import { readRun, type RunEnv } from "./run.ts";

export interface Options {
  /** Run the structural sweep at each new state (default true). */
  sweeps?: boolean;
  /** Check every dump the extension makes against one read from scratch (the tests turn it on). */
  verify?: boolean;
  /**
   * Where the accessibility tree comes from. `"auto"` (the default): the extension on Linux and Windows, the DevTools port on macOS and wherever the extension cannot be expected to load, with a
   * switch to the DevTools port at run time if the extension does not come up. `"extension"` or `"devtools"` forces that source and never switches. It wins over `ANNOUNCEMENT_EMULATOR_TREE`,
   * and the reports say so.
   */
  tree?: TreeOption;
}

type Use = NonNullable<PlaywrightTestConfig["use"]>;
type Launch = NonNullable<Use["launchOptions"]>;

/**
 * The one line: `export default defineConfig(withAnnouncements(config))`.
 *
 * It adds a reporter (which starts the runtime for each worker and attaches the predicted speech to each test's report), and, for each chromium project, the launch options the emulator needs.
 * The browser is the team's: Playwright's own Chromium, the one `npx playwright install chromium` installed. Nothing here names a browser, except that a headless launch left to Playwright
 * is given `channel: "chromium"` where the extension is the tree source, because the headless shell loads no extension. It changes nothing in a test and in no other part of the config.
 * Firefox and WebKit projects are left alone: the emulator reads Chrome's tree.
 */
export function withAnnouncements<T extends PlaywrightTestConfig>(config: T, options: Options = {}): T {
  return announce(config, options, readPlaywright());
}

/** `withAnnouncements` for a Playwright already read: the tests give it the facts of a Playwright they made up. */
export function announce<T extends PlaywrightTestConfig>(config: T, options: Options, playwright: PlaywrightChromium | null): T {
  const pins = readPins();
  const bundle = findBundle(pins.version);
  if (!bundle) throw new BundleMissing(pins.version);
  const run = readRun();
  const reporter = fileURLToPath(new URL("./reporter.mjs", import.meta.url));
  // A channel set on the config's `use` is inherited by every project, a firefox one included, which would refuse it: it is added there only when every project is chromium.
  const topLevel: AttachContext = { bundle, run, playwright, addChannel: everyProjectIsChromium(config) };
  return {
    ...config,
    reporter: [[reporter, { bundle, extension: extensionFor(config, playwright), ...options }], ...reportersOf(config)],
    use: config.use ? attach(config.use, undefined, topLevel) : config.use,
    projects: config.projects?.map((project) => (project.use ? { ...project, use: attach(project.use, config.use, { ...topLevel, addChannel: true }) } : project)),
  };
}

/** What `attach` needs of the run: the bundle, what the reporter published for the workers (null outside a worker), the team's Playwright, and whether this `use` may be given a channel. */
interface AttachContext { bundle: string; run: RunEnv | null; playwright: PlaywrightChromium | null; addChannel: boolean }

/** A project's `use` over the config's, as Playwright merges them: shallowly, and a value that is undefined does not override. */
function mergedUse(use: Use, inherited: Use | undefined): Use {
  return { ...inherited, ...Object.fromEntries(Object.entries(use).filter(([, value]) => value !== undefined)) };
}

/** What a project launches with. */
function choiceOf(use: Use, inherited: Use | undefined): BrowserChoice {
  const merged = mergedUse(use, inherited);
  const launchOptions = merged.launchOptions ?? {};
  return { channel: merged.channel ?? launchOptions.channel, executablePath: launchOptions.executablePath, headless: merged.headless ?? launchOptions.headless };
}

/** `browserName`, or the `defaultBrowserType` a `devices[...]` descriptor carries in its place. */
function isChromium(use: Use): boolean {
  const { browserName, defaultBrowserType } = use as { browserName?: string; defaultBrowserType?: string };
  const browser = browserName ?? defaultBrowserType;
  return !browser || browser === "chromium";
}

const projectUses = (config: PlaywrightTestConfig): (Use | undefined)[] => (config.projects?.length ? config.projects.map((project) => project.use) : [undefined]);
const everyProjectIsChromium = (config: PlaywrightTestConfig): boolean => projectUses(config).every((use) => isChromium(mergedUse(use ?? {}, config.use)));

/**
 * Whether the extension can be expected to load in every chromium project of the config, and if not, why not: the reporter picks the tree source with it, and the source is one for the run.
 * A project that has no `use` of its own and shares the config's with a firefox or webkit project is not given a channel, so the headless shell would run it.
 */
function extensionFor(config: PlaywrightTestConfig, playwright: PlaywrightChromium | null): Verdict {
  const chromium = projectUses(config).filter((use) => isChromium(mergedUse(use ?? {}, config.use)));
  if (!everyProjectIsChromium(config) && chromium.some((use) => !use)) return { ok: false, why: "a chromium project shares its launch with the config's other browsers, and a channel for it cannot be added without breaking theirs" };
  const verdicts = chromium.map((use) => extensionVerdict(playwright, choiceOf(use ?? {}, config.use)));
  return verdicts.find((verdict) => !verdict.ok) ?? { ok: true, why: "every chromium project is left to Playwright's own Chromium" };
}

function reportersOf(config: PlaywrightTestConfig): ReporterDescription[] {
  const given = config.reporter;
  if (given === undefined) return [[process.env.CI ? "dot" : "list"]];
  if (typeof given === "string") return [[given] as ReporterDescription];
  if (typeof given[0] === "string") return [given as unknown as ReporterDescription];
  return given as ReporterDescription[];
}

/**
 * The `use` of a worker the emulator is attached to: only inside a worker (the reporter has published the run, and the worker has an index) and only for chromium. The browser is not named:
 * `inherited` is the config's `use`, which a project's own is read over, so that a channel or executablePath the team set at the top is seen from a project.
 */
function attach(use: Use, inherited: Use | undefined, { bundle, run, playwright, addChannel }: AttachContext): Use {
  const index = Number(process.env.TEST_PARALLEL_INDEX ?? NaN);
  if (!run || Number.isNaN(index) || !isChromium(mergedUse(use, inherited))) return use;
  const files = layout(bundle);
  const extensionId = readFileSync(files.extensionId, "utf8").trim();
  const given: Launch = use.launchOptions ?? {};
  const launchOptions: Launch = {
    ...given,
    args: [...(given.args ?? []), ...browserArgs(run.extensions[index] ?? "", extensionId, run.ports[index]!, run.tree)],
    ignoreDefaultArgs: run.tree === "devtools" ? given.ignoreDefaultArgs : ignoring(given.ignoreDefaultArgs, "--disable-extensions"),
  };
  const channel = run.tree === "extension" && addChannel ? launchChannel(playwright, choiceOf(use, inherited)) : undefined;
  return { ...use, ...(channel ? { channel } : {}), launchOptions };
}

/** Playwright adds `--disable-extensions` to every launch; the emulator's extension is one. */
export function ignoring(given: Launch["ignoreDefaultArgs"], flag: string): Launch["ignoreDefaultArgs"] {
  if (given === true) return true;
  return [...new Set([...(Array.isArray(given) ? given : []), flag])];
}
