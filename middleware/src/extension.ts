import { cpSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { layout } from "./bundle.ts";

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
 * `devtools`: the runtime reads it through the DevTools port (`Accessibility.getFullAXTree` and `DOMSnapshot`), the lower-fidelity source ADR 0047 allows. macOS gets the second because
 * `chrome.automation.getDesktop` never answers there (docs/playwright-middleware-spike.md, Q7). `ANNOUNCEMENT_EMULATOR_TREE` sets it by hand.
 */
export type TreeSource = "extension" | "devtools";

/** Where the tree comes from, and why: what the report says when it is not the extension. */
export interface TreePick { source: TreeSource; why: string }

/**
 * The environment decides when it is set. Otherwise macOS reads through the DevTools port, and so does a launch the extension cannot be expected to load in (`extension.ok` false: the team chose
 * its own browser, or Playwright's full Chromium is not installed). Anywhere else the extension is the default. No setup is broken by this: the DevTools source runs in any Chromium.
 */
export function pickTree(platform: string = process.platform, env: NodeJS.ProcessEnv = process.env, extension: { ok: boolean; why: string } = { ok: true, why: "" }): TreePick {
  const given = env.ANNOUNCEMENT_EMULATOR_TREE;
  if (given === "extension" || given === "devtools") return { source: given, why: `ANNOUNCEMENT_EMULATOR_TREE=${given}` };
  if (platform === "darwin") return { source: "devtools", why: "macOS gives the extension no desktop tree" };
  if (!extension.ok) return { source: "devtools", why: `the extension was not used: ${extension.why}` };
  return { source: "extension", why: "the default where the browser gives the extension a desktop tree" };
}

export const treeSource = (platform: string = process.platform, env: NodeJS.ProcessEnv = process.env): TreeSource => pickTree(platform, env).source;

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
