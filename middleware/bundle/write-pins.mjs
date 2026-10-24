// Writes middleware/pins.json from the pin-<platform>.json files a bundle build wrote:
//   node write-pins.mjs <version> <pin-linux-x64.json> [<pin-darwin-arm64.json> ...] > pins.json
import { readFileSync } from "node:fs";

const [version, ...files] = process.argv.slice(2);
if (!version || !files.length) throw new Error("usage: write-pins.mjs <version> <pin file>...");
const bundles = {};
for (const file of files) {
  const { platform, ...pin } = JSON.parse(readFileSync(file, "utf8"));
  bundles[platform] = pin;
}
console.log(JSON.stringify({ version, bundles }, null, 2));
