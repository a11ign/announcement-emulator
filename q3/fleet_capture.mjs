// Ask one fleet worker for the capture of one address, with the body the real-page capture sends (screenreader-worker's /capture), and write the record.
//   node fleet_capture.mjs <worker url> <address> <out.json> [steps]
// Used for control pages we serve ourselves; it changes nothing on the worker and touches no evidence record of a11ign.
import { writeFileSync } from "node:fs";
const [, , worker, url, out, steps] = process.argv;
const res = await fetch(`${worker}/capture`, {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ url, probeForms: false, probeFocus: true, probeNavigation: true, probeFocusContext: true, probeFocusReveal: true, steps: Number(steps || 600) }),
  signal: AbortSignal.timeout(600_000),
});
const text = await res.text();
let json; try { json = JSON.parse(text); } catch { json = { error: text.slice(0, 300) }; }
writeFileSync(out, JSON.stringify({ capturedAt: new Date().toISOString(), worker, status: res.status, capture: json }, null, 1));
console.log(res.status, json.error ? json.error : `${(json.transcript || []).length} lines`);
