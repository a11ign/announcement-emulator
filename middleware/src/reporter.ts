import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { FullConfig, Reporter, TestCase, TestResult } from "@playwright/test/reporter";
import { readManifest } from "./bundle.ts";
import { annotationsFor, assign, attachments, browserBuild, describe, type Window } from "./format.ts";
import { pickTree, prepareExtension, type TreeSource } from "./extension.ts";
import { freePorts } from "./ports.ts";
import type { Verdict } from "./playwright-chromium.ts";
import { publishRun } from "./run.ts";
import { Runtime, type DrainStats } from "./runtime.ts";
import { agreementFor, readSupported, type Agreement, type SupportedVersions } from "./supported.ts";

interface ReporterOptions { bundle: string; sweeps?: boolean; verify?: boolean; /** Whether the extension can be expected to load in the config's chromium projects (config.ts), and if not, why not. */ extension?: Verdict }
interface Seen { test: TestCase; result: TestResult; worker: number; window: Window }

/**
 * The part of the middleware that lives in Playwright's main process. It starts one runtime for each worker before the workers exist (they read their ports from the environment it sets),
 * notes when each test ran, and at the end asks every runtime for its predictions and attaches them to the tests they belong to.
 */
export default class AnnouncementsReporter implements Reporter {
  private runtimes: Runtime[] = [];
  private readonly seen: Seen[] = [];
  private dir = "";
  private tree: TreeSource = "extension";
  private treeWhy = "";
  private supported: SupportedVersions = { builds: [] };
  private started = 0;
  private readonly options: ReporterOptions;
  constructor(options: ReporterOptions) { this.options = options; }

  printsToStdio(): boolean { return false; }

  async onBegin(config: FullConfig): Promise<void> {
    this.started = Date.now();
    this.dir = join(config.configFile ? dirname(config.configFile) : config.rootDir, "test-results", "announcement-emulator");
    mkdirSync(this.dir, { recursive: true });
    const count = Math.max(1, config.workers);
    const numbers = await freePorts(count * 2);
    const ports = Array.from({ length: count }, (_, i) => ({ collector: numbers[2 * i]!, cdp: numbers[2 * i + 1]! }));
    const pick = pickTree(process.platform, process.env, this.options.extension);
    this.tree = pick.source; this.treeWhy = pick.why;
    this.supported = readSupported();
    const extensions = this.tree === "extension" ? ports.map((p, i) => prepareExtension(this.options.bundle, join(this.dir, `extension-${i}`), p.collector, this.options.verify)) : [];
    publishRun({ bundle: this.options.bundle, dir: this.dir, ports, extensions, verify: !!this.options.verify, sweeps: sweepsOn(this.options), tree: this.tree });
    this.runtimes = ports.map((p, i) => new Runtime(this.options.bundle, p, { sweeps: sweepsOn(this.options), log: join(this.dir, `runtime-${i}.log`), tree: this.tree }));
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const start = result.startTime.getTime();
    this.seen.push({ test, result, worker: result.parallelIndex, window: { title: test.titlePath().filter(Boolean).join(" > "), start, end: start + result.duration + 50 } });
  }

  async onEnd(): Promise<void> {
    const waited = Date.now();
    const stats = await Promise.all(this.runtimes.map(async (r) => { await r.ready.catch(() => 0); return r.drain(); }));
    for (const [i, r] of this.runtimes.entries()) if (r.failure) console.error(`announcement-emulator: runtime ${i} did not run (${r.failure}); see ${join(this.dir, `runtime-${i}.log`)}. No speech is attached for its tests.`);
    const drainMs = Date.now() - waited;
    const emulator = readManifestOrNull(this.options.bundle);
    let flagged = 0, unassigned = 0;
    this.runtimes.forEach((runtime, worker) => {
      const mine = this.seen.filter((s) => s.worker === worker);
      const agreement = this.agreement(runtime);
      const owned = assign(runtime.records.filter((rec) => rec.kind !== "start"), mine.map((s) => s.window));
      unassigned += owned.unassigned;
      for (const { test, result, window } of mine) {
        const output = describe(window, owned.byWindow.get(window) ?? [], emulator, { tree: this.tree, treeWhy: this.treeWhy, agreement });
        result.attachments.push(...attachments(output));
        test.annotations.push(...annotationsFor(output.flags));
        flagged += output.flags.length;
      }
    });
    this.write(stats, drainMs, flagged, unassigned);
    await Promise.all(this.runtimes.map((r) => r.stop()));
  }

  private agreement(runtime: Runtime): Agreement {
    return agreementFor(this.supported, browserBuild(runtime.records), this.tree);
  }

  /** When the browser's side came up, against when the worker's first test began: positive means the test began first, and what it did before then was not seen. */
  private startup(runtime: Runtime, worker: number): Record<string, number | string | null> {
    const first = Math.min(...this.seen.filter((s) => s.worker === worker).map((s) => s.window.start));
    const at = (what: string) => { const t = runtime.records.find((r) => r.kind === "start" && r.what === what)?.t; return t === undefined || !Number.isFinite(first) ? null : t - first; };
    const up = runtime.records.find((rec) => rec.kind === "start" && rec.what === "extension");
    return { treeSource: this.tree, treeSourceWhy: this.treeWhy, chromium: browserBuild(runtime.records), agreement: this.agreement(runtime).line, treeSourceUpAfterFirstTestStartedMs: at("tree-source"), extensionUpAfterFirstTestStartedMs: at("extension"), devtoolsAttachedAfterFirstTestStartedMs: at("devtools"), desktopChildrenWhenUp: (up?.desktopChildren as number | undefined) ?? null, chromeAutomationInWorker: (runtime.records.find((rec) => rec.kind === "start" && rec.what === "worker")?.automation as string | undefined) ?? null };
  }

  private write(stats: DrainStats[], drainMs: number, flagged: number, unassigned: number): void {
    this.runtimes.forEach((r, i) => writeFileSync(join(this.dir, `records-${i}.json`), JSON.stringify(r.records, null, 1)));
    const run = { label: "predicted NVDA speech: run summary", wallMs: Date.now() - this.started, drainMs, workers: this.runtimes.map((r, i) => ({ bootMs: r.bootMs, startup: this.startup(r, i), ...stats[i] })), tests: this.seen.length, flags: flagged, recordsOutsideAnyTest: unassigned };
    writeFileSync(join(this.dir, "run.json"), JSON.stringify(run, null, 2));
    console.log(`announcement-emulator: predicted NVDA speech attached to ${this.seen.length} tests, ${flagged} flags; the runtime waited ${drainMs} ms at the end (${join(this.dir, "run.json")})`);
  }
}

/** Sweeps are on unless the config or ANNOUNCEMENT_EMULATOR_SWEEPS=0 says not: the second is how the cost of a sweep is measured without editing the config. */
function sweepsOn(options: ReporterOptions): boolean {
  return options.sweeps !== false && process.env.ANNOUNCEMENT_EMULATOR_SWEEPS !== "0";
}

function readManifestOrNull(bundle: string) {
  try { return readManifest(bundle); } catch { return null; }
}

