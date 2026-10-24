import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { PlaywrightTestConfig } from "@playwright/test";
import { announce, ignoring } from "./config.ts";
import type { PlaywrightChromium } from "./playwright-chromium.ts";
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

/** The facts of a Playwright 1.64.1 whose full Chromium and headless shell are installed: what `npx playwright install chromium` leaves. */
const installed: PlaywrightChromium = {
  version: "1.64.1", chromium: { revision: "1248", build: "156.0.8078.4" }, headlessShell: { revision: "1248", build: "156.0.8078.4" },
  executablePath: "/pw/chromium-1248/chrome-linux64/chrome", fullInstalled: true, shellInstalled: true,
};
/** What `npx playwright install --only-shell chromium` leaves. */
const onlyShell: PlaywrightChromium = { ...installed, fullInstalled: false };
/** Playwright 1.48: its headless mode is the old one, and `browsers.json` has no headless shell. */
const before149: PlaywrightChromium = { ...installed, version: "1.48.2", headlessShell: null, shellInstalled: false };

/** `withAnnouncements` keeps the type of the config it is given; these tests look inside the result, so they ask for the general one. */
const withAnnouncements = (config: PlaywrightTestConfig, playwright: PlaywrightChromium | null = installed) => announce(config, {}, playwright);
/** What the reporter is told about whether the extension can load in the config's chromium projects. */
const extensionOf = (config: PlaywrightTestConfig) => (config.reporter as unknown as [string, { extension: { ok: boolean; why: string } }][])[0]![1].extension;

const run = (bundle: string, tree?: string) => JSON.stringify({ bundle, dir: "/tmp/x", ports: [{ collector: 41001, cdp: 41002 }], extensions: ["/tmp/x/extension-0"], verify: false, sweeps: true, ...(tree ? { tree } : {}) });

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

test("where the tree is read through the DevTools port the browser is launched with no extension, and with the port and the accessibility flag", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle, "devtools"), TEST_PARALLEL_INDEX: "0" }, () => {
    const launch = withAnnouncements({ use: { launchOptions: { args: ["--mine"] } } }).use!.launchOptions!;
    assert.deepEqual(launch.args, ["--mine", "--force-renderer-accessibility", "--remote-debugging-port=41002"]);
    assert.equal(launch.ignoreDefaultArgs, undefined);
    assert.equal(launch.executablePath, undefined);
  });
});

test("the browser is Playwright's: no launch option names an executablePath or a library path, and the team's own env is kept as it was", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    for (const tree of [undefined, "devtools"]) {
      withEnv({ [RUN_ENV]: run(bundle, tree) }, () => {
        const use = withAnnouncements({ use: { launchOptions: { env: { MINE: "1" } } } }).use!;
        assert.equal(use.launchOptions!.executablePath, undefined);
        assert.deepEqual(use.launchOptions!.env, { MINE: "1" });
        assert.equal(JSON.stringify(use).includes(bundle), false, "nothing in the launch names the bundle");
        assert.equal(JSON.stringify(use).includes("LD_LIBRARY_PATH"), false);
      });
    }
  });
});

test("in a worker a chromium project is launched in Playwright's browser with the extension and the flags the ticket names", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => {
    const config = withAnnouncements({ use: { launchOptions: { args: ["--mine"] } }, projects: [{ name: "a", use: { browserName: "chromium" } }] });
    const launch = config.use!.launchOptions!;
    assert.equal(launch.executablePath, undefined);
    assert.ok(launch.args!.includes("--mine"));
    for (const flag of ["--force-renderer-accessibility", "--load-extension=/tmp/x/extension-0", "--allowlisted-extension-id=abcdefghijklmnopabcdefghijklmnop", "--remote-debugging-port=41002",
      "--disable-features=DisableLoadExtensionCommandLineSwitch"]) assert.ok(launch.args!.includes(flag), flag);
    assert.deepEqual(launch.ignoreDefaultArgs, ["--disable-extensions"]);
    assert.equal(config.projects![0]!.use!.launchOptions!.executablePath, undefined);
  });
});

