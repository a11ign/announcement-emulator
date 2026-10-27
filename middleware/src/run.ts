import type { BrowserPorts } from "./launch.ts";

/** What the reporter (in Playwright's main process) tells the config (loaded again in each worker) through the environment: the workers are started after it has set it. */
export interface RunEnv { bundle: string; dir: string; ports: BrowserPorts[]; verify: boolean; sweeps: boolean }

export const RUN_ENV = "ANNOUNCEMENT_EMULATOR_RUN";

export function readRun(env: NodeJS.ProcessEnv = process.env): RunEnv | null {
  const text = env[RUN_ENV];
  return text ? (JSON.parse(text) as RunEnv) : null;
}

export function publishRun(run: RunEnv, env: NodeJS.ProcessEnv = process.env): void {
  env[RUN_ENV] = JSON.stringify(run);
}
