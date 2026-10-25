import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { bundleName, findBundle } from "./bundle.ts";
import { bundleSource, install, releaseBaseUrl, repositoryUrl } from "./install.ts";
import type { Pins } from "./pins.ts";

const PLATFORM = "linux-x64";

const FORMATS = [
  { extension: "gz", flag: "-z" },
  { extension: "xz", flag: "-J" },
  { extension: "zst", flag: "--zstd" },
] as const;
type Format = (typeof FORMATS)[number];

/** Whether this host's tar can write the format, and so unpack it: the bundle is read with the same tar (install.ts). */
function tarCan(format: Format): boolean {
  try {
    const source = mkdtempSync(join(tmpdir(), "ae-tar-src-")), out = mkdtempSync(join(tmpdir(), "ae-tar-out-"));
    writeFileSync(join(source, "f"), "f");
    execFileSync("tar", [format.flag, "-cf", join(out, `t.tar.${format.extension}`), "-C", source, "."], { stdio: "ignore" });
    return true;
  } catch { return false; }
}

const VERSION = "9.9.9";

/** A bundle as the build writes one (a tar with a bundle.json, compressed), laid out on an http server the way a GitHub Release lays out its assets (`/v<version>/<file>`), and the pins that name it. `requests` is every path the server was asked for. */
async function served(tamper = false, format: Format = FORMATS[0]) {
  const work = mkdtempSync(join(tmpdir(), "ae-install-"));
  mkdirSync(join(work, "src", "python"), { recursive: true });
  writeFileSync(join(work, "src", "bundle.json"), JSON.stringify({ name: "x" }));
  writeFileSync(join(work, "src", "python", "marker"), "m");
  const file = `announcement-emulator-bundle-linux-x64.tar.${format.extension}`;
  execFileSync("tar", [format.flag, "-cf", join(work, file), "-C", join(work, "src"), "."]);
  const bytes = readFileSync(join(work, file));
  const requests: string[] = [];
  const server = createServer((request, res) => {
    requests.push(request.url ?? "");
    if (request.url !== `/v${VERSION}/${file}`) { res.statusCode = 404; res.end(); return; }
    res.end(tamper ? Buffer.concat([bytes, Buffer.from("x")]) : bytes);
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  const pins: Pins = { version: VERSION, bundles: { [PLATFORM]: { file, sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length } } };
  const env = { ANNOUNCEMENT_EMULATOR_PATH: join(work, "cache") };
  return { pins, env, server, origin, requests, releaseBase: `${origin}/v${VERSION}/`, cache: join(work, "cache") };
}

test("install from a fixture release: the bundle is downloaded from the version's Release path, checked against the pin and unpacked where the middleware looks", async () => {
  const { pins, env, server, cache, releaseBase, requests } = await served();
  try {
    const dir = await install(pins, { env, platform: PLATFORM, releaseBase });
    assert.equal(dir, join(cache, bundleName(VERSION, PLATFORM)));
    assert.ok(existsSync(join(dir, "python", "marker")));
    assert.equal(findBundle(VERSION, env), dir);
    assert.deepEqual(requests, [`/v${VERSION}/${pins.bundles[PLATFORM]!.file}`]);
  } finally { server.close(); }
});

for (const format of FORMATS) {
  test(`install unpacks a .tar.${format.extension} bundle from the release with the host's tar`, { skip: !tarCan(format) && `this host's tar cannot write .${format.extension}` }, async () => {
    const { pins, env, server, releaseBase } = await served(false, format);
    try {
      assert.ok(pins.bundles[PLATFORM]!.file.endsWith(`.tar.${format.extension}`));
      const dir = await install(pins, { env, platform: PLATFORM, releaseBase });
      assert.ok(existsSync(join(dir, "python", "marker")));
      assert.equal(readFileSync(join(dir, "bundle.json"), "utf8"), JSON.stringify({ name: "x" }));
    } finally { server.close(); }
  });
}

test("a release bundle whose sha256 is not the pinned one is refused, naming the Release, and nothing is unpacked or left behind", async () => {
  const { pins, env, server, cache, releaseBase } = await served(true);
  try {
    await assert.rejects(install(pins, { env, platform: PLATFORM, releaseBase }), /has sha256 [0-9a-f]{64}, and this package pins [0-9a-f]{64}.*Nothing was unpacked/);
    await assert.rejects(install(pins, { env, platform: PLATFORM, releaseBase }), /the Release v9\.9\.9/);
    assert.ok(!existsSync(join(cache, bundleName(VERSION, PLATFORM))));
    assert.deepEqual(readdirSync(cache), []);      // the archive that failed the check is deleted
    assert.equal(findBundle(VERSION, env), null);
  } finally { server.close(); }
});

test("the mirror variable replaces the Release: the bundle comes from <host>/v<version>/<file> and the Release's server is not asked", async () => {
  const mirror = await served(), release = await served();
  try {
    for (const host of [mirror.origin, `${mirror.origin}/`]) {
      const env = { ...mirror.env, ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: host };
      const dir = await install(mirror.pins, { env, platform: PLATFORM, releaseBase: release.releaseBase });
      assert.ok(existsSync(join(dir, "python", "marker")));
      rmSync(mirror.cache, { recursive: true, force: true });
    }
    assert.deepEqual(mirror.requests, [`/v${VERSION}/${mirror.pins.bundles[PLATFORM]!.file}`, `/v${VERSION}/${mirror.pins.bundles[PLATFORM]!.file}`]);
    assert.deepEqual(release.requests, []);
  } finally { mirror.server.close(); release.server.close(); }
});

test("a mirror cannot change what is pinned: a mirrored bundle with another sha256 is refused, naming the mirror", async () => {
  const mirror = await served(true);
  try {
    const env = { ...mirror.env, ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: mirror.origin };
    await assert.rejects(install(mirror.pins, { env, platform: PLATFORM }), /the mirror ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST\) has sha256/);
    assert.ok(!existsSync(join(mirror.cache, bundleName(VERSION, PLATFORM))));
  } finally { mirror.server.close(); }
});

test("a second install finds the first and downloads nothing", async () => {
  const { pins, env, server, releaseBase, requests } = await served();
  try {
    await install(pins, { env, platform: PLATFORM, releaseBase });
    const lines: string[] = [];
    await install(pins, { env, platform: PLATFORM, releaseBase, log: (l) => lines.push(l) });
    assert.match(lines[0]!, /already installed/);
    assert.equal(requests.length, 1);
  } finally { server.close(); }
});

const PINS: Pins = { version: "1.2.3", bundles: { [PLATFORM]: { file: "f.tar.xz", sha256: "0", bytes: 1 } } };

test("the bundle's source is the Release of the package's version, from the repository field, unless the mirror variable is set", () => {
  const repository = (JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { repository: unknown }).repository;
  const release = bundleSource(PINS, PLATFORM, {});
  assert.equal(release.url, `${repositoryUrl(repository)}/releases/download/v1.2.3/f.tar.xz`);
  assert.match(release.url, /^https:\/\/github\.com\/[^/]+\/[^/]+\/releases\/download\/v1\.2\.3\/f\.tar\.xz$/);
  assert.equal(release.via, "the Release v1.2.3");
  assert.equal(bundleSource(PINS, PLATFORM, {}, "http://r/v1.2.3/").url, "http://r/v1.2.3/f.tar.xz");
  assert.equal(bundleSource(PINS, PLATFORM, { ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: "http://h" }).url, "http://h/v1.2.3/f.tar.xz");
  assert.equal(bundleSource(PINS, PLATFORM, { ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: "http://h/m//" }).url, "http://h/m/v1.2.3/f.tar.xz");
  assert.equal(bundleSource(PINS, PLATFORM, { ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: "" }).url, release.url);      // an empty variable is no mirror
});

test("the Release's URL is a pure function of the repository field and the version", () => {
  const base = "https://github.com/a11ign/announcement-emulator/releases/download/v1.2.3/";
  for (const repository of [
    "git+https://github.com/a11ign/announcement-emulator.git",
    "https://github.com/a11ign/announcement-emulator",
    "https://github.com/a11ign/announcement-emulator/",
    "git://github.com/a11ign/announcement-emulator.git",
    { type: "git", url: "git+https://github.com/a11ign/announcement-emulator.git", directory: "middleware" },
  ]) assert.equal(releaseBaseUrl(repository, "1.2.3"), base, JSON.stringify(repository));
  for (const repository of [undefined, "", "a11ign/announcement-emulator", "git@github.com:a11ign/announcement-emulator.git", { type: "git" }]) assert.throws(() => releaseBaseUrl(repository, "1.2.3"), /no `repository` URL.*ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST/, JSON.stringify(repository));
});

test("for a platform with no bundle the install says what there is, and how to use a bundle of your own", () => {
  assert.throws(() => bundleSource(PINS, "win32-x64", { ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST: "http://h" }), /has: linux-x64.*ANNOUNCEMENT_EMULATOR_BUNDLE/);
  assert.throws(() => bundleSource({ version: "0.0.0", bundles: {} }, PLATFORM, {}), /has: none.*ANNOUNCEMENT_EMULATOR_BUNDLE/);
});
