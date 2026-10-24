import { spawn, type ChildProcess } from "node:child_process";
import { mkdirSync, openSync } from "node:fs";
import { createInterface } from "node:readline";
import { dirname } from "node:path";
import { layout } from "./bundle.ts";
import type { BrowserPorts, TreeSource } from "./extension.ts";

/** One thing the runtime predicted or noticed. `kind` is speech, observe, sweep, flag, error or verify; `t` is the page's clock in ms, as Playwright's is. */
export interface RuntimeRecord { kind: string; t: number; [field: string]: unknown }
export interface DrainStats { snapshots: number; speechMs: number; sweepMs: number[]; keys: number; skippedSweeps: number; lostSnapshots: number }

/**
 * The runtime, as a separate process (ADR 0047, Decision 3): this file starts it with the bundle's own Python and reads the JSON lines it writes. It imports nothing from it.
 * One runtime serves one Playwright worker, because NVDA's state is one per process.
 */
export class Runtime {
  readonly records: RuntimeRecord[] = [];
  bootMs = 0;
  private readonly child: ChildProcess;
  private readonly waiting = new Map<number, (stats: DrainStats) => void>();
  private nextId = 0;
  readonly ready: Promise<number>;
  /** Why the runtime is not running, if it is not: the middleware must never fail a test run for the sake of a prediction. */
  failure: string | null = null;

  readonly ports: BrowserPorts;

  constructor(bundle: string, ports: BrowserPorts, options: { sweeps?: boolean; log?: string; tree?: TreeSource } = {}) {
    this.ports = ports;
    const files = layout(bundle);
    if (options.log) mkdirSync(dirname(options.log), { recursive: true });
    const stderr = options.log ? openSync(options.log, "w") : "ignore";
    this.child = spawn(files.python, ["-I", files.runtime, "--port", String(ports.collector), "--cdp", String(ports.cdp), "--tree", options.tree ?? "extension", ...(options.sweeps === false ? ["--no-sweeps"] : []), ...(process.env.ANNOUNCEMENT_EMULATOR_REPORT_FOCUS ? ["--report-focus"] : [])], {
      env: { ...process.env, EMU_DOWNLOADS: bundle, PYTHONDONTWRITEBYTECODE: "1", PYTHONUTF8: "1" },
      stdio: ["pipe", "pipe", stderr],
    });
    let onReady: (ms: number) => void = () => {};
    this.ready = new Promise((resolve, reject) => { onReady = resolve; this.child.once("error", reject); this.child.once("exit", (code) => reject(new Error(`the runtime exited ${code} before it was ready`))); });
    this.ready.catch((error: Error) => { this.failure = error.message; });
    createInterface({ input: this.child.stdout! }).on("line", (line) => this.onLine(line, onReady));
  }

  private onLine(line: string, onReady: (ms: number) => void): void {
    let message: { type: string; [k: string]: unknown };
    try { message = JSON.parse(line); } catch { return; }
    if (message.type === "ready") { this.bootMs = message.bootMs as number; onReady(this.bootMs); }
    else if (message.type === "record") this.records.push(message.rec as RuntimeRecord);
    else if (message.type === "drained") this.waiting.get(message.id as number)?.(message.stats as DrainStats);
  }

  /** Ask the runtime to finish what the browser has told it, run the sweeps that wait and derive the flags; resolves with its counts. */
  drain(): Promise<DrainStats> {
    if (this.failure || this.child.exitCode !== null) return Promise.resolve({ snapshots: 0, speechMs: 0, sweepMs: [], keys: 0, skippedSweeps: 0, lostSnapshots: 0 });
    const id = (this.nextId += 1);
    return new Promise((resolve) => { this.waiting.set(id, resolve); this.child.stdin!.write(`${JSON.stringify({ cmd: "drain", id })}\n`); });
  }

  async stop(): Promise<void> {
    if (this.child.exitCode !== null) return;
    this.child.stdin!.write(`${JSON.stringify({ cmd: "quit" })}\n`);
    await new Promise<void>((resolve) => { const t = setTimeout(() => { this.child.kill("SIGKILL"); resolve(); }, 3000); this.child.once("exit", () => { clearTimeout(t); resolve(); }); });
  }
}

