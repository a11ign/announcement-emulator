import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { browserArgs, prepareExtension, treeSource } from "./extension.ts";

test("the extension copy names passive.js as its service worker and carries the runtime's port, and the bundle's own copy is untouched", () => {
  const bundle = mkdtempSync(join(tmpdir(), "ae-ext-"));
  const source = join(bundle, "emu", "ext2");
  mkdirSync(source, { recursive: true });
  writeFileSync(join(source, "manifest.json"), JSON.stringify({ name: "x", background: { service_worker: "bg.js" } }));
  writeFileSync(join(source, "passive.js"), "const C = 'http://127.0.0.1:__PORT__/'; const VERIFY = '__VERIFY__' === '1';");
  const dest = prepareExtension(bundle, join(bundle, "copy"), 4242, true);
  assert.equal(JSON.parse(readFileSync(join(dest, "manifest.json"), "utf8")).background.service_worker, "passive.js");
  assert.equal(readFileSync(join(dest, "passive.js"), "utf8"), "const C = 'http://127.0.0.1:4242/'; const VERIFY = '1' === '1';");
  assert.equal(JSON.parse(readFileSync(join(source, "manifest.json"), "utf8")).background.service_worker, "bg.js");
  assert.match(readFileSync(join(source, "passive.js"), "utf8"), /__PORT__/);
});

test("the browser flags are the ones the ticket names, the one Chrome 155 needs to honour --load-extension, and the DevTools port", () => {
  assert.deepEqual(browserArgs("/e", "id", { collector: 1, cdp: 2 }), ["--force-renderer-accessibility", "--load-extension=/e", "--allowlisted-extension-id=id",
    "--disable-features=DisableLoadExtensionCommandLineSwitch", "--remote-debugging-port=2"]);
});

test("tree.js lists a node's fields in the order the node has them, the fields that name other nodes where they stand (as bg.js did before the code moved)", () => {
  const source = readFileSync(join(import.meta.dirname, "..", "..", "emu", "ext2", "tree.js"), "utf8");
  const other = { role: "button", children: [] };
  const node = { role: "list", name: "n", labelledBy: [other], value: "v", children: [], state: { focused: true }, fn: () => 1, tabs: [{ a: 1 }] };
  const describeNode = new Function("node", "other", `${source}; IX.set(node, 0); IX.set(other, 1); return describe(node);`);
  const described = describeNode(node, other);
  assert.deepEqual(Object.keys(described), ["role", "name", "labelledByIx", "value", "children", "state", "tabs"]);
  assert.deepEqual(described.labelledByIx, [1]);
});

test("the tree is read by the extension where the browser has a desktop tree, and through the DevTools port on macOS, which has none; the environment decides when it is set", () => {
  assert.equal(treeSource("linux", {}), "extension");
  assert.equal(treeSource("win32", {}), "extension");
  assert.equal(treeSource("darwin", {}), "devtools");
  assert.equal(treeSource("darwin", { ANNOUNCEMENT_EMULATOR_TREE: "extension" }), "extension");
  assert.equal(treeSource("linux", { ANNOUNCEMENT_EMULATOR_TREE: "devtools" }), "devtools");
  assert.equal(treeSource("linux", { ANNOUNCEMENT_EMULATOR_TREE: "nonsense" }), "extension");
});

test("with the tree through the DevTools port the browser gets no extension flag", () => {
  assert.deepEqual(browserArgs("", "id", { collector: 1, cdp: 2 }, "devtools"), ["--force-renderer-accessibility", "--remote-debugging-port=2"]);
});
