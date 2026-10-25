import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { accessSync, constants, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

// The release is rehearsed on every pull request that changes it (release-dry-run.yml), and the scripts it runs are tested here on scratch copies with fixture files: no network, no bundle, no browser.
// The workflows are read as YAML and never as words, so a comment that explains why there is no `id-token: write` cannot satisfy a search for one.

const REPOSITORY = fileURLToPath(new URL("../..", import.meta.url));
const read = (path: string) => readFileSync(join(REPOSITORY, path), "utf8");

type Job = { uses?: string; needs?: string | string[]; permissions?: Record<string, string>; strategy?: { matrix?: { include?: Record<string, unknown>[] } }; steps?: { uses?: string; with?: Record<string, unknown>; run?: string }[] };
type Workflow = { on?: Record<string, { paths?: string[] } | null>; permissions?: Record<string, string>; jobs?: Record<string, Job> };
const workflow = (name: string): Workflow => parse(read(`.github/workflows/${name}`)) as Workflow;

/** Every permissions block of a workflow: its own and each job's. */
const permissionBlocks = (w: Workflow): Record<string, string>[] => [w.permissions, ...Object.values(w.jobs ?? {}).map((job) => job.permissions)].filter((p) => p !== undefined);

for (const name of ["release-bundles.yml", "release-dry-run.yml"]) {
  test(`${name} holds no id-token: write and no contents: write, and no secret`, () => {
    const w = workflow(name);
    assert.deepEqual(w.permissions, { contents: "read" });      // the workflow's own: a job can only keep or reduce it
    for (const block of permissionBlocks(w)) {
      assert.notEqual(block["id-token"], "write");
      assert.notEqual(block.contents, "write");
      assert.ok(Object.values(block).every((level) => level !== "write"), JSON.stringify(block));
    }
    assert.doesNotMatch(read(`.github/workflows/${name}`), /secrets\.|secrets:|GH_TOKEN|NODE_AUTH_TOKEN|environment:/);
  });
}

test("release-bundles.yml is a reusable workflow that builds linux-x64 and darwin-arm64, requires the linux build to be reproducible and only reports darwin's, and uploads release-files", () => {
  const w = workflow("release-bundles.yml");
  assert.deepEqual(Object.keys(w.on ?? {}), ["workflow_call"]);
  const legs = w.jobs!.bundle!.strategy!.matrix!.include!;
  assert.deepEqual(legs.map((l) => [l.platform, l.required]), [["linux-x64", true], ["darwin-arm64", false]]);
  const uploads = Object.values(w.jobs!).flatMap((job) => job.steps ?? []).filter((s) => s.uses?.startsWith("actions/upload-artifact"));
  assert.ok(uploads.some((s) => s.with?.name === "release-files"));
  assert.deepEqual(w.jobs!.files!.needs, "bundle");
});

test("release-dry-run.yml rehearses on a pull request that changes a release and on dispatch, calls release-bundles.yml, and installs on both platforms", () => {
  const w = workflow("release-dry-run.yml");
  assert.deepEqual(Object.keys(w.on ?? {}).sort(), ["pull_request", "workflow_dispatch"]);
  const paths = w.on!.pull_request!.paths!;
  for (const path of [".github/workflows/release*.yml", "middleware/bundle/**", "middleware/release/**", "middleware/runtime/**", "middleware/src/**", "middleware/package.json", "middleware/pins.json", "pins.env", "emu/**", "q1/**", "q2/**", "q3/**"]) assert.ok(paths.includes(path), path);
  assert.equal(w.jobs!.bundles!.uses, "./.github/workflows/release-bundles.yml");
  assert.deepEqual(w.jobs!.install!.strategy!.matrix!.include!.map((l) => l.platform), ["linux-x64", "darwin-arm64"]);
});

test("the dry run is not part of the merge gate", () => {
  const ci = workflow("ci.yml");
  assert.ok(!JSON.stringify(ci).includes("release"), "ci.yml names a release job");
});

// ---- after-version.sh and gather.sh, on scratch copies ------------------------------------------------------------------------------------------------------------------------------------

const SUMS = { "linux-x64": "ab".repeat(32), "darwin-arm64": "cd".repeat(32) };
const fileOf = (platform: string) => `announcement-emulator-bundle-${platform}.tar.xz`;

/** A copy of the files after-version.sh runs, with a changelog whose newest entry is 1.2.3, and a release-files directory laid out as release-bundles.yml lays it. `listed` are the sums SHA256SUMS holds. */
function scratch(listed: Record<string, string> = SUMS) {
  const root = mkdtempSync(join(tmpdir(), "ae-release-"));
  for (const path of ["middleware/release/after-version.sh", "middleware/bundle/write-pins.mjs", "middleware/src/release-notes.ts", "middleware/src/supported.ts", "middleware/supported-versions.json", "pins.env", "middleware/results/playwright-versions/fleet-readings.json"]) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    cpSync(join(REPOSITORY, path), join(root, path));
  }
  writeFileSync(join(root, "middleware/package.json"), JSON.stringify({ name: "x", version: "1.2.3", private: true }));
  writeFileSync(join(root, "middleware/pins.json"), JSON.stringify({ version: "0.0.0", bundles: {} }, null, 2));
  writeFileSync(join(root, "middleware/CHANGELOG.md"), "# x\n\n## 1.2.3\n\n### Minor Changes\n\n- a: first\n");
  const files = join(root, "release-files");
  mkdirSync(join(files, "assets"), { recursive: true }); mkdirSync(join(files, "pins"));
  for (const [platform, sha256] of Object.entries(SUMS)) writeFileSync(join(files, "pins", `pin-${platform}.json`), JSON.stringify({ platform, file: fileOf(platform), sha256, bytes: 7 }));
  writeFileSync(join(files, "assets", "SHA256SUMS"), Object.entries(listed).map(([platform, sha]) => `${sha}  ${fileOf(platform)}\n`).join(""));
  return { root, files, run: (env: Record<string, string> = { RELEASE_FILES: files }) => spawnSync("sh", [join(root, "middleware/release/after-version.sh")], { encoding: "utf8", env: { ...process.env, RELEASE_FILES: "", ...env } }) };
}

