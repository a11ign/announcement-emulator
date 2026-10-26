import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

// CI runs only what a change needs (A11-260). Every workflow in .github/workflows is read as YAML and never as words, so a comment that explains a rule cannot satisfy a search for it. The spike's matrices are made by
// its `mode` job, so that job's script is run here, once for a pull request and once for the other events, and the rows it prints are what is counted.

const REPOSITORY = fileURLToPath(new URL("../..", import.meta.url));
const WORKFLOWS = join(REPOSITORY, ".github", "workflows");

type Trigger = { paths?: string[]; types?: string[] } | null;
type Step = { id?: string; if?: string; uses?: string; run?: string; with?: { name?: string } };
type Job = { if?: string; needs?: string | string[]; uses?: string; "runs-on"?: string; steps?: Step[]; strategy?: { matrix?: string } };
type Concurrency = { group?: string; "cancel-in-progress"?: boolean | string };
type Workflow = { on?: Record<string, Trigger>; concurrency?: Concurrency; jobs?: Record<string, Job> };
type Row = Record<string, string | boolean>;

const names = readdirSync(WORKFLOWS).filter((file) => /\.ya?ml$/.test(file));
const workflows = new Map(names.map((name) => [name, parse(readFileSync(join(WORKFLOWS, name), "utf8")) as Workflow]));
const workflow = (name: string): Workflow => workflows.get(name) ?? assert.fail(`${name} is not in .github/workflows`);
const jobsOf = (name: string): [string, Job][] => Object.entries(workflow(name).jobs ?? {});
const stepsOf = (job: Job): Step[] => job.steps ?? [];

const DRAFT = "github.event_name != 'pull_request' || !github.event.pull_request.draft";
const SPIKE = "middleware-spike.yml";
/** The workflows that a fleet capture window starts by committing a stamp file (A11-229, A11-230, A11-234). */
const MEASUREMENTS = names.filter((name) => workflow(name).on?.push?.paths?.some((path) => path.startsWith("middleware/results/")));

/** Every string in the parsed document: what the workflow says, with its comments left out. */
function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === "object") return Object.values(value).flatMap(strings);
  return [];
}

/** Whether the workflow, or a workflow it calls from this repository, names a macOS runner. */
function usesMacos(name: string, seen: string[] = []): boolean {
  if (seen.includes(name)) return false;
  const doc = workflow(name);
  const called = jobsOf(name).flatMap(([, job]) => (job.uses?.startsWith("./.github/workflows/") ? [job.uses.split("/").pop()!] : []));
  return strings(doc).some((text) => /macos-/.test(text)) || called.some((callee) => usesMacos(callee, [...seen, name]));
}

const modeRuns = new Map<string, Record<string, { include: Row[] }>>();

/** What the spike's `mode` job prints for an event, as parsed JSON by output name. The script is run once for each event. */
function modeOutputs(event: string): Record<string, { include: Row[] }> {
  if (!modeRuns.has(event)) modeRuns.set(event, runModeJob(event));
  return modeRuns.get(event)!;
}

function runModeJob(event: string): Record<string, { include: Row[] }> {
  const step = stepsOf(workflow(SPIKE).jobs!.mode!).find((s) => s.id === "mode") ?? assert.fail("the mode job has no step `mode`");
  const dir = mkdtempSync(join(tmpdir(), "ae-mode-"));
  const output = join(dir, "output"), summary = join(dir, "summary");
  const ran = spawnSync("bash", ["-c", step.run!], { encoding: "utf8", env: { PATH: process.env.PATH, EVENT_NAME: event, GITHUB_OUTPUT: output, GITHUB_STEP_SUMMARY: summary } });
  assert.equal(ran.status, 0, ran.stderr);
  const lines = readFileSync(output, "utf8").trim().split("\n");
  return Object.fromEntries(lines.map((line) => [line.slice(0, line.indexOf("=")), JSON.parse(line.slice(line.indexOf("=") + 1))]));
}

/** The rows a job of the spike runs for an event: its matrix is `fromJSON(needs.mode.outputs.<name>)`. A job with no matrix is one row. */
function rowsOf(job: Job, event: string): Row[] {
  const matrix = job.strategy?.matrix;
  if (matrix === undefined) return [{}];
  const output = /needs\.mode\.outputs\.([\w-]+)/.exec(matrix)?.[1] ?? assert.fail(`the matrix ${matrix} is not made by the mode job`);
  return modeOutputs(event)[output]!.include;
}

