/** The two ports one runtime serves its worker's browser through: where the browser tells the runtime what a page changed, and the browser's own DevTools port, which the runtime reads the trees and the keys through. */
export interface BrowserPorts { collector: number; cdp: number }

/**
 * The flags the emulator's browser needs, which the ticket names: `--force-renderer-accessibility`, and `--remote-debugging-port`, the second door to the browser that cdp.py reads the trees and the keys through
 * (Playwright keeps its own, a pipe). The browser is the team's, whichever it launches: nothing here loads an extension or names a channel, so the flags work in Playwright's headless shell, in its full Chromium, in a
 * branded browser, and in the contexts a suite opens itself with `browser.newContext()`.
 */
export function browserArgs(ports: BrowserPorts): string[] {
  return ["--force-renderer-accessibility", `--remote-debugging-port=${ports.cdp}`];
}

/** The setting that used to choose a tree source. There is one source now, the DevTools port, so the setting does nothing. */
export const TREE_SETTING = "ANNOUNCEMENT_EMULATOR_TREE";

/** What a run says when a setting that used to choose a tree source is still set (a CI file written before there was one source): the run goes on and the setting changes nothing, so no setup breaks. Null when it is not set. */
export function treeSettingNote(env: NodeJS.ProcessEnv = process.env): string | null {
  const given = env[TREE_SETTING];
  return given ? `announcement-emulator: ${TREE_SETTING}=${given} is ignored: the DevTools port is the only tree source, on every operating system.` : null;
}
