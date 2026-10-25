import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { createWriteStream, mkdirSync, renameSync, rmSync } from "node:fs";
import { get as httpGet } from "node:http";
import { get as httpsGet } from "node:https";
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { join } from "node:path";
import { bundleName, cacheRoot, isInstalled, platformId } from "./bundle.ts";
import { pinFor, type Pins } from "./pins.ts";

export interface InstallOptions { env?: NodeJS.ProcessEnv; platform?: string; log?: (line: string) => void }

/** Where bundles are fetched from, as PLAYWRIGHT_DOWNLOAD_HOST is for browsers. This spike publishes nothing, so there is no default: a real version needs a host (docs/playwright-middleware-spike.md). */
export function downloadUrl(pins: Pins, platform: string, env: NodeJS.ProcessEnv): string {
  const host = env.ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST;
  if (!host) throw new Error("announcement-emulator: no download host is configured. This spike publishes no bundle; set ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST to where the bundle is served.");
  return `${host.replace(/\/$/, "")}/${pinFor(pins, platform).file}`;
}

/** Download the pinned bundle into the cache, refuse it unless its sha256 is the pinned one, and unpack it where `findBundle` looks. Returns the directory. */
export async function install(pins: Pins, options: InstallOptions = {}): Promise<string> {
  const env = options.env ?? process.env, platform = options.platform ?? platformId(), log = options.log ?? (() => {});
  const pin = pinFor(pins, platform);
  const root = cacheRoot(env), target = join(root, bundleName(pins.version, platform));
  if (isInstalled(target)) { log(`already installed: ${target}`); return target; }
  const url = downloadUrl(pins, platform, env);
  mkdirSync(root, { recursive: true });
  const archive = join(root, `${bundleName(pins.version, platform)}.download`);
  log(`downloading ${url}`);
  const digest = await download(url, archive);
  if (digest !== pin.sha256) {
    rmSync(archive, { force: true });
    throw new Error(`announcement-emulator: the bundle from ${url} has sha256 ${digest}, and this package pins ${pin.sha256}. Nothing was unpacked.`);
  }
  log(`sha256 ${digest} matches the pin`);
  const staging = `${target}.unpacking`;
  rmSync(staging, { recursive: true, force: true }); mkdirSync(staging, { recursive: true });
  await untar(archive, staging);
  rmSync(archive, { force: true });
  rmSync(target, { recursive: true, force: true });
  renameSync(staging, target);
  log(`installed ${target}`);
  return target;
}

/** node:http and node:https and not fetch: fetch's body stream, piped to a file, hit an assertion inside Node's http client on a macOS runner (`assert(!this.paused)`, undici) with a 300 MB body. */
function download(url: string, file: string, hops = 0): Promise<string> {
  return new Promise((resolve, reject) => {
    const get = url.startsWith("https:") ? httpsGet : httpGet;
    get(url, (response) => {
      const status = response.statusCode ?? 0;
      if (status >= 300 && status < 400 && response.headers.location && hops < 5) { response.resume(); download(new URL(response.headers.location, url).href, file, hops + 1).then(resolve, reject); return; }
      if (status !== 200) { response.resume(); reject(new Error(`announcement-emulator: ${url} answered ${status}`)); return; }
      const hash = createHash("sha256");
      const summing = new Transform({ transform(chunk: Buffer, _encoding, done) { hash.update(chunk); done(null, chunk); } });
      pipeline(response, summing, createWriteStream(file)).then(() => resolve(hash.digest("hex")), reject);
    }).on("error", reject);
  });
}

function untar(archive: string, into: string): Promise<void> {
  return new Promise((resolve, reject) => {
    // `-xf` and not `-xzf`: the host's tar reads the compression off the archive (gzip, xz or zstd), so the bundle's format is the build's choice and not this code's
    const tar = spawn("tar", ["-xf", archive, "-C", into], { stdio: ["ignore", "inherit", "inherit"] });
    tar.on("error", reject);
    tar.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(`tar exited ${code}`))));
  });
}
