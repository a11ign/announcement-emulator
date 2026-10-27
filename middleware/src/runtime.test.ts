import { test } from "node:test";
import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Runtime } from "./runtime.ts";

/** A bundle whose Python is a script that writes the command line it was started with, says the runtime is ready, and waits for the quit. */
function bundleThatWritesItsArguments() {
  const bundle = mkdtempSync(join(tmpdir(), "ae-runtime-"));
  mkdirSync(join(bundle, "python", "bin"), { recursive: true });
  const python = join(bundle, "python", "bin", "python3");
  writeFileSync(python, `#!/bin/sh\necho "$@" > "$0.args"\necho '{"type":"ready","bootMs":1}'\nread line\n`);
  chmodSync(python, 0o755);
  return { bundle, args: () => readFileSync(`${python}.args`, "utf8").trim().split(" ") };
}

async function started(options: ConstructorParameters<typeof Runtime>[2] = {}) {
  const { bundle, args } = bundleThatWritesItsArguments();
  const runtime = new Runtime(bundle, { collector: 41001, cdp: 41002 }, options);
  await runtime.ready;
  await runtime.stop();
  return args();
}

test("the runtime is told to check each incremental read of the tree against a read from scratch only when the config asks for it (A11-229)", async () => {
  assert.ok((await started({ verify: true })).includes("--verify"));
  assert.ok(!(await started()).includes("--verify"));
  assert.ok(!(await started({ verify: false })).includes("--verify"));
});

test("the runtime is told where the collector and the browser's DevTools port are, and is not told which tree source to use: there is one", async () => {
  const args = await started();
  assert.deepEqual(args.slice(args.indexOf("--port"), args.indexOf("--port") + 4), ["--port", "41001", "--cdp", "41002"]);
  assert.ok(!args.includes("--tree") && !args.includes("--fallback-after"));
});
