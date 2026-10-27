import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readdirSync, readFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

// A11-353: the package is Apache-2.0 and holds no file of the GPL-3.0-or-later runtime it starts. The runtime is a separate download (A11-232); this reads what `npm pack` would publish.

const PACKAGE = fileURLToPath(new URL("..", import.meta.url));
const REPOSITORY = fileURLToPath(new URL("../..", import.meta.url));
const manifest = JSON.parse(readFileSync(join(PACKAGE, "package.json"), "utf8")) as { name: string; license: string; files: string[] };

/** Every file under `directory`, relative to the repository, without the dependencies and caches that are not the runtime's own. */
function filesUnder(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (["node_modules", "__pycache__", ".git"].includes(entry.name)) return [];
    const path = join(directory, entry.name);
    return entry.isDirectory() ? filesUnder(path) : [relative(REPOSITORY, path)];
  });
}

const digest = (path: string): string => createHash("sha256").update(readFileSync(join(REPOSITORY, path))).digest("hex");

/** The packed files, as `npm pack --dry-run` lists them: nothing is written, nothing is built (`--ignore-scripts`), so a missing `dist` is not a failure here. */
function packed(): string[] {
  const cache = mkdtempSync(join(tmpdir(), "ae-pack-"));
  const done = spawnSync("npm", ["pack", "--dry-run", "--json", "--ignore-scripts"], { cwd: PACKAGE, encoding: "utf8", env: { ...process.env, npm_config_cache: cache } });
  assert.equal(done.status, 0, done.stderr);
  return (JSON.parse(done.stdout) as { files: { path: string }[] }[])[0]!.files.map((file) => file.path);
}

/** The runtime: its Python, the emulator and the probes, the bundle's build and its notices. Not the package's own TypeScript. */
const RUNTIME_DIRECTORIES = ["middleware/runtime", "middleware/bundle", "emu", "q1", "q2", "q3"];
const runtimeFiles = RUNTIME_DIRECTORIES.flatMap((directory) => filesUnder(join(REPOSITORY, directory)).filter((path) => statSync(join(REPOSITORY, path)).size > 0));

test("the package is named @a11ign/foresay and declares Apache-2.0", () => {
  assert.equal(manifest.name, "@a11ign/foresay");
  assert.equal(manifest.license, "Apache-2.0");
});

test("the packed files are the package's own: dist, the pins, the notes, the licence and the notice", () => {
  const files = packed();
  assert.ok(files.includes("package.json") && files.includes("LICENSE") && files.includes("NOTICE"), files.join(", "));
  const allowed = /^(dist\/.+|pins\.json|supported-versions\.json|CHANGELOG\.md|README\.md|LICENSE|NOTICE|package\.json)$/;
  assert.deepEqual(files.filter((file) => !allowed.test(file)), []);
});

test("no packed file is a file of the runtime, by path or by content", () => {
  const files = packed();
  const runtimePaths = new Set(runtimeFiles.map((path) => path.replace(/^middleware\//, "")));
  assert.ok(runtimeFiles.length > 50, "the runtime's files were not found");
  assert.deepEqual(files.filter((file) => runtimePaths.has(file) || RUNTIME_DIRECTORIES.some((directory) => file.startsWith(`${directory}/`)) || /\.(py|pyc)$/.test(file)), []);
  const runtimeDigests = new Set(runtimeFiles.map(digest));
  const packedFromDisk = files.filter((file) => statSync(join(PACKAGE, file), { throwIfNoEntry: false })?.isFile());
  assert.deepEqual(packedFromDisk.filter((file) => runtimeDigests.has(createHash("sha256").update(readFileSync(join(PACKAGE, file))).digest("hex"))), []);
});

test("the package's LICENSE is Apache-2.0 and not the runtime's GPL text, and its NOTICE says where the runtime is", () => {
  const licence = readFileSync(join(PACKAGE, "LICENSE"), "utf8");
  assert.match(licence, /Apache License\s+Version 2\.0/);
  assert.notEqual(digest("middleware/LICENSE"), digest("LICENSE"));
  assert.match(readFileSync(join(PACKAGE, "NOTICE"), "utf8"), /separate download[\s\S]*GPL-3\.0-or-later/);
});

test("the package's own code copies no file out of the runtime and rewrites none", () => {
  const sources = readdirSync(join(PACKAGE, "src")).filter((file) => file.endsWith(".ts") && !file.endsWith(".test.ts"));
  assert.ok(sources.length > 10);
  for (const file of sources) assert.doesNotMatch(readFileSync(join(PACKAGE, "src", file), "utf8"), /\b(copyFile|copyFileSync|cp|cpSync)\(/, file);
});

test("the READMEs say what the tool is in the wording of docs/release-decisions.md section 1, and claim no NVDA, endorsement or compatibility", () => {
  const sentence = "Predicts what the NVDA screen reader would say, built on NVDA's open-source code. Not affiliated with NV Access.";
  for (const path of ["README.md", "middleware/README.md"]) {
    const text = readFileSync(join(REPOSITORY, path), "utf8");
    assert.ok(text.includes(sentence), path);
    assert.doesNotMatch(text, /NVDA[- ]compatible|endorsed by NV Access|NV Access endorses|\bis NVDA\b|official NVDA/i, path);
  }
});
