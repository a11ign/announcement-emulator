// A11-279: the middleware tests make about 15,000 folders in /tmp (`ae-*`) and never remove them. On 2026-10-25 a host with /tmp at
// 19,960 entries stalled in an ext4 directory read for 26 s and rebooted, killing every run on it. This is rstest's globalSetup: it
// makes ONE private directory for the whole run, points TMPDIR at it before the workers fork (rstest hands a globalSetup's
// environment changes to every worker), and removes it when the run ends. Every `tmpdir()` in the tests then lands inside it, so no
// test is edited and /tmp gains nothing.
import { mkdirSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join, resolve } from "node:path";

export const RUN_PREFIX = "ae-run-";

/**
 * Where a run's directory is made: A11Y_PRIVATE_TMP_BASE when set, else `~/.cache/a11ign/tmp` (agent-org's default too). NOT a folder inside
 * this package: `readPlaywright` and the bundle lookups resolve upward from a test's temp directory, so under `middleware/` they would find
 * this package's own `node_modules` and the "no Playwright here" tests (playwright-chromium.test.ts) would read a Playwright that is not theirs.
 */
export function privateBase(env = process.env) {
  return env.A11Y_PRIVATE_TMP_BASE ? resolve(env.A11Y_PRIVATE_TMP_BASE) : join(homedir(), ".cache", "a11ign", "tmp");
}

/** Makes `<base>/ae-run-<UTC stamp>-<pid>` and returns its path. The pid keeps two runs at the same second apart. */
export function makeRunTmp({ env = process.env, now = new Date(), pid = process.pid } = {}) {
  const stamp = now.toISOString().replaceAll(/[:.]/g, "-");
  const dir = join(privateBase(env), `${RUN_PREFIX}${stamp}-${pid}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

/** Removes a directory `makeRunTmp` made, and nothing else: a path not named `ae-run-*` is refused. */
export function removeRunTmp(dir) {
  if (!basename(dir).startsWith(RUN_PREFIX)) throw new Error(`refusing to remove ${dir}: not an ${RUN_PREFIX}* directory`);
  rmSync(dir, { recursive: true, force: true });
}

let made = null;

export function setup() {
  made = makeRunTmp();
  process.env.TMPDIR = made;
}

export function teardown() {
  if (made) removeRunTmp(made);
  made = null;
}
