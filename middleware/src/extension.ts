import { cpSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { layout } from "./bundle.ts";
import type { Verdict } from "./playwright-chromium.ts";

/**
 * A private copy of the companion extension for one runtime. The copy's manifest names `passive.js` as its service worker (the extension in the bundle keeps `bg.js`, which a session
 * of `emu/session.mjs` uses), and `passive.js` has the runtime's port written into it. Nothing in the bundle is changed.
 */
export function prepareExtension(bundle: string, dest: string, port: number, verify = false): string {
  rmSync(dest, { recursive: true, force: true });
  cpSync(layout(bundle).extension, dest, { recursive: true });
  const manifestPath = join(dest, "manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  manifest.background = { service_worker: "passive.js" };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  const workerPath = join(dest, "passive.js");
  writeFileSync(workerPath, readFileSync(workerPath, "utf8").replaceAll("__PORT__", String(port)).replaceAll("__VERIFY__", verify ? "1" : "0"));
  return dest;
}

export interface BrowserPorts { collector: number; cdp: number }

/**
 * Where the accessibility tree comes from. `extension`: the companion extension reads it with chrome.automation (a Linux, Windows or ChromeOS browser has a desktop tree to read it from).
 * `devtools`: the runtime reads it through the DevTools port (`Accessibility.getFullAXTree` and `DOMSnapshot`), the source ADR 0047 allows as a fallback (what each source agreed with a real NVDA is in tree-rates.ts). macOS gets the second because
 * `chrome.automation.getDesktop` never answers there (docs/playwright-middleware-spike.md, Q7). The `tree` option of `withAnnouncements` and `ANNOUNCEMENT_EMULATOR_TREE` set it by hand.
 */
export type TreeSource = "extension" | "devtools";

/** What `withAnnouncements` is given to choose the tree source: `auto` (the default) lets the middleware pick, the others force one. */
export type TreeOption = "auto" | TreeSource;

/** Where the tree comes from, and why: what the report says. `forced` is set by the option or the environment, and the runtime does not fall back from a forced source. */
export interface TreePick { source: TreeSource; why: string; forced: boolean }

const isSource = (value: unknown): value is TreeSource => value === "extension" || value === "devtools";

/**
 * The option decides when it names a source, then the environment (`ANNOUNCEMENT_EMULATOR_TREE`, the same option for CI and the measurement). When both name one, the option wins and the
 * reason says the environment was set and not used. Otherwise macOS reads through the DevTools port, and so does a launch the extension cannot be expected to load in (`extension.ok` false: the
 * team chose its own browser, or Playwright's full Chromium is not installed). Anywhere else the extension is the default, and where it is not forced the runtime reads the trees through the
 * DevTools port instead if the extension does not come up (runtime/fallback.py). No setup is broken by this: the DevTools source runs in any Chromium.
 */
export function pickTree(platform: string = process.platform, env: NodeJS.ProcessEnv = process.env, extension: Verdict = { ok: true, why: "" }, option?: TreeOption): TreePick {
  const fromEnv = isSource(env.ANNOUNCEMENT_EMULATOR_TREE) ? env.ANNOUNCEMENT_EMULATOR_TREE : null;
  if (isSource(option)) {
    const ignored = fromEnv ? ` (ANNOUNCEMENT_EMULATOR_TREE=${fromEnv} is set and is not used: the option wins)` : "";
    return { source: option, why: `the tree option is "${option}"${ignored}`, forced: true };
  }
  if (fromEnv) return { source: fromEnv, why: `ANNOUNCEMENT_EMULATOR_TREE=${fromEnv}`, forced: true };
  const ignored = option === undefined || option === "auto" ? "" : ` (the tree option ${JSON.stringify(option)} is not auto, extension or devtools: ignored)`;
  if (platform === "darwin") return { source: "devtools", why: `macOS gives the extension no desktop tree${ignored}`, forced: false };
  if (!extension.ok) return { source: "devtools", why: `the extension was not used: ${extension.why}${ignored}`, forced: false };
  return { source: "extension", why: `the default where the browser gives the extension a desktop tree${ignored}`, forced: false };
}

/** How long the runtime waits, after the first page, for an extension that has said nothing before it reads the trees through the DevTools port (seconds; 0 where the source is forced). The extension is up a fraction of a second after the first page on an ordinary host. */
export const EXTENSION_WAIT_S = 5;
export function extensionWait(pick: TreePick, env: NodeJS.ProcessEnv = process.env): number {
  if (pick.forced || pick.source !== "extension") return 0;
  const given = Number(env.ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT);
  return Number.isFinite(given) && given >= 0 && env.ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT ? given : EXTENSION_WAIT_S;
}

export const treeSource = (platform: string = process.platform, env: NodeJS.ProcessEnv = process.env, option?: TreeOption): TreeSource => pickTree(platform, env, undefined, option).source;

/**
 * The flags the emulator's browser needs, which the ticket names (`--force-renderer-accessibility`, `--load-extension`, `--allowlisted-extension-id`) and two more:
 * `--disable-features=DisableLoadExtensionCommandLineSwitch`, without which Chrome 155 ignores `--load-extension` (emu/session.mjs passes it), and `--remote-debugging-port`, the second
 * door to the browser that cdp.py reads keys through (Playwright keeps its own, a pipe). The `--disable-features` flag replaces the one Playwright passes: Chrome takes the last.
 */
export function browserArgs(extensionDir: string, extensionId: string, ports: BrowserPorts, tree: TreeSource = "extension"): string[] {
  if (tree === "devtools") return ["--force-renderer-accessibility", `--remote-debugging-port=${ports.cdp}`];      // no extension: the tree comes through the port
  return [
    "--force-renderer-accessibility",
    `--load-extension=${extensionDir}`,
    `--allowlisted-extension-id=${extensionId}`,
    "--disable-features=DisableLoadExtensionCommandLineSwitch",
    `--remote-debugging-port=${ports.cdp}`,
  ];
}
