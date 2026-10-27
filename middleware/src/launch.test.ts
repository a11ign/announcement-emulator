import { test } from "node:test";
import assert from "node:assert/strict";
import { browserArgs, treeSettingNote, TREE_SETTING } from "./launch.ts";

test("the browser is launched with the accessibility flag and the DevTools port, and with nothing that loads an extension", () => {
  const args = browserArgs({ collector: 41001, cdp: 41002 });
  assert.deepEqual(args, ["--force-renderer-accessibility", "--remote-debugging-port=41002"]);
  assert.equal(args.some((a) => /extension|disable-features/.test(a)), false);
});

test("each worker's browser is given its own port", () => {
  assert.notDeepEqual(browserArgs({ collector: 1, cdp: 2 }), browserArgs({ collector: 3, cdp: 4 }));
});

test("a setting that used to choose a tree source is ignored with one line that says so, and any value of it, the old ones included", () => {
  for (const given of ["devtools", "extension", "anything"]) {
    const note = treeSettingNote({ [TREE_SETTING]: given });
    assert.match(note!, new RegExp(`${TREE_SETTING}=${given} is ignored: the DevTools port is the only tree source`));
    assert.equal(note!.includes("\n"), false);
  }
});

test("nothing is said when the setting is not set, or is empty", () => {
  assert.equal(treeSettingNote({}), null);
  assert.equal(treeSettingNote({ [TREE_SETTING]: "" }), null);
});