/** A worker of the extension source, and the `use` a config with the given `use` comes out with. */
function inWorker(use: NonNullable<PlaywrightTestConfig["use"]>, playwright: PlaywrightChromium | null = installed, projects?: PlaywrightTestConfig["projects"]) {
  const bundle = fakeBundle();
  return withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle), TEST_PARALLEL_INDEX: "0" }, () => withAnnouncements({ use, projects }, playwright));
}

test("a headless launch left to Playwright is run in the full Chromium, because the headless shell loads no extension", () => {
  assert.equal(inWorker({}).use!.channel, "chromium");
  assert.equal(inWorker({ headless: true }).use!.channel, "chromium");
});

test("a headed launch is left to Playwright as it is: it already runs the full Chromium", () => {
  assert.equal(inWorker({ headless: false }).use!.channel, undefined);
});

test("where the tree is read through the DevTools port the headless shell is left alone: it reads that tree", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: run(bundle, "devtools"), TEST_PARALLEL_INDEX: "0" }, () => {
    assert.equal(withAnnouncements({ use: {} }).use!.channel, undefined);
  });
});

test("a channel or an executablePath the team chose is not changed, and the reporter is told the extension is not expected to load there", () => {
  const chrome = inWorker({ channel: "chrome" });
  assert.equal(chrome.use!.channel, "chrome");
  const own = inWorker({ launchOptions: { executablePath: "/team/chrome" } });
  assert.equal(own.use!.launchOptions!.executablePath, "/team/chrome");
  assert.equal(own.use!.channel, undefined);
  assert.equal(extensionOf(chrome as PlaywrightTestConfig).ok, false);
  assert.match(extensionOf(chrome as PlaywrightTestConfig).why, /channel "chrome"/);
  assert.match(extensionOf(own as PlaywrightTestConfig).why, /executablePath/);
});

test("a channel the team set at the top is seen from a project that sets none, and the project is not given another", () => {
  const config = inWorker({ channel: "msedge" }, installed, [{ name: "a", use: { browserName: "chromium", viewport: { width: 1, height: 1 } } }]);
  assert.equal(config.projects![0]!.use!.channel, undefined);
  assert.equal(config.use!.channel, "msedge");
});

test("a team that chose the channel \"chromium\" itself keeps it, and the extension is expected to load", () => {
  const config = inWorker({ channel: "chromium" });
  assert.equal(config.use!.channel, "chromium");
  assert.equal(extensionOf(config as PlaywrightTestConfig).ok, true);
});

test("with only the headless shell installed the launch is not changed, and the reporter is told which command installs the browser", () => {
  const config = inWorker({}, onlyShell);
  assert.equal(config.use!.channel, undefined);
  assert.equal(extensionOf(config as PlaywrightTestConfig).ok, false);
  assert.match(extensionOf(config as PlaywrightTestConfig).why, /npx playwright install chromium/);
});

test("a Playwright before 1.49 runs headless in the old mode, which loads no extension: headed it does", () => {
  assert.equal(inWorker({}, before149).use!.channel, undefined);
  assert.equal(extensionOf(inWorker({}, before149) as PlaywrightTestConfig).ok, false);
  assert.equal(extensionOf(inWorker({ headless: false }, before149) as PlaywrightTestConfig).ok, true);
});

test("a Playwright that could not be read leaves every launch as it is, and the DevTools source is expected", () => {
  const config = inWorker({}, null);
  assert.equal(config.use!.channel, undefined);
  assert.equal(extensionOf(config as PlaywrightTestConfig).ok, false);
});

test("the extension is expected to load only if it is in every chromium project, and a firefox project does not count", () => {
  const bundle = fakeBundle();
  withEnv({ ANNOUNCEMENT_EMULATOR_BUNDLE: bundle, [RUN_ENV]: undefined }, () => {
    const mixed = withAnnouncements({ projects: [{ name: "a", use: { browserName: "chromium" } }, { name: "b", use: { browserName: "chromium", channel: "chrome" } }] });
    assert.equal(extensionOf(mixed).ok, false);
    const withFirefox = withAnnouncements({ projects: [{ name: "a", use: { browserName: "chromium" } }, { name: "ff", use: { browserName: "firefox", channel: "firefox-beta" } }] });
    assert.equal(extensionOf(withFirefox).ok, true);
    assert.equal(extensionOf(withAnnouncements({})).ok, true);
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