test("after-version.sh pins the sums of the release files and appends the measured agreement to the entry of the version", () => {
  const { root, run } = scratch();
  const done = run();
  assert.equal(done.status, 0, done.stderr);
  const pins = JSON.parse(readFileSync(join(root, "middleware/pins.json"), "utf8"));
  assert.equal(pins.version, "1.2.3");
  assert.deepEqual(Object.fromEntries(Object.entries(pins.bundles as Record<string, { sha256: string; file: string }>).map(([p, b]) => [p, [b.sha256, b.file]])), Object.fromEntries(Object.entries(SUMS).map(([p, s]) => [p, [s, fileOf(p)]])));
  const changelog = readFileSync(join(root, "middleware/CHANGELOG.md"), "utf8");
  assert.match(changelog, /- a: first\n\n### Measured agreement\n\n/);
  const [build] = (JSON.parse(read("middleware/supported-versions.json")) as { builds: { chromium: string; playwright: string[] }[] }).builds;
  assert.ok(changelog.includes(`Playwright ${build!.playwright.join(", ")}: Chromium ${build!.chromium}`));
  assert.ok(!existsSync(join(root, "middleware/pins.json.new")));
});

test("after-version.sh fails when a pin's sum is not the one SHA256SUMS lists, and leaves pins.json and the changelog as they were", () => {
  const { root, run } = scratch({ ...SUMS, "darwin-arm64": "ee".repeat(32) });
  const pinsBefore = readFileSync(join(root, "middleware/pins.json"), "utf8"), changelogBefore = readFileSync(join(root, "middleware/CHANGELOG.md"), "utf8");
  const done = run();
  assert.notEqual(done.status, 0);
  assert.match(done.stderr, /darwin-arm64 pins announcement-emulator-bundle-darwin-arm64\.tar\.xz at sha256 cdcd/);
  assert.equal(readFileSync(join(root, "middleware/pins.json"), "utf8"), pinsBefore);
  assert.equal(readFileSync(join(root, "middleware/CHANGELOG.md"), "utf8"), changelogBefore);
  assert.ok(!existsSync(join(root, "middleware/pins.json.new")));
});

test("after-version.sh fails when a pin has no line in SHA256SUMS, with no RELEASE_FILES, and with no bundle built", () => {
  const missing = scratch({ "linux-x64": SUMS["linux-x64"] });
  assert.match(missing.run().stderr, /no line for it/);
  assert.notEqual(missing.run().status, 0);
  const none = scratch();
  assert.notEqual(none.run({}).status, 0);
  assert.match(none.run({}).stderr, /RELEASE_FILES/);
  const empty = scratch();
  for (const pin of readdirSync(join(empty.files, "pins"))) rmSync(join(empty.files, "pins", pin));
  assert.match(empty.run().stderr, /has no pin-<platform>\.json/);
});

/** Legs as the two build jobs upload them, merged into one directory: archives, their .sha256 files, pins and the reproducibility records. */
function legs(only?: string[]) {
  const dir = mkdtempSync(join(tmpdir(), "ae-legs-"));
  for (const platform of only ?? Object.keys(SUMS)) {
    writeFileSync(join(dir, fileOf(platform)), `bundle ${platform}`);
    const sha256 = spawnSync("sha256sum", [join(dir, fileOf(platform))], { encoding: "utf8" }).stdout.split(" ")[0]!;
    writeFileSync(join(dir, `${fileOf(platform)}.sha256`), `${sha256}  ${fileOf(platform)}\n`);
    writeFileSync(join(dir, `pin-${platform}.json`), JSON.stringify({ platform, file: fileOf(platform), sha256, bytes: 8 }));
    writeFileSync(join(dir, `reproducible-${platform}.json`), JSON.stringify({ platform, reproducible: true, required: platform === "linux-x64" }));
  }
  return dir;
}
const gather = (dir: string, out = mkdtempSync(join(tmpdir(), "ae-files-"))) => ({ out, done: spawnSync("sh", [join(REPOSITORY, "middleware/release/gather.sh"), dir, out], { encoding: "utf8" }) });

test("gather.sh lays the legs out as the release-files artifact, with a SHA256SUMS that names every bundle and that sha256sum accepts", () => {
  const { out, done } = gather(legs());
  assert.equal(done.status, 0, done.stderr);
  const sums = readFileSync(join(out, "assets", "SHA256SUMS"), "utf8").trim().split("\n");
  assert.deepEqual(sums.map((l) => l.split("  ")[1]), [fileOf("darwin-arm64"), fileOf("linux-x64")]);
  for (const platform of Object.keys(SUMS)) for (const path of [`assets/${fileOf(platform)}`, `assets/${fileOf(platform)}.sha256`, `pins/pin-${platform}.json`, `report/reproducible-${platform}.json`]) assert.ok(existsSync(join(out, path)), path);
  assert.equal(spawnSync("sha256sum", ["-c", "SHA256SUMS"], { cwd: join(out, "assets") }).status, 0);
});

test("gather.sh fails for a bundle that has no pin and for a pin that is not its bundle's sum", () => {
  const unpinned = legs();
  rmSync(join(unpinned, "pin-darwin-arm64.json"));
  assert.notEqual(gather(unpinned).done.status, 0);
  const wrong = legs();
  writeFileSync(join(wrong, "pin-linux-x64.json"), JSON.stringify({ platform: "linux-x64", file: fileOf("linux-x64"), sha256: "ff".repeat(32), bytes: 8 }));
  const { done } = gather(wrong);
  assert.notEqual(done.status, 0);
  assert.match(done.stderr, /linux-x64 pins/);
});

test("the release scripts are executable", () => {
  for (const script of ["after-version.sh", "dry-run.sh", "gather.sh", "install-check.sh"]) assert.doesNotThrow(() => accessSync(join(REPOSITORY, "middleware/release", script), constants.X_OK), script);
});
