// Ask one fleet worker for the capture of one address, with the body the real-page capture sends (screenreader-worker's /capture), and write the record.
//   node fleet_capture.mjs <worker name>=<worker url> <address> <out.json> [steps] [--tables]
// Used for control pages we serve ourselves; it changes nothing on the worker and touches no evidence record of a11ign.
// The record names the worker (`a11y-worker-2`) and the machine serving the page (`capture-host`), never a network address: the worker's URL is only where to ask.
import { writeFileSync } from "node:fs";
import { request } from "node:http";
const [, , workerArg, url, out, steps] = process.argv;
const parsed = /^([\w-]+)=(http:\/\/.+)$/.exec(workerArg || "");
if (!parsed) throw new Error("the first argument is <worker name>=<worker url>, e.g. a11y-worker-2=http://host:8765 (http: the workers speak no other)");
const [, workerName, worker] = parsed;
const SERVER_NAME = "capture-host";
const serverHost = new URL(url).hostname;
const named = (text) => /^[\d.]+$/.test(serverHost) ? text.replaceAll(serverHost, SERVER_NAME) : text;     // an address of ours given as an IP literal is written by name
const tables = process.argv.includes('--tables');
// node:http and not fetch: fetch gives up on the response headers after 300 s (undici's default) and a worker answers only when the capture is done, which on a real page can take longer
// (the re-measure of A11-155 lost its first 99 captures to it, and the retries met `429 a capture is already in progress`). The idle limit here is the worker's own 600 s.
const body = JSON.stringify({ url, probeForms: false, probeFocus: true, probeNavigation: true, probeFocusContext: true, probeFocusReveal: true, steps: Number(steps || 600), ...(tables ? { probeTables: true } : {}) });
const post = (target, payload, idleMs) => new Promise((resolve, reject) => {
  const u = new URL(target);
  const req = request({ hostname: u.hostname, port: u.port || 80, path: u.pathname, method: "POST", timeout: idleMs,
    headers: { "content-type": "application/json", "content-length": Buffer.byteLength(payload) } }, (r) => {
    let text = ""; r.setEncoding("utf8"); r.on("data", (d) => { text += d; });
    r.on("end", () => resolve({ status: r.statusCode, text }));
    r.on("error", reject);
    r.on("close", () => { if (!r.complete) reject(new Error("the connection closed before the answer was complete")); });
  });
  req.on("timeout", () => req.destroy(new Error(`no answer in ${idleMs / 1000} s`)));
  req.on("error", reject); req.end(payload);
});
// A connection that fails is a record too, so that a stale file of an earlier run is never mistaken for this one's, and it names the worker, not its address.
const res = await post(`${worker}/capture`, body, 600_000).catch((e) => ({ status: 0, text: JSON.stringify({ error: `${workerName}: ${String(e.message).replaceAll(new URL(worker).hostname, workerName)}` }) }));
const text = res.text;
let json; try { json = JSON.parse(text); } catch { json = { error: text.slice(0, 300) }; }
writeFileSync(out, named(JSON.stringify({ capturedAt: new Date().toISOString(), worker: workerName, status: res.status, capture: json }, null, 1)));
console.log(res.status, json.error ? json.error : `${(json.transcript || []).length} lines`);
