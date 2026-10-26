// The middleware tests' globalSetup (A11-279): it points TMPDIR at one private directory per run and removes it at the end.
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { RUN_PREFIX, makeRunTmp, privateBase, removeRunTmp } from "./private-tmp.mjs";

const inside = (dir: string, parent: string) => dir.startsWith(parent + "/");

test("the run's TMPDIR is the private directory the globalSetup made, so tmpdir() lands in it", () => {
  const run = process.env.TMPDIR ?? "";
  assert.match(run, new RegExp(`/${RUN_PREFIX}[^/]+$`));
  assert.equal(tmpdir(), run);
  assert.ok(inside(run, privateBase()), `${run} is under ${privateBase()}`);
  assert.ok(inside(mkdtempSync(join(tmpdir(), "ae-probe-")), run));
});

test("the base is A11Y_PRIVATE_TMP_BASE when set, else ~/.cache/a11ign/tmp, and never a folder inside this package", () => {
  assert.equal(privateBase({ A11Y_PRIVATE_TMP_BASE: "/somewhere/private" }), "/somewhere/private");
  assert.equal(privateBase({}), join(homedir(), ".cache", "a11ign", "tmp"));
  assert.ok(!inside(privateBase({}), join(import.meta.dirname, "..")));
});

test("makeRunTmp makes a short ae-run-* directory under the base, and removeRunTmp removes it with what is inside", () => {
  const base = mkdtempSync(join(tmpdir(), "ae-base-"));
  const dir = makeRunTmp({ A11Y_PRIVATE_TMP_BASE: base });
  assert.equal(join(dir, ".."), base);
  assert.match(dir.slice(base.length + 1), new RegExp(`^${RUN_PREFIX}\\w{6}$`));
  assert.notEqual(makeRunTmp({ A11Y_PRIVATE_TMP_BASE: base }), dir);
  writeFileSync(join(dir, "left-behind.txt"), "x");
  removeRunTmp(dir);
  assert.ok(!existsSync(dir));
  assert.ok(existsSync(base));
});

test("removeRunTmp refuses a directory that is not an ae-run-* one", () => {
  const other = mkdtempSync(join(tmpdir(), "ae-other-"));
  assert.throws(() => removeRunTmp(other), /refusing to remove/);
  assert.ok(existsSync(other));
  assert.throws(() => removeRunTmp("/tmp"), /refusing to remove/);
});
