import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

/** Where the runtime bundle is looked for, and what is in it. The layout is the one `bundle/build.sh` writes. */
export interface BundleManifest {
  name: string;
  platform: string;
  nvda: { release: string; commit: string };
  /** The Chromium milestone the mapping tables were read from (pins.env `CHROME`). Not a browser: the bundle holds none. */
  chromiumTables: string;
  python: string;
  commit: string;
}

export const platformId = (platform = process.platform, arch = process.arch): string => `${platform}-${arch}`;

/** The cache root, as Playwright's PLAYWRIGHT_BROWSERS_PATH is the browsers': an environment variable moves it. */
export function cacheRoot(env: NodeJS.ProcessEnv = process.env, platform = process.platform): string {
  if (env.ANNOUNCEMENT_EMULATOR_PATH) return env.ANNOUNCEMENT_EMULATOR_PATH;
  if (platform === "darwin") return join(homedir(), "Library", "Caches", "announcement-emulator");
  return join(env.XDG_CACHE_HOME ?? join(homedir(), ".cache"), "announcement-emulator");
}

export const bundleName = (version: string, platform = platformId()): string => `${version}-${platform}`;

export const layout = (root: string) => ({
  root,
  python: join(root, "python", "bin", "python3"),
  runtime: join(root, "middleware", "runtime", "main.py"),
  manifest: join(root, "bundle.json"),
});

export const isInstalled = (root: string): boolean => existsSync(layout(root).manifest);
export const readManifest = (root: string): BundleManifest => JSON.parse(readFileSync(layout(root).manifest, "utf8"));

/** The installed bundle for this package version: an explicit path (ANNOUNCEMENT_EMULATOR_BUNDLE) first, else the cache's. */
export function findBundle(version: string, env: NodeJS.ProcessEnv = process.env): string | null {
  const dir = env.ANNOUNCEMENT_EMULATOR_BUNDLE ?? join(cacheRoot(env), bundleName(version));
  return isInstalled(dir) ? dir : null;
}

export class BundleMissing extends Error {
  constructor(version: string) {
    super(`announcement-emulator: no runtime bundle for ${version} on ${platformId()} (looked in ${cacheRoot()}). Run: npx announcement-emulator install`);
  }
}
