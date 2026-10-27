import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { doctor } from "./doctor.ts";
import { Runtime } from "./runtime.ts";

// A11-353: the package is Apache-2.0 and holds no file of the GPL-3.0-or-later runtime it starts. The runtime is a separate download (A11-232); this reads what `npm pack` would publish.

const PACKAGE = fileURLToPath(new URL("..", import.meta.url));
const REPOSITORY = fileURLToPath(new URL("../..", import.meta.url));
const manifest = JSON.parse(readFileSync(join(PACKAGE, "package.json"), "utf8")) as { name: string; license: string; files: string[] };

/** Every file git tracks under `directories`, relative to the repository: not a venv or a capture a development machine has left beside them. */
function trackedFilesUnder(directories: string[]): string[] {
  const done = spawnSync("git", ["ls-files", "-z", "--", ...directories], { cwd: REPOSITORY, encoding: "utf8" });
  assert.equal(done.status, 0, done.stderr);
  return done.stdout.split("\0").filter(Boolean);
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
const runtimeFiles = trackedFilesUnder(RUNTIME_DIRECTORIES).filter((path) => statSync(join(REPOSITORY, path)).size > 0);

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

// The behaviour behind "copies no file and rewrites none": run the package's own code against a bundle, and look at the bundle and at every place the package writes.

/** Each file under `root` (a link is not followed) as `relative path -> [sha256, mode, mtime]`. */
function snapshot(root: string): Map<string, string> {
  const files = new Map<string, string>();
  const walk = (directory: string): void => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) { walk(path); continue; }
      const stat = lstatSync(path);
      files.set(relative(root, path), `${createHash("sha256").update(readFileSync(path)).digest("hex")} ${stat.mode} ${stat.mtimeMs}`);
    }
  };
  walk(root);
  return files;
}

/** A bundle with a Python that says the runtime is ready, and files that stand for the GPL runtime and for what the package once copied out of it. Every file's content is its own. */
function fakeBundle(): string {
  const bundle = mkdtempSync(join(tmpdir(), "ae-nocopy-bundle-"));
  const files: Record<string, string> = {
    "bundle.json": JSON.stringify({ name: "b", platform: "linux-x64", license: "GPL-3.0-or-later", nvda: { release: "release-2026.1.1", commit: "5d92106f" }, chromiumTables: "155.0.8059.84", python: "3.13.16", commit: "abc" }),
    "LICENSE": "GNU GENERAL PUBLIC LICENSE, as the bundle ships it",
    "NOTICES": "the notices of this bundle",
    "nvda-src/copying.txt": "NVDA's licence file",
    "nvda-src/source/speech/speech.py": "# a file of NVDA's own",
    "middleware/runtime/main.py": "# the runtime's main, with a placeholder: __PORT__",
    "middleware/runtime/passive.js": "// a script with the port to rewrite: __COLLECTOR_PORT__",
  };
  for (const [path, content] of Object.entries(files)) { mkdirSync(join(bundle, path, ".."), { recursive: true }); writeFileSync(join(bundle, path), content); }
  mkdirSync(join(bundle, "python", "bin"), { recursive: true });
  const python = join(bundle, "python", "bin", "python3");
  writeFileSync(python, `#!/bin/sh\ncase "$1" in -I) if [ "$2" = "-c" ]; then echo 3.13.16; exit 0; fi;; esac\necho '{"type":"ready","bootMs":1}'\nread line\n`);
  chmodSync(python, 0o755);
  return bundle;
}

test("running the package against a bundle changes no file of the bundle and leaves no copy of one anywhere the package writes", async () => {
  const bundle = fakeBundle(), project = mkdtempSync(join(tmpdir(), "ae-nocopy-project-"));
  const before = snapshot(bundle);
  const log = join(project, "test-results", "foresay", "runtime-0.log");

  const runtime = new Runtime(bundle, { collector: 41011, cdp: 41012 }, { log });
  await runtime.ready;
  await runtime.stop();
  const lines: string[] = [];
  doctor({ env: { ANNOUNCEMENT_EMULATOR_BUNDLE: bundle }, playwright: { version: "1.63.0", chromium: { revision: "1", build: "153.0.8010.12" }, headlessShell: { revision: "1", build: "153.0.8010.12" }, executablePath: "/x/chrome", fullInstalled: true, shellInstalled: true }, supported: { builds: [] }, version: () => ({ status: 0, out: "Chromium 153.0.8010.12" }), log: (line) => lines.push(line) });

  assert.deepEqual(snapshot(bundle), before, "a file of the bundle was written, rewritten or removed");
  const bundleContents = new Set([...before.values()].map((value) => value.split(" ")[0]));
  const written = [...snapshot(project).entries()].filter(([, value]) => bundleContents.has(value.split(" ")[0]!));
  assert.deepEqual(written, [], "a file of the bundle was copied into the project");
});
