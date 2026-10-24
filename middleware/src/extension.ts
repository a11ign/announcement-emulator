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
 * The flags the emulator's browser needs, which the ticket names (`--force-renderer-accessibility`, `--load-extension`, `--allowlisted-extension-id`) and two more:
 * `--disable-features=DisableLoadExtensionCommandLineSwitch`, without which Chrome 155 ignores `--load-extension` (emu/session.mjs passes it), and `--remote-debugging-port`, the second
 * door to the browser that cdp.py reads keys through (Playwright keeps its own, a pipe). The `--disable-features` flag replaces the one Playwright passes: Chrome takes the last.
 */
export function browserArgs(extensionDir: string, extensionId: string, ports: BrowserPorts): string[] {
  return [
    "--force-renderer-accessibility",
    `--load-extension=${extensionDir}`,
    `--allowlisted-extension-id=${extensionId}`,
    "--disable-features=DisableLoadExtensionCommandLineSwitch",
    `--remote-debugging-port=${ports.cdp}`,
  ];
}
