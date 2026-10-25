// Writes middleware/pins.json from the pin-<platform>.json files a bundle build wrote:
//   node write-pins.mjs <version> [--sums <SHA256SUMS>] <pin-linux-x64.json> [<pin-darwin-arm64.json> ...] > pins.json
// With --sums (a release: middleware/release/after-version.sh), every pin must be a line of that file as `sha256sum` writes it, "<sha256>  <file>", so that the package and the Release it is published
// beside cannot name different sums. A pin the file lacks, or has with another sum, is an error and nothing is printed.
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const sumsAt = args.indexOf("--sums");
const sumsFile = sumsAt >= 0 ? args.splice(sumsAt, 2)[1] : undefined;
const [version, ...files] = args;
if (!version || !files.length || (sumsAt >= 0 && !sumsFile)) throw new Error("usage: write-pins.mjs <version> [--sums <SHA256SUMS>] <pin file>...");

/** The sum of each file in a `sha256sum` listing (a `*` before the name marks binary mode). */
const sumsOf = (text) => new Map(text.split("\n").flatMap((line) => { const m = /^([0-9a-f]{64}) [ *](.+)$/.exec(line); return m ? [[m[2], m[1]]] : []; }));
const sums = sumsFile ? sumsOf(readFileSync(sumsFile, "utf8")) : undefined;

const bundles = {};
for (const file of files) {
  const { platform, ...pin } = JSON.parse(readFileSync(file, "utf8"));
  if (platform in bundles) throw new Error(`${file}: a second pin for ${platform}`);
  if (sums && sums.get(pin.file) !== pin.sha256) throw new Error(`${file}: ${platform} pins ${pin.file} at sha256 ${pin.sha256}, and ${sumsFile} has ${sums.get(pin.file) ?? "no line for it"}`);
  bundles[platform] = pin;
}
console.log(JSON.stringify({ version, bundles }, null, 2));
