// Ask one fleet worker for the capture of one address, with the body the real-page capture sends (screenreader-worker's /capture), and write the record.
//   node fleet_capture.mjs <worker name>=<worker url> <address> <out.json> [steps] [--tables]
// Used for control pages we serve ourselves; it changes nothing on the worker and touches no evidence record of a11ign.
// The record names the worker (`a11y-worker-2`) and the machine serving the page (`capture-host`), never a network address: the worker's URL is only where to ask.
import { writeFileSync } from "node:fs";
const [, , workerArg, url, out, steps] = process.argv;
const parsed = /^([\w-]+)=(https?:\/\/.+)$/.exec(workerArg || "");
if (!parsed) throw new Error("the first argument is <worker name>=<worker url>, e.g. a11y-worker-2=http://host:8765");
const [, workerName, worker] = parsed;
const SERVER_NAME = "capture-host";
const serverHost = new URL(url).hostname;
const named = (text) => /^[\d.]+$/.test(serverHost) ? text.replaceAll(serverHost, SERVER_NAME) : text;     // an address of ours given as an IP literal is written by name
const tables = process.argv.includes('--tables');
const res = await fetch(`${worker}/capture`, {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ url, probeForms: false, probeFocus: true, probeNavigation: true, probeFocusContext: true, probeFocusReveal: true, steps: Number(steps || 600), ...(tables ? { probeTables: true } : {}) }),
  signal: AbortSignal.timeout(600_000),
});
const text = await res.text();
let json; try { json = JSON.parse(text); } catch { json = { error: text.slice(0, 300) }; }
writeFileSync(out, named(JSON.stringify({ capturedAt: new Date().toISOString(), worker: workerName, status: res.status, capture: json }, null, 1)));
console.log(res.status, json.error ? json.error : `${(json.transcript || []).length} lines`);
