import { readFileSync } from "node:fs";

export interface Pin { file: string; sha256: string; bytes: number }
export interface Pins { version: string; bundles: Record<string, Pin> }

/** The pins ship in the package (`pins.json` beside `dist`): the version of the runtime this package drives, and each platform's bundle with the sha256 it must have. */
export function readPins(url = new URL("../pins.json", import.meta.url)): Pins {
  return JSON.parse(readFileSync(url, "utf8")) as Pins;
}

export function pinFor(pins: Pins, platform: string): Pin {
  const pin = pins.bundles[platform];
  if (!pin) throw new Error(`announcement-emulator ${pins.version} has no runtime bundle for ${platform} (it has: ${Object.keys(pins.bundles).join(", ") || "none"})`);
  return pin;
}