const macosRows = (event: string): Row[] =>
  jobsOf(SPIKE).flatMap(([, job]) => (/macos/.test(job["runs-on"] ?? "") ? [{}] : rowsOf(job, event).filter((row) => String(row.runner).startsWith("macos"))));

// ---- 1: a new push cancels the run it supersedes ---------------------------------------------------------------------------------------------------------------------------------

test("every workflow with a pull_request trigger has a concurrency group of the pull request that cancels on pull_request", () => {
  const withPullRequest = names.filter((name) => "pull_request" in (workflow(name).on ?? {}));
  assert.ok(withPullRequest.includes("ci.yml") && withPullRequest.includes(SPIKE) && withPullRequest.includes("release-dry-run.yml"), withPullRequest.join(", "));
  for (const name of withPullRequest) {
    const concurrency = workflow(name).concurrency ?? assert.fail(`${name} has no concurrency`);
    assert.match(concurrency.group ?? "", /github\.event\.pull_request\.number/, `${name}: the group names the pull request`);
    const cancel = concurrency["cancel-in-progress"];
    assert.ok(cancel === true || /github\.event_name == 'pull_request'/.test(String(cancel)), `${name}: cancel-in-progress is ${String(cancel)}`);
  }
});

test("a nightly, a dispatch and a release run of the spike and of the dry run are never cancelled", () => {
  for (const name of [SPIKE, "release-dry-run.yml"]) assert.match(String(workflow(name).concurrency!["cancel-in-progress"]), /github\.event_name == 'pull_request'/, name);
});

// ---- 2: macOS runs only for a relevant pull request --------------------------------------------------------------------------------------------------------------------------

test("a workflow with a macOS job, or one that calls a workflow with one, filters its pull_request by paths, filters its push to the stamp that asks for it, and is not run by the merge queue", () => {
  const costly = names.filter((name) => usesMacos(name));
  assert.deepEqual(costly.sort(), ["agreement-round.yml", "playwright-versions-agreement.yml", "release-bundles.yml", "release-dry-run.yml", "middleware-spike.yml", "tree-source-agreement.yml"].sort());
  for (const name of costly) {
    const on = workflow(name).on ?? {};
    assert.ok(!("merge_group" in on), `${name}: not on the merge queue`);
    if ("pull_request" in on) assert.ok(on.pull_request?.paths?.length, `${name}: pull_request has no paths`);
    if ("push" in on) assert.ok(on.push?.paths?.length && on.push.paths.every((path) => path.startsWith("middleware/results/")), `${name}: push is not a stamp file`);
  }
});

test("a pull request runs one macOS job in the spike: the primary Playwright's darwin row, which builds its own bundle", () => {
  const rows = macosRows("pull_request");
  assert.equal(rows.length, 1, JSON.stringify(rows));
  assert.deepEqual([rows[0]!.platform, rows[0]!.playwright, rows[0]!.primary, rows[0]!.build], ["darwin-arm64", "1.64.1", true, true]);
});

test("the nightly, a dispatch and a release run the spike on both platforms, with a bundle, a trace and a demo row for each, and the macOS demo rows take the bundle job's bundle", () => {
  for (const event of ["schedule", "workflow_dispatch", "push"]) {
    const modeOut = modeOutputs(event);
    for (const output of ["bundle", "trace", "demo"]) assert.deepEqual([...new Set(modeOut[output]!.include.map((row) => row.platform))].sort(), ["darwin-arm64", "linux-x64"], `${event}: ${output}`);
    assert.equal(modeOut.demo!.include.filter((row) => row.platform === "darwin-arm64").length, 2, `${event}: both macOS demo rows`);
    assert.ok(modeOut.demo!.include.every((row) => row.build === false), `${event}: no demo row builds a bundle of its own`);
  }
  assert.equal(modeOutputs("pull_request").demo!.include.filter((row) => row.platform === "linux-x64").length, 3, "a pull request runs every Linux demo row");
});

// ---- 3: one build of the bundle for each platform ---------------------------------------------------------------------------------------------------------------------------

