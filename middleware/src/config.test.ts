import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { PlaywrightTestConfig } from "@playwright/test";
import { ignoring, withAnnouncements as wrap } from "./config.ts";
import { readPins } from "./pins.ts";
import { RUN_ENV } from "./run.ts";

/** A bundle as `findBundle` knows one: a directory with the manifest and the two files the config reads. */
function fakeBundle(): string {
  const dir = mkdtempSync(join(tmpdir(), "ae-bundle-"));
  mkdirSync(join(dir, "q1"), { recursive: true });
  writeFileSync(join(dir, "bundle.json"), "{}");
  writeFileSync(join(dir, "q1", "ext-id.txt"), "abcdefghijklmnopabcdefghijklmnop\n");
  return dir;
}

function withEnv<T>(env: Record<string, string | undefined>, body: () => T): T {
  const before = Object.fromEntries(Object.keys(env).map((k) => [k, process.env[k]]));
  for (const [k, v] of Object.entries(env)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  try { return body(); } finally { for (const [k, v] of Object.entries(before)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; } }
}

/** `withAnnouncements` keeps the type of the config it is given; these tests look inside the result, so they ask for the general one. */
const withAnnouncements = (config: PlaywrightTestConfig) => wrap(config);

const run = (bundle: string) => JSON.stringify({ bundle, dir: "/tmp/x", ports: [{ collector: 41001, cdp: 41002 }], extensions: ["/tmp/x/extension-0"], verify: false, sweeps: true });

test("without a bundle the one line says what to run", () => {
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: join(tmpdir(), "no-such-bundle") }, () => {
    assert.throws(() => withAnnouncements({}), /npx announcement-emulator install/);
  });
});

test("the config gets a reporter first, and keeps the reporters it had", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle }, () => {
    const config = withAnnouncements({ reporter: [["html", { open: "never" }], ["json"]] });
    const reporters = config.reporter as unknown as [string, unknown?][];
    assert.match(reporters[0]![0], /reporter\.mjs$/);
    assert.deepEqual(reporters.slice(1), [["html", { open: "never" }], ["json"]]);
  });
});

test("a config with no reporter keeps the one Playwright would have used", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, CI: undefined }, () => {
    const reporters = withAnnouncements({}).reporter as unknown as [string][];
    assert.deepEqual(reporters.slice(1), [["list"]]);
  });
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, CI: "1" }, () => {
    const reporters = withAnnouncements({}).reporter as unknown as [string][];
    assert.deepEqual(reporters.slice(1), [["dot"]]);
  });
});

test("a single reporter given as a name or as a pair is kept", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle }, () => {
    assert.deepEqual((withAnnouncements({ reporter: "dot" }).reporter as unknown as unknown[]).slice(1), [["dot"]]);
    assert.deepEqual((withAnnouncements({ reporter: ["html", { open: "never" }] } as unknown as PlaywrightTestConfig).reporter as unknown as unknown[]).slice(1), [["html", { open: "never" }]]);
  });
});

test("in a worker a chromium project is launched with the bundle's browser, the extension and the flags the ticket names", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    const config = withAnnouncements({ use: { launchOptions: { args: ["--mine"] } }, projects: [{ name: "a", use: { browserName: "chromium" } }] });
    const launch = config.use!.launchOptions!;
    assert.match(launch.executablePath!, /chrome/);
    assert.ok(launch.args!.includes("--mine"));
    for (const flag of ["--force-renderer-accessibility", "--load-extension=/tmp/x/extension-0", "--allowlisted-extension-id=abcdefghijklmnopabcdefghijklmnop", "--remote-debugging-port=41002",
      "--disable-features=DisableLoadExtensionCommandLineSwitch"]) assert.ok(launch.args!.includes(flag), flag);
    assert.deepEqual(launch.ignoreDefaultArgs, ["--disable-extensions"]);
    assert.ok(config.projects![0]!.use!.launchOptions!.executablePath);
  });
});

test("firefox and webkit projects are left as they were", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    const config = withAnnouncements({ projects: [{ name: "ff", use: { browserName: "firefox" } }, { name: "wk", use: { browserName: "webkit" } }] });
    assert.deepEqual(config.projects!.map((p) => p.use), [{ browserName: "firefox" }, { browserName: "webkit" }]);
  });
});

test("outside a worker the launch options are not touched", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: undefined, TEST_PARALLEL_INDEX: undefined }, () => {
    const use = { baseURL: "http://x" };
    assert.deepEqual(withAnnouncements({ use }).use, use);
  });
});

test("--disable-extensions is added to what is ignored, and ignoring everything stays so", () => {
  assert.deepEqual(ignoring(undefined, "--disable-extensions"), ["--disable-extensions"]);
  assert.deepEqual(ignoring(["--x"], "--disable-extensions"), ["--x", "--disable-extensions"]);
  assert.deepEqual(ignoring(["--disable-extensions"], "--disable-extensions"), ["--disable-extensions"]);
  assert.equal(ignoring(true, "--disable-extensions"), true);
});

test("the package's pins name the version the bundle is looked up by", () => {
  assert.match(readPins().version, /^\d+\.\d+\.\d+/);
});
