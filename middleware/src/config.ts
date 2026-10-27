import { fileURLToPath } from "node:url";
import type { PlaywrightTestConfig, ReporterDescription } from "@playwright/test";
import { BundleMissing, findBundle } from "./bundle.ts";
import { browserArgs } from "./launch.ts";
import { readPins } from "./pins.ts";
import { readRun, type RunEnv } from "./run.ts";

export interface Options {
  /** Run the structural sweep at each new state (default true). */
  sweeps?: boolean;
  /** Check every incremental read of a page's accessibility tree against one made from scratch, and say where they differ (the tests turn it on). */
  verify?: boolean;
}

type Use = NonNullable<PlaywrightTestConfig["use"]>;
type Launch = NonNullable<Use["launchOptions"]>;

/**
 * The one line: `export default defineConfig(withAnnouncements(config))`.
 *
 * It adds a reporter (which starts the runtime for each worker and attaches the predicted speech to each test's report), and, for each chromium project, the launch flags the emulator needs.
 * The browser is the team's: whichever one the config launches, Playwright's own Chromium or its headless shell, a channel or an executablePath. The accessibility tree is read through the browser's DevTools port, so
 * nothing here loads an extension, names a browser or changes how a test opens its pages or its contexts. It changes nothing in a test and in no other part of the config.
 * Firefox and WebKit projects are left alone: the emulator reads Chrome's tree.
 */
export function withAnnouncements<T extends PlaywrightTestConfig>(config: T, options: Options = {}): T {
  return announce(config, options);
}

/** `withAnnouncements`, named for the tests that call it with the environment they made up. */
export function announce<T extends PlaywrightTestConfig>(config: T, options: Options = {}): T {
  const pins = readPins();
  const bundle = findBundle(pins.version);
  if (!bundle) throw new BundleMissing(pins.version);
  const run = readRun();
  const reporter = fileURLToPath(new URL("./reporter.mjs", import.meta.url));
  return {
    ...config,
    reporter: [[reporter, { bundle, ...options }], ...reportersOf(config)],
    use: config.use ? attach(config.use, undefined, run) : config.use,
    projects: config.projects?.map((project) => (project.use ? { ...project, use: attach(project.use, config.use, run) } : project)),
  };
}

/** A project's `use` over the config's, as Playwright merges them: shallowly, and a value that is undefined does not override. */
function mergedUse(use: Use, inherited: Use | undefined): Use {
  return { ...inherited, ...Object.fromEntries(Object.entries(use).filter(([, value]) => value !== undefined)) };
}

/** `browserName`, or the `defaultBrowserType` a `devices[...]` descriptor carries in its place. */
function isChromium(use: Use): boolean {
  const { browserName, defaultBrowserType } = use as { browserName?: string; defaultBrowserType?: string };
  const browser = browserName ?? defaultBrowserType;
  return !browser || browser === "chromium";
}

function reportersOf(config: PlaywrightTestConfig): ReporterDescription[] {
  const given = config.reporter;
  if (given === undefined) return [[process.env.CI ? "dot" : "list"]];
  if (typeof given === "string") return [[given] as ReporterDescription];
  if (typeof given[0] === "string") return [given as unknown as ReporterDescription];
  return given as ReporterDescription[];
}

/**
 * The `use` of a worker the emulator is attached to: only inside a worker (the reporter has published the run, and the worker has an index) and only for chromium. `inherited` is the config's `use`, which a project's own
 * is read over, so that a project that says nothing of its browser is seen as the config's browser is.
 */
function attach(use: Use, inherited: Use | undefined, run: RunEnv | null): Use {
  const index = Number(process.env.TEST_PARALLEL_INDEX ?? NaN);
  if (!run || Number.isNaN(index) || !isChromium(mergedUse(use, inherited))) return use;
  const given: Launch = use.launchOptions ?? {};
  return { ...use, launchOptions: { ...given, args: [...(given.args ?? []), ...browserArgs(run.ports[index]!)] } };
}
