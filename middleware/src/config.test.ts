import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { PlaywrightTestConfig } from "@playwright/test";
import { withAnnouncements as announce } from "./config.ts";
import { readPins } from "./pins.ts";
import { RUN_ENV } from "./run.ts";

/** A bundle as `findBundle` knows one: a directory with the manifest. */
function fakeBundle(): string {
  const dir = mkdtempSync(join(tmpdir(), "ae-bundle-"));
  writeFileSync(join(dir, "bundle.json"), "{}");
  return dir;
}

function withEnv<T>(env: Record<string, string | undefined>, body: () => T): T {
  const before = Object.fromEntries(Object.keys(env).map((k) => [k, process.env[k]]));
  for (const [k, v] of Object.entries(env)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  try { return body(); } finally { for (const [k, v] of Object.entries(before)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; } }
}

/** `withAnnouncements` keeps the type of the config it is given; these tests look inside the result, so they ask for the general one. */
const withAnnouncements = (config: PlaywrightTestConfig) => announce(config);

const run = (bundle: string) => JSON.stringify({ bundle, dir: "/tmp/x", ports: [{ collector: 41001, cdp: 41002 }], verify: false, sweeps: true });

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

test("the reporter is given the bundle and the options, and nothing about an extension", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle }, () => {
    const options = ((announce({}, { sweeps: false, verify: true }) as PlaywrightTestConfig).reporter as unknown as [string, Record<string, unknown>][])[0]![1];
    assert.deepEqual(options, { bundle, sweeps: false, verify: true });
  });
});

test("in a worker a chromium project is launched with the port and the accessibility flag, and nothing else is added: no extension, no channel", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    const config = withAnnouncements({ use: { launchOptions: { args: ["--mine"] } }, projects: [{ name: "a", use: { browserName: "chromium" } }] });
    const launch = config.use!.launchOptions!;
    assert.deepEqual(launch.args, ["--mine", "--force-renderer-accessibility", "--remote-debugging-port=41002"]);
    assert.equal(launch.ignoreDefaultArgs, undefined);
    assert.equal(launch.executablePath, undefined);
    assert.equal(config.use!.channel, undefined);
    assert.equal(config.projects![0]!.use!.launchOptions!.executablePath, undefined);
    assert.deepEqual(config.projects![0]!.use!.launchOptions!.args, ["--force-renderer-accessibility", "--remote-debugging-port=41002"]);
  });
});

test("the browser is Playwright's: no launch option names an executablePath or a library path, and the team's own env is kept as it was", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    const use = withAnnouncements({ use: { launchOptions: { env: { MINE: "1" } } } }).use!;
    assert.equal(use.launchOptions!.executablePath, undefined);
    assert.deepEqual(use.launchOptions!.env, { MINE: "1" });
    assert.equal(JSON.stringify(use).includes(bundle), false, "nothing in the launch names the bundle");
    assert.equal(JSON.stringify(use).includes("LD_LIBRARY_PATH"), false);
  });
});

/** The `use` a config with the given `use` comes out with in a worker. */
function inWorker(use: NonNullable<PlaywrightTestConfig["use"]>, projects?: PlaywrightTestConfig["projects"]) {
  const bundle = fakeBundle();
  return withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => withAnnouncements({ use, projects }));
}

test("a launch is left to the browser the team chose: a headless launch left to Playwright keeps the headless shell, a headed one and a channel or an executablePath are not changed", () => {
  assert.equal(inWorker({}).use!.channel, undefined);
  assert.equal(inWorker({ headless: true }).use!.channel, undefined);
  assert.equal(inWorker({ headless: false }).use!.channel, undefined);
  assert.equal(inWorker({ channel: "chromium" }).use!.channel, "chromium");
  assert.equal(inWorker({ channel: "chrome" }).use!.channel, "chrome");
  const own = inWorker({ launchOptions: { executablePath: "/team/chrome" } });
  assert.equal(own.use!.launchOptions!.executablePath, "/team/chrome");
  assert.equal(own.use!.channel, undefined);
  assert.ok(own.use!.launchOptions!.args!.includes("--remote-debugging-port=41002"));
});

test("a channel the team set at the top is seen from a project that sets none, and the project is not given another", () => {
  const config = inWorker({ channel: "msedge" }, [{ name: "a", use: { browserName: "chromium", viewport: { width: 1, height: 1 } } }]);
  assert.equal(config.projects![0]!.use!.channel, undefined);
  assert.equal(config.use!.channel, "msedge");
});

test("a chromium project is given the flags whether or not it shares the config's use with a firefox project, and the firefox project is not", () => {
  const config = inWorker({}, [{ name: "plain" }, { name: "ff", use: { browserName: "firefox" } }, { name: "c", use: { browserName: "chromium" } }]);
  assert.ok(config.use!.launchOptions!.args!.includes("--remote-debugging-port=41002"));
  assert.ok(config.projects![2]!.use!.launchOptions!.args!.includes("--remote-debugging-port=41002"));
  assert.deepEqual(config.projects![1]!.use, { browserName: "firefox" });
});

test("firefox and webkit projects are left as they were", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    const config = withAnnouncements({ projects: [{ name: "ff", use: { browserName: "firefox" } }, { name: "wk", use: { browserName: "webkit" } }] });
    assert.deepEqual(config.projects!.map((p) => p.use), [{ browserName: "firefox" }, { browserName: "webkit" }]);
  });
});

test("a project made of a firefox or webkit device is left alone: it is given no chromium flag", () => {
  const firefox = { defaultBrowserType: "firefox" } as NonNullable<PlaywrightTestConfig["use"]>;
  const config = inWorker({}, [{ name: "c", use: { browserName: "chromium" } }, { name: "ff", use: firefox }]);
  assert.ok(config.projects![0]!.use!.launchOptions!.args!.includes("--force-renderer-accessibility"));
  assert.deepEqual(config.projects![1]!.use, firefox);
});

test("outside a worker the launch options are not touched", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: undefined, TEST_PARALLEL_INDEX: undefined }, () => {
    const use = { baseURL: "http://x" };
    assert.deepEqual(withAnnouncements({ use }).use, use);
  });
});

test("the package's pins name the version the bundle is looked up by", () => {
  assert.match(readPins().version, /^\d+\.\d+\.\d+/);
});

test("a project's launchOptions replace the config's, as Playwright merges them: the flags are put on the project's own", () => {
  const config = inWorker({ launchOptions: { executablePath: "/team/chrome" } }, [{ name: "a", use: { browserName: "chromium", launchOptions: { slowMo: 50 } } }]);
  assert.equal(config.projects![0]!.use!.launchOptions!.slowMo, 50);
  assert.deepEqual(config.projects![0]!.use!.launchOptions!.args, ["--force-renderer-accessibility", "--remote-debugging-port=41002"]);
});
