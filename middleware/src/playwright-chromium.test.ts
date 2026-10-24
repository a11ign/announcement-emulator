import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { browsersRoot, extensionVerdict, launchChannel, readPlaywright, type PlaywrightChromium } from "./playwright-chromium.ts";

interface Fake { version: string; chromium: [string, string]; shell: [string, string] | null; install: "both" | "shell" | "none" }

/** A project directory with the `node_modules` layout of a Playwright: `@playwright/test` needs `playwright`, which needs `playwright-core`, whose `browsers.json` names the Chromium and whose `chromium.executablePath()` says where it is. */
function project(fake: Fake): string {
  const dir = mkdtempSync(join(tmpdir(), "ae-pw-"));
  const put = (path: string, text: string) => { mkdirSync(join(dir, path, ".."), { recursive: true }); writeFileSync(join(dir, path), text); };
  put("node_modules/@playwright/test/package.json", JSON.stringify({ name: "@playwright/test", version: fake.version }));
  put("node_modules/playwright/package.json", JSON.stringify({ name: "playwright", version: fake.version }));
  put("node_modules/playwright-core/package.json", JSON.stringify({ name: "playwright-core", version: fake.version, main: "index.js" }));
  const browsers = [{ name: "chromium", revision: fake.chromium[0], browserVersion: fake.chromium[1] }, ...(fake.shell ? [{ name: "chromium-headless-shell", revision: fake.shell[0], browserVersion: fake.shell[1] }] : [])];
  put("node_modules/playwright-core/browsers.json", JSON.stringify({ browsers }));
  const executable = join(dir, "browsers", `chromium-${fake.chromium[0]}`, "chrome-linux64", "chrome");
  put("node_modules/playwright-core/index.js", `exports.chromium = { executablePath: () => ${JSON.stringify(executable)} };`);
  if (fake.install === "both") put(`browsers/chromium-${fake.chromium[0]}/chrome-linux64/chrome`, "");
  if (fake.shell && fake.install !== "none") put(`browsers/chromium_headless_shell-${fake.shell[0]}/chrome-linux/headless_shell`, "");
  return dir;
}

test("the team's Playwright version, the Chromium build its browsers.json names and what is installed are read from the team's project", () => {
  const dir = project({ version: "1.63.0", chromium: ["1243", "153.0.8010.12"], shell: ["1243", "153.0.8010.12"], install: "both" });
  const pw = readPlaywright(dir)!;
  assert.equal(pw.version, "1.63.0");
  assert.deepEqual(pw.chromium, { revision: "1243", build: "153.0.8010.12" });
  assert.deepEqual(pw.headlessShell, { revision: "1243", build: "153.0.8010.12" });
  assert.equal(pw.fullInstalled, true);
  assert.equal(pw.shellInstalled, true);
});

test("a project with only the headless shell installed (--only-shell) has no full Chromium", () => {
  const pw = readPlaywright(project({ version: "1.64.1", chromium: ["1248", "156.0.8078.4"], shell: ["1248", "156.0.8078.4"], install: "shell" }))!;
  assert.equal(pw.fullInstalled, false);
  assert.equal(pw.shellInstalled, true);
});

test("a project with no browser installed has neither", () => {
  const pw = readPlaywright(project({ version: "1.64.1", chromium: ["1248", "156.0.8078.4"], shell: ["1248", "156.0.8078.4"], install: "none" }))!;
  assert.deepEqual([pw.fullInstalled, pw.shellInstalled], [false, false]);
});

test("a Playwright before 1.49 has no headless shell in browsers.json", () => {
  const pw = readPlaywright(project({ version: "1.48.2", chromium: ["1140", "130.0.6723.31"], shell: null, install: "both" }))!;
  assert.equal(pw.headlessShell, null);
  assert.equal(pw.shellInstalled, false);
});

test("where there is no Playwright nothing is thrown", () => {
  assert.equal(readPlaywright(mkdtempSync(join(tmpdir(), "ae-none-"))), null);
});

test("the Playwright this package is built against is read through its pnpm layout: its version is the one in package.json", () => {
  const pw = readPlaywright()!;
  const wanted = JSON.parse(readFileSync(join(import.meta.dirname, "..", "package.json"), "utf8")).devDependencies["@playwright/test"];
  assert.equal(pw.version, wanted);
  assert.match(pw.chromium.build, /^\d+\.\d+\.\d+\.\d+$/);
  assert.match(pw.chromium.revision, /^\d+$/);
});

test("the browsers directory is the parent of the chromium-<revision> directory, on both platforms", () => {
  assert.equal(browsersRoot("/home/u/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"), "/home/u/.cache/ms-playwright");
  assert.equal(browsersRoot("/Users/u/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"), "/Users/u/Library/Caches/ms-playwright");
  assert.equal(browsersRoot("/opt/chrome/chrome"), null);
});

const pw = (over: Partial<PlaywrightChromium> = {}): PlaywrightChromium => ({
  version: "1.64.1", chromium: { revision: "1248", build: "156.0.8078.4" }, headlessShell: { revision: "1248", build: "156.0.8078.4" }, executablePath: "/x/chromium-1248/chrome", fullInstalled: true, shellInstalled: true, ...over,
});

test("the extension is expected to load in the full Chromium of a launch left to Playwright", () => {
  assert.equal(extensionVerdict(pw()).ok, true);
  assert.equal(extensionVerdict(pw(), { headless: false }).ok, true);
});

test("the extension is not expected to load where the team chose the browser, or the full Chromium is missing, and the reason says what to do", () => {
  assert.match(extensionVerdict(pw(), { channel: "chrome" }).why, /channel "chrome"/);
  assert.match(extensionVerdict(pw(), { channel: "msedge" }).why, /channel "msedge"/);
  assert.match(extensionVerdict(pw(), { executablePath: "/x" }).why, /executablePath/);
  const missing = extensionVerdict(pw({ fullInstalled: false }));
  assert.equal(missing.ok, false);
  assert.match(missing.why, /npx playwright install chromium, without --only-shell/);
  assert.equal(extensionVerdict(null).ok, false);
});

test("the channel \"chromium\" is added to a headless launch left to Playwright and to nothing else", () => {
  assert.equal(launchChannel(pw()), "chromium");
  assert.equal(launchChannel(pw(), { headless: true }), "chromium");
  assert.equal(launchChannel(pw(), { headless: false }), undefined);
  assert.equal(launchChannel(pw(), { channel: "chromium" }), undefined);
  assert.equal(launchChannel(pw(), { channel: "chrome" }), undefined);
  assert.equal(launchChannel(pw(), { executablePath: "/x" }), undefined);
  assert.equal(launchChannel(pw({ fullInstalled: false }), {}), undefined);
  assert.equal(launchChannel(pw({ headlessShell: null }), {}), undefined);
  assert.equal(launchChannel(null, {}), undefined);
});
