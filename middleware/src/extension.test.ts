import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { browserArgs, extensionWait, EXTENSION_WAIT_S, pickTree, prepareExtension, treeSource, type TreeOption } from "./extension.ts";

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

test("a run says why its tree came from where it did, and a setup the extension cannot be expected to load in reads through the DevTools port and breaks nothing", () => {
  const no = { ok: false, why: "Playwright's full Chromium 156.0.8078.4 is not installed" };
  assert.deepEqual(pickTree("linux", {}, { ok: true, why: "" }), { source: "extension", why: "the default where the browser gives the extension a desktop tree", forced: false });
  assert.deepEqual(pickTree("linux", {}, no), { source: "devtools", why: "the extension was not used: Playwright's full Chromium 156.0.8078.4 is not installed", forced: false });
  assert.deepEqual(pickTree("darwin", {}, { ok: true, why: "" }), { source: "devtools", why: "macOS gives the extension no desktop tree", forced: false });
});

test("the environment still decides over what the launch is expected to load", () => {
  const no = { ok: false, why: "x" };
  assert.deepEqual(pickTree("linux", { ANNOUNCEMENT_EMULATOR_TREE: "extension" }, no), { source: "extension", why: "ANNOUNCEMENT_EMULATOR_TREE=extension", forced: true });
  assert.deepEqual(pickTree("darwin", { ANNOUNCEMENT_EMULATOR_TREE: "extension" }, no), { source: "extension", why: "ANNOUNCEMENT_EMULATOR_TREE=extension", forced: true });
  assert.equal(pickTree("linux", { ANNOUNCEMENT_EMULATOR_TREE: "devtools" }).source, "devtools");
});

test("the runtime waits for an extension that has said nothing only where the extension is picked and not forced, for as long as the environment says or the default", () => {
  const auto = pickTree("linux", {});
  assert.equal(extensionWait(auto, {}), EXTENSION_WAIT_S);
  assert.equal(extensionWait(auto, { ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT: "12" }), 12);
  assert.equal(extensionWait(auto, { ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT: "nonsense" }), EXTENSION_WAIT_S);
  assert.equal(extensionWait(pickTree("linux", { ANNOUNCEMENT_EMULATOR_TREE: "extension" }), {}), 0, "forced: the readings of a source are not switched to the other");
  assert.equal(extensionWait(pickTree("darwin", {}), {}), 0, "already the DevTools port");
});

const yes = { ok: true, why: "" };

test("the pick for each platform and option: auto is the extension on Linux and Windows and the DevTools port on macOS, and the option forces either source anywhere", () => {
  const table: [string, TreeOption | undefined, string][] = [
    ["linux", "auto", "extension"], ["win32", "auto", "extension"], ["darwin", "auto", "devtools"],
    ["linux", undefined, "extension"], ["darwin", undefined, "devtools"],
    ["linux", "devtools", "devtools"], ["win32", "devtools", "devtools"], ["darwin", "devtools", "devtools"],
    ["linux", "extension", "extension"], ["win32", "extension", "extension"], ["darwin", "extension", "extension"],
  ];
  for (const [platform, option, source] of table) assert.equal(pickTree(platform, {}, yes, option).source, source, `${platform} / ${option}`);
});

test("a pick says why: the platform, the launch, the option, or the environment, and only a pick made by hand is forced", () => {
  assert.deepEqual(pickTree("linux", {}, yes, "auto"), { source: "extension", why: "the default where the browser gives the extension a desktop tree", forced: false });
  assert.deepEqual(pickTree("darwin", {}, yes, "auto"), { source: "devtools", why: "macOS gives the extension no desktop tree", forced: false });
  assert.deepEqual(pickTree("linux", {}, { ok: false, why: "x" }, "auto"), { source: "devtools", why: "the extension was not used: x", forced: false });
  assert.deepEqual(pickTree("linux", {}, yes, "devtools"), { source: "devtools", why: 'the tree option is "devtools"', forced: true });
  assert.deepEqual(pickTree("darwin", {}, yes, "extension"), { source: "extension", why: 'the tree option is "extension"', forced: true });
});

test("the option wins over the environment, and the reason says the environment was set and not used", () => {
  const picked = pickTree("linux", { ANNOUNCEMENT_EMULATOR_TREE: "extension" }, yes, "devtools");
  assert.equal(picked.source, "devtools");
  assert.equal(picked.why, 'the tree option is "devtools" (ANNOUNCEMENT_EMULATOR_TREE=extension is set and is not used: the option wins)');
  assert.equal(pickTree("linux", { ANNOUNCEMENT_EMULATOR_TREE: "devtools" }, yes, "extension").source, "extension");
});

test("auto, and an option that names no source, leave the decision to the environment and then to the platform", () => {
  assert.deepEqual(pickTree("linux", { ANNOUNCEMENT_EMULATOR_TREE: "devtools" }, yes, "auto"), { source: "devtools", why: "ANNOUNCEMENT_EMULATOR_TREE=devtools", forced: true });
  assert.equal(pickTree("linux", {}, yes, "nonsense" as TreeOption).source, "extension");
  assert.equal(pickTree("darwin", {}, yes, "nonsense" as TreeOption).source, "devtools");
});

test("a source forced by the option is not switched by the runtime, and one left to auto is", () => {
  assert.equal(extensionWait(pickTree("linux", {}, yes, "extension"), {}), 0);
  assert.equal(extensionWait(pickTree("linux", {}, yes, "auto"), {}), EXTENSION_WAIT_S);
});
