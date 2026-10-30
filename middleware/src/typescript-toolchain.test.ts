import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { ESLint } from "eslint";
import { parse } from "yaml";

// A11-400: `tsc` and the Rslib declaration build run on TypeScript 7, and typescript-eslint, which has no TypeScript 7 support (typescript-eslint#10940), runs on a TypeScript 6 beside it.

const PACKAGE = fileURLToPath(new URL("..", import.meta.url));
const manifest = JSON.parse(readFileSync(join(PACKAGE, "package.json"), "utf8")) as { devDependencies: Record<string, string>; exports: Record<string, string | { types?: string; default?: string }> };
const lock = parse(readFileSync(join(PACKAGE, "pnpm-lock.yaml"), "utf8")) as { importers: Record<string, { devDependencies: Record<string, { version: string }> }>; snapshots: Record<string, { dependencies?: Record<string, string> }> };

const run = (bin: string, args: string[]) => spawnSync(join(PACKAGE, "node_modules", ".bin", bin), args, { cwd: PACKAGE, encoding: "utf8" });

test("the package asks for TypeScript 7, and the install resolves it", () => {
  assert.match(manifest.devDependencies.typescript!, /^\^7\./);
  assert.match(lock.importers["."]!.devDependencies.typescript!.version, /^7\./);
});

test("the `tsc` the typecheck step runs reports TypeScript 7", () => {
  assert.match(run("tsc", ["--version"]).stdout, /^Version 7\./);
});

test("typescript-eslint and every @typescript-eslint package resolve their own TypeScript 6, beside the 7", () => {
  const eslintSnapshots = Object.entries(lock.snapshots).filter(([key]) => /^(typescript-eslint|@typescript-eslint\/[^@]+)@/.test(key));
  assert.deepEqual(eslintSnapshots.map(([key]) => key).filter((key) => key.includes("typescript@7")), [], "a typescript-eslint package took the importer's TypeScript 7");
  const withTypescript = eslintSnapshots.filter(([, snapshot]) => snapshot.dependencies?.typescript !== undefined);
  assert.ok(withTypescript.length >= 8, `found ${withTypescript.map(([key]) => key).join(", ")}`);
  for (const [key, snapshot] of withTypescript) assert.match(snapshot.dependencies!.typescript!, /^6\./, key);
  const typescripts = Object.keys(lock.snapshots).filter((key) => /^typescript@/.test(key));
  assert.ok(typescripts.some((key) => key.startsWith("typescript@6.")) && typescripts.some((key) => key.startsWith("typescript@7.")), typescripts.join(", "));
});

test("lint reads TypeScript with the typescript-eslint recommended rules", async () => {
  const [result] = await new ESLint({ cwd: PACKAGE }).lintText("export const value: any = 1;\n", { filePath: join(PACKAGE, "src", "lint-probe.ts") });
  assert.ok(result!.messages.some((message) => message.ruleId === "@typescript-eslint/no-explicit-any"), JSON.stringify(result!.messages));
});

test("every file `exports` names is in dist after a build, declarations included", () => {
  const built = run("rslib", ["build"]);
  assert.equal(built.status, 0, built.stdout + built.stderr);
  const targets = Object.values(manifest.exports).flatMap((entry) => (typeof entry === "string" ? [entry] : [entry.types, entry.default])).filter((target) => target !== undefined);
  assert.ok(targets.some((target) => target.startsWith("./dist/") && target.includes(".d.")), targets.join(", "));
  assert.deepEqual(targets.filter((target) => !existsSync(join(PACKAGE, target))), []);
});
