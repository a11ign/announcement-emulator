import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { PlaywrightTestConfig, ReporterDescription } from "@playwright/test";
import { BundleMissing, findBundle, layout } from "./bundle.ts";
import { browserArgs } from "./extension.ts";
import { readPins } from "./pins.ts";
import { readRun, type RunEnv } from "./run.ts";

export interface Options {
  /** Run the structural sweep at each new state (default true). */
  sweeps?: boolean;
  /** Check every dump the extension makes against one read from scratch (the tests turn it on). */
  verify?: boolean;
}

type Use = NonNullable<PlaywrightTestConfig["use"]>;
type Launch = NonNullable<Use["launchOptions"]>;

/**
 * The one line: `export default defineConfig(withAnnouncements(config))`.
 *
 * It adds a reporter (which starts the runtime for each worker and attaches the predicted speech to each test's report), and, for each chromium project, the launch options the emulator's
 * browser needs. It changes nothing in a test and in no other part of the config. Firefox and WebKit projects are left alone: the emulator reads Chrome's tree.
 */
export function withAnnouncements<T extends PlaywrightTestConfig>(config: T, options: Options = {}): T {
  const pins = readPins();
  const bundle = findBundle(pins.version);
  if (!bundle) throw new BundleMissing(pins.version);
  const run = readRun();
  const reporter = fileURLToPath(new URL("./reporter.mjs", import.meta.url));
  return {
    ...config,
    reporter: [[reporter, { bundle, ...options }], ...reportersOf(config)],
    use: config.use ? attach(config.use, bundle, run) : config.use,
    projects: config.projects?.map((project) => (project.use ? { ...project, use: attach(project.use, bundle, run) } : project)),
  };
}

function reportersOf(config: PlaywrightTestConfig): ReporterDescription[] {
  const given = config.reporter;
  if (given === undefined) return [[process.env.CI ? "dot" : "list"]];
  if (typeof given === "string") return [[given] as ReporterDescription];
  if (typeof given[0] === "string") return [given as unknown as ReporterDescription];
  return given as ReporterDescription[];
}

/** The `use` of a worker with the emulator's browser: only inside a worker (the reporter has published the run, and the worker has an index) and only for chromium. */
function attach(use: Use, bundle: string, run: RunEnv | null): Use {
  const browser = (use as { browserName?: string }).browserName;
  const index = Number(process.env.TEST_PARALLEL_INDEX ?? NaN);
  if (!run || Number.isNaN(index) || (browser && browser !== "chromium")) return use;
  const files = layout(bundle);
  const extensionId = readFileSync(files.extensionId, "utf8").trim();
  const given: Launch = use.launchOptions ?? {};
  const launchOptions: Launch = {
    ...given,
    executablePath: files.chrome,
    args: [...(given.args ?? []), ...browserArgs(run.extensions[index]!, extensionId, run.ports[index]!)],
    ignoreDefaultArgs: ignoring(given.ignoreDefaultArgs, "--disable-extensions"),
    env: { ...(given.env as Record<string, string> | undefined), ...(process.platform === "linux" ? { LD_LIBRARY_PATH: libraryPath(files.libs, given.env as Record<string, string> | undefined) } : {}) },
  };
  return { ...use, channel: undefined, launchOptions };
}

/** Playwright adds `--disable-extensions` to every launch; the emulator's extension is one. */
export function ignoring(given: Launch["ignoreDefaultArgs"], flag: string): Launch["ignoreDefaultArgs"] {
  if (given === true) return true;
  return [...new Set([...(Array.isArray(given) ? given : []), flag])];
}

function libraryPath(libs: string, env: Record<string, string> | undefined): string {
  return [libs, env?.LD_LIBRARY_PATH ?? process.env.LD_LIBRARY_PATH].filter(Boolean).join(":");
}