/** The platform of each build of the bundle that `build.sh` makes in a run of the spike for an event, with the job that makes it. A step that is `if: matrix.build` runs in the rows that build their own bundle only. */
function buildsOf(event: string): { platform: string; job: string }[] {
  return jobsOf(SPIKE).flatMap(([job, definition]) => stepsOf(definition)
    .filter((step) => /bundle\/build\.sh \$\{\{ matrix\.platform/.test(step.run ?? ""))
    .flatMap((step) => {
      const ownBuildOnly = /matrix\.build/.test(step.if ?? "") && !/!matrix\.build/.test(step.if ?? "");
      return rowsOf(definition, event).filter((row) => !ownBuildOnly || row.build === true).map((row) => ({ platform: String(row.platform), job }));
    }));
}

test("build.sh is never run as a layout-only rebuild, and trace.sh takes the full layout it is given", () => {
  for (const [name, job] of jobsOf(SPIKE)) for (const step of stepsOf(job)) {
    assert.doesNotMatch(step.run ?? "", /--layout-only/, `${name}: a layout-only rebuild`);
    if (/trace\.sh/.test(step.run ?? "")) assert.match(step.run!, /--full-dir/, `${name}: trace.sh builds a layout of its own`);
  }
});

test("a run of the spike builds the bundle once for each platform it runs on, and for no other", () => {
  for (const event of ["pull_request", "schedule"]) {
    const platforms = buildsOf(event).map((build) => build.platform).sort();
    assert.deepEqual(platforms, ["darwin-arm64", "linux-x64"], `${event}: ${JSON.stringify(buildsOf(event))}`);
  }
  assert.deepEqual(buildsOf("pull_request").map((build) => build.job).sort(), ["bundle", "demo"], "a pull request's macOS bundle is built by its one macOS job");
  assert.deepEqual(buildsOf("schedule").map((build) => build.job), ["bundle", "bundle"]);
});

test("the spike does not build the archive twice to compare: that check is release-bundles.yml's, which the dry run calls", () => {
  const compares = (name: string) => strings(workflow(name)).some((text) => /cmp -s/.test(text));
  assert.equal(compares(SPIKE), false);
  assert.equal(compares("release-bundles.yml"), true);
  assert.equal(workflow("release-dry-run.yml").jobs!.bundles!.uses, "./.github/workflows/release-bundles.yml");
  assert.ok("schedule" in (workflow("release-dry-run.yml").on ?? {}), "the dry run is nightly");
});

/** The name of an artifact with the matrix platform left as a placeholder, so that an upload and a download of one platform's file are the same name. */
const artifactName = (step: Step) => (step.with?.name ?? "").replace(/\$\{\{ matrix\.platform \}\}/, "<platform>");

test("the spike still proves what it proved: no browser in the archive, the transcripts, the format choice, the lists, and the live comparison of the lean bundle with the full layout", () => {
  const ran = (job: string, command: RegExp) => stepsOf(workflow(SPIKE).jobs![job]!).some((step) => command.test(step.run ?? ""));
  assert.ok(ran("bundle", /check_no_browser\.py/), "bundle: no browser");
  assert.ok(ran("transcripts", /compare_bundles\.py replay/), "transcripts: replay");
  assert.ok(ran("bundle-format", /sizes\.py"? choose/), "bundle-format: the format is the measured one");
  assert.ok(ran("trace", /trace\.sh/), "trace: the lists");
  assert.ok(ran("demo", /compare_bundles\.py misses/) && ran("demo", /compare_live\.py/), "demo: the live comparison");
});

test("every artifact a job of the spike downloads is uploaded by a job it needs", () => {
  const jobs = new Map(jobsOf(SPIKE));
  const uploadedBy = (name: string) => [...jobs].filter(([, job]) => stepsOf(job).some((step) => step.uses?.startsWith("actions/upload-artifact") && artifactName(step) === name)).map(([job]) => job);
  let downloads = 0;
  for (const [name, job] of jobs) for (const step of stepsOf(job).filter((s) => s.uses?.startsWith("actions/download-artifact") && artifactName(s) !== "")) {
    downloads++;
    const needs = [job.needs ?? []].flat();
    assert.ok(uploadedBy(artifactName(step)).some((uploader) => needs.includes(uploader)), `${name} downloads ${artifactName(step)}, which none of ${needs.join(", ")} uploads`);
  }
  assert.ok(downloads >= 5, "the downloads are found");
});

test("every matrix key a job of the spike reads is in every row the mode job makes for it", () => {
  for (const [name, job] of jobsOf(SPIKE).filter(([, j]) => j.strategy?.matrix)) {
    const keys = [...new Set([...JSON.stringify(job).matchAll(/matrix\.([\w-]+)/g)].map((match) => match[1]!))];
    const rows = ["pull_request", "schedule"].flatMap((event) => rowsOf(job, event));
    for (const row of rows) assert.deepEqual(keys.filter((key) => !(key in row)), [], `${name}: ${JSON.stringify(row)}`);
  }
});

// ---- 4: the spike runs on the nightly, on a dispatch and for a release, and nowhere else -------------------------------------------------------------------------------

test("the spike runs for a pull request that touches it, nightly, on dispatch and by call, and not on a push or the merge queue", () => {
  const on = workflow(SPIKE).on ?? {};
  assert.deepEqual(Object.keys(on).sort(), ["pull_request", "schedule", "workflow_call", "workflow_dispatch"]);
  const paths = on.pull_request!.paths!;
  for (const path of [".github/workflows/middleware-spike.yml", "middleware/bundle/**", "middleware/runtime/**", "middleware/src/**", "middleware/sample-suite/**", "pins.env", "emu/**", "q1/**", "q2/**", "q3/**"]) assert.ok(paths.includes(path), path);
  for (const docs of ["docs/**", "README.md", "middleware/README.md", "middleware/results/**", "middleware/agreement/**"]) assert.ok(!paths.some((path) => path === docs), `${docs} would run the spike`);
  assert.ok(on.pull_request!.types!.includes("ready_for_review"), "a draft that is marked ready runs");
});

test("a draft pull request runs none of the spike's jobs and none of the dry run's", () => {
  for (const name of [SPIKE, "release-dry-run.yml"]) for (const [job, definition] of jobsOf(name)) assert.equal(definition.if, DRAFT, `${name}: ${job}`);
});

test("the dry run is for a pull request that changes the release machinery, and for the nightly and a dispatch", () => {
  const on = workflow("release-dry-run.yml").on ?? {};
  assert.deepEqual(Object.keys(on).sort(), ["pull_request", "schedule", "workflow_dispatch"]);
  assert.deepEqual(on.pull_request!.paths, [".github/workflows/release*.yml", "middleware/release/**", "middleware/bundle/write-pins.mjs", "middleware/pins.json"]);
});

// ---- 5: the measurements run when somebody asks ---------------------------------------------------------------------------------------------------------------------------

test("the three measurement workflows are found, so that the tests below hold each of them", () => {
  assert.deepEqual([...MEASUREMENTS].sort(), ["agreement-round.yml", "playwright-versions-agreement.yml", "tree-source-agreement.yml"]);
});

test("the agreement workflows run when their stamp file is pushed and on dispatch, never on a schedule or a pull request, and a measurement is never cancelled", () => {
  for (const name of MEASUREMENTS) {
    const on = workflow(name).on ?? {};
    assert.deepEqual(Object.keys(on).sort(), ["push", "workflow_dispatch"], name);
    assert.equal(workflow(name).concurrency!["cancel-in-progress"], false, name);
  }
});

test("a dispatch of a measurement is not refused by the guard that keeps the merge of its stamp from running it again", () => {
  for (const name of MEASUREMENTS.filter((measurement) => workflow(measurement).jobs!.reading!.if !== undefined)) {
    const guard = workflow(name).jobs!.reading!.if!;
    assert.match(guard, /github\.event_name == 'workflow_dispatch'/, name);
    assert.match(guard, /github\.ref_name != github\.event\.repository\.default_branch/, name);
  }
});

// ---- 6: the gate passes when the heavy jobs are not run ----------------------------------------------------------------------------------------------------------------

test("gate needs only jobs that always run: ci.yml has no path filter and none of its jobs has a condition, and nothing from another workflow is in it", () => {
  const ci = workflow("ci.yml");
  for (const trigger of Object.values(ci.on ?? {})) assert.equal(trigger?.paths, undefined);
  const needs = [ci.jobs!.gate!.needs].flat();
  assert.deepEqual(needs.sort(), ["middleware", "python"]);
  for (const name of needs) assert.equal(ci.jobs![name!]!.if, undefined, name);
  assert.doesNotMatch(JSON.stringify(ci), /middleware-spike|release-dry-run|release-bundles|tree-source|playwright-versions/);
});

test("gate accepts success only, so a heavy job added to its needs later that a path filter skips would fail it", () => {
  const script = stepsOf(workflow("ci.yml").jobs!.gate!)[0]!.run!;
  assert.match(script, /!= "success"/);
  assert.equal(workflow("ci.yml").jobs!.gate!.if, "always() && !cancelled()");
});
