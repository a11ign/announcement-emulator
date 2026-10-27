#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { doctor } from "./doctor.ts";
import { install } from "./install.ts";
import { readPins } from "./pins.ts";
import { wrapperSource } from "./wrapper.ts";

const USAGE = `foresay <command>

  install            download the runtime bundle this package is pinned to into the cache (like \`npx playwright install\`)
  test [playwright test args]
                     run your Playwright tests with the middleware attached, without changing a file: it writes a wrapper config beside yours, runs \`playwright test\` with it, and removes it
  doctor             say which Playwright and Chromium your tests run in and whether that build has a measured agreement rate, where the bundle is, and whether its parts start

Everything this prints about speech is a prediction, never a reading of NVDA, and never evidence.`;

const CONFIGS = ["playwright.config.ts", "playwright.config.mts", "playwright.config.js", "playwright.config.mjs", "playwright.config.cjs"];

async function main(argv: string[]): Promise<number> {
  const [command, ...rest] = argv;
  if (command === "install") { await install(readPins(), { log: (l) => console.log(`foresay: ${l}`) }); return 0; }
  if (command === "test") return runTests(rest);
  if (command === "doctor") return doctor();
  console.log(USAGE);
  return command ? 1 : 0;
}

function configFrom(args: string[]): { path: string; rest: string[] } {
  const rest = [...args];
  const at = rest.findIndex((a) => a === "-c" || a === "--config");
  if (at >= 0) { const [, value] = rest.splice(at, 2); return { path: resolve(value!), rest }; }
  const found = CONFIGS.map((c) => resolve(c)).find(existsSync);
  if (!found) throw new Error("foresay: no playwright.config.* here; pass --config <file>");
  return { path: found, rest };
}

async function runTests(args: string[]): Promise<number> {
  const { path, rest } = configFrom(args);
  const wrapper = join(dirname(path), `.foresay.config${path.endsWith(".ts") || path.endsWith(".mts") ? ".ts" : ".mjs"}`);
  writeFileSync(wrapper, wrapperSource(path));
  try {
    const cli = createRequire(path).resolve("@playwright/test/cli");
    const child = spawn(process.execPath, [cli, "test", "--config", wrapper, ...rest], { stdio: "inherit", cwd: dirname(path) });
    return await new Promise((done) => child.on("exit", (code) => done(code ?? 1)));
  } finally {
    rmSync(wrapper, { force: true });
  }
}

main(process.argv.slice(2)).then((code) => process.exit(code), (error: Error) => { console.error(error.message); process.exit(1); });
