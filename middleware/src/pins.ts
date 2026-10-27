import { readFileSync } from "node:fs";

export interface Pin { file: string; sha256: string; bytes: number }
export interface Pins { version: string; bundles: Record<string, Pin> }

/** The pins ship in the package (`pins.json` beside `dist`): the version of the runtime this package drives, and each platform's bundle with the sha256 it must have. */
export function readPins(url = new URL("../pins.json", import.meta.url)): Pins {
  return JSON.parse(readFileSync(url, "utf8")) as Pins;
}

export function pinFor(pins: Pins, platform: string): Pin {
  const pin = pins.bundles[platform];
  if (!pin) throw new Error(`foresay ${pins.version} has no runtime bundle for ${platform} (it has: ${Object.keys(pins.bundles).join(", ") || "none"}). A build from the repository pins none: install a released version, or set ANNOUNCEMENT_EMULATOR_BUNDLE to an unpacked bundle you built with middleware/bundle/build.sh.`);
  return pin;
}
