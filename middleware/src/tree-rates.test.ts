import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { TREE_RATES, treeRate } from "./tree-rates.ts";

const measured = JSON.parse(readFileSync(new URL("../results/tree-source/comparison.json", import.meta.url), "utf8")) as { readings: Record<string, { agreed: number; units: number }> };

test("the rates a report quotes are the ones measured against the fleet, in results/tree-source/comparison.json", () => {
  assert.deepEqual(TREE_RATES["extension-linux"], measured.readings["ext-linux"]);
  assert.deepEqual(TREE_RATES["devtools-linux"], measured.readings["devtools-linux"]);
  assert.deepEqual(TREE_RATES["devtools-macos"], measured.readings["devtools-macos"]);
});

test("the sentence names the source, the rate, the units and the system, and says plainly when a system was not measured", () => {
  assert.equal(treeRate("extension", "linux"), "the extension tree agreed with a real NVDA on 82.1% of 1,138 units on Linux, Chrome 155, six pages (A11-229)");
  assert.equal(treeRate("devtools", "darwin"), "the devtools tree agreed with a real NVDA on 83.6% of 1,026 units on macOS, Chrome 155, six pages (A11-229)");
  assert.equal(treeRate("devtools", "win32"), "the devtools tree was not measured on Windows");
  assert.equal(treeRate("extension", "darwin"), "the extension tree was not measured on macOS");
});
