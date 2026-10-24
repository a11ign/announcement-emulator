import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { browserArgs, prepareExtension } from "./extension.ts";

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
