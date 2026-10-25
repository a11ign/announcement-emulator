import type { TreeSource } from "./extension.ts";
import { percent } from "./supported.ts";

/** How often one reading of a tree source agreed with a real NVDA on the same actions: `agreed` of `units`. */
export interface TreeRate { agreed: number; units: number }

/**
 * What each tree source measured against the fleet's real NVDA, on the six pages of `results/agreement/pages.json`, in the Chrome 155 of the bundle (A11-229, step 1: `results/tree-source/comparison.json`,
 * every channel, the first fleet capture against the first run). Windows was not measured. `tree-rates.test.ts` holds these numbers to that file. These are the figures in a report until the rate of
 * the team's own Chromium build is on `supported-versions.json` (A11-230).
 */
export const TREE_RATES: Record<string, TreeRate> = {
  "extension-linux": { agreed: 934, units: 1138 },
  "devtools-linux": { agreed: 926, units: 1138 },
  "devtools-macos": { agreed: 858, units: 1026 },
};

const SYSTEM: Record<string, string> = { linux: "Linux", darwin: "macOS", win32: "Windows" };
const OS: Record<string, string> = { linux: "linux", darwin: "macos", win32: "windows" };

/** The sentence a report carries about how well a tree source agreed with NVDA, on the platform the run is on. */
export function treeRate(tree: TreeSource, platform: string = process.platform): string {
  const rate = TREE_RATES[`${tree}-${OS[platform] ?? platform}`];
  const system = SYSTEM[platform] ?? platform;
  if (!rate) return `the ${tree} tree was not measured on ${system}`;
  return `the ${tree} tree agreed with a real NVDA on ${percent(rate.agreed / rate.units)} of ${rate.units.toLocaleString("en-US")} units on ${system}, Chrome 155, six pages (A11-229)`;
}
