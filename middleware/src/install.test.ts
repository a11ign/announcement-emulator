import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { bundleName, findBundle } from "./bundle.ts";
import { downloadUrl, install } from "./install.ts";
import type { Pins } from "./pins.ts";

const PLATFORM = "linux-x64";

/** A bundle as the build writes one (a tar.gz with a bundle.json), served over http, and the pins that name it. */
async function served(tamper = false) {
  const work = mkdtempSync(join(tmpdir(), "ae-install-"));
  mkdirSync(join(work, "src", "python"), { recursive: true });
  writeFileSync(join(work, "src", "bundle.json"), JSON.stringify({ name: "x" }));
  writeFileSync(join(work, "src", "python", "marker"), "m");
  const file = "announcement-emulator-bundle-linux-x64.tar.gz";
  execFileSync("tar", ["-czf", join(work, file), "-C", join(work, "src"), "."]);
  const bytes = readFileSync(join(work, file));
  const server = createServer((_, res) => { res.end(tamper ? Buffer.concat([bytes, Buffer.from("x")]) : bytes); });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = (server.address() as { port: number }).port;
  const pins: Pins = { version: "9.9.9", bundles: { [PLATFORM]: { file, sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length } } };
  const env = { ANNOUNCEMENT_EMULATOR_PATH: join(work, "cache"), ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: `http://127.0.0.1:${port}/` };
  return { pins, env, server, cache: join(work, "cache") };
}

test("install downloads the bundle, checks its sha256 against the pin and unpacks it where the middleware looks", async () => {
  const { pins, env, server, cache } = await served();
  try {
    const dir = await install(pins, { env, platform: PLATFORM });
    assert.equal(dir, join(cache, bundleName("9.9.9", PLATFORM)));
    assert.ok(existsSync(join(dir, "python", "marker")));
    assert.equal(findBundle("9.9.9", env), dir);
  } finally { server.close(); }
});

test("a bundle whose sha256 is not the pinned one is refused and nothing is unpacked", async () => {
  const { pins, env, server, cache } = await served(true);
  try {
    await assert.rejects(install(pins, { env, platform: PLATFORM }), /pins/);
    assert.ok(!existsSync(join(cache, bundleName("9.9.9", PLATFORM))));
    assert.equal(findBundle("9.9.9", env), null);
  } finally { server.close(); }
});

test("a second install finds the first and downloads nothing", async () => {
  const { pins, env, server } = await served();
  try {
    await install(pins, { env, platform: PLATFORM });
    server.close();
    const lines: string[] = [];
    await install(pins, { env, platform: PLATFORM, log: (l) => lines.push(l) });
    assert.match(lines[0]!, /already installed/);
  } finally { server.close(); }
});

test("with no download host the install says what to set, and for a platform with no bundle what there is", () => {
  const pins: Pins = { version: "1.0.0", bundles: { [PLATFORM]: { file: "f", sha256: "0", bytes: 1 } } };
  assert.throws(() => downloadUrl(pins, PLATFORM, {}), /ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST/);
  assert.throws(() => downloadUrl(pins, "win32-x64", { ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: "http://h" }), /has: linux-x64/);
  assert.equal(downloadUrl(pins, PLATFORM, { ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: "http://h/" }), "http://h/f");
});
