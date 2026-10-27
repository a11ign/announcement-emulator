import { ANNOTATION, ATTACH_JSON, ATTACH_TEXT, LABEL } from "./label.ts";
import type { BundleManifest } from "./bundle.ts";
import type { RuntimeRecord } from "./runtime.ts";
import { percent, shapeRateFor, type Agreement, type ShapeRate } from "./supported.ts";

const TREE_NOTE = "Predicted by the announcement emulator from the accessibility tree the browser's DevTools port gives and NVDA's own Python. Not what NVDA said. Nothing here may fill an a11ign evidence field.";

/** The Chromium build a worker's browser named when the runtime reached it (`/json/version`), which is not always the one `browsers.json` names: a team's channel or executablePath may run another. */
export function browserBuild(records: RuntimeRecord[]): string | null {
  const found = records.find((r) => r.kind === "start" && r.what === "devtools" && typeof r.browser === "string");
  return (found?.browser as string | undefined) ?? null;
}

/** The slice of a run one test owns: what happened on its worker's browser while the test ran. */
export interface Window { title: string; start: number; end: number }

/** How long after a test ends its last events may still arrive: the browser tells the runtime about a change some tens of milliseconds after the test's own check of it has passed (measured, docs/playwright-middleware-spike.md). */
export const LAG_MS = 1000;

/**
 * Which test each record belongs to. A test's records are those of the pages it opened, and a page is the test whose window holds the page's first record: a record that arrives after its test
 * ended (the lag above) is still that test's, and not the next one's. Records with no page (errors) belong to no test. Returns the records for each window, and how many belonged to none.
 */
export function assign(records: RuntimeRecord[], windows: Window[]): { byWindow: Map<Window, RuntimeRecord[]>; unassigned: number } {
  const byWindow = new Map<Window, RuntimeRecord[]>(windows.map((w) => [w, []]));
  const first = new Map<number, number>();
  for (const r of records) if (typeof r.page === "number") first.set(r.page, Math.min(first.get(r.page) ?? Infinity, r.t));
  let unassigned = 0;
  for (const r of records) {
    const t = typeof r.page === "number" ? first.get(r.page)! : NaN;
    const owner = windows.filter((w) => t >= w.start && t <= w.end + LAG_MS).sort((a, b) => b.start - a.start)[0];
    if (owner) byWindow.get(owner)!.push(r); else unassigned += 1;
  }
  return { byWindow, unassigned };
}

/** Field names an a11ign evidence record uses (the fleet's capture, `screenreader-worker/src/capture-core.mjs`). A prediction never carries one (ADR 0047, Decision 2). */
export const EVIDENCE_FIELDS = ["transcript", "structure", "interaction", "observed", "media", "formInputs", "diagnostics", "focusOrder", "typedFeedback", "dialogEscape", "screenReader"] as const;

const ms = (t: number, w: Window) => Math.max(0, Math.round(t - w.start));
const seconds = (t: number, w: Window) => `+${(ms(t, w) / 1000).toFixed(2)}s`;

/** What a run knows about a test's browser that its own records do not say: what is measured of the browser's build. */
export interface RunNote { agreement?: Agreement }

export interface Output { text: string; json: Record<string, unknown>; flags: { flag: string; detail: string }[] }

/** How a report says the measured rate of an announcement's shape: `NAME + ROLE: 86.0% of 57`, with `, low confidence` where the list marks the shape weak, or `shape not measured`. */
export const shapeNote = (rate: ShapeRate): string => rate.measured ? `${rate.shape}: ${percent(rate.agreement!)} of ${rate.units}${rate.lowConfidence ? ", low confidence" : ""}` : "shape not measured";

/** The output for one test, from the records `assign` gave it. */
export function describe(w: Window, records: RuntimeRecord[], emulator: BundleManifest | null, note: RunNote = {}): Output {
  const mine = [...records].sort((a, b) => a.t - b.t);
  const speech = mine.filter((r) => r.kind === "speech");
  const sweeps = mine.filter((r) => r.kind === "sweep");
  const flags = mine.filter((r) => r.kind === "flag");
  const predicted = speech.map((r) => {
    const rate = shapeRateFor(note.agreement, r.shape);
    return { atMs: ms(r.t, w), cause: r.cause, text: r.text, utterances: r.utterances, shape: r.shape, ...(rate ? { shapeRate: rate } : {}), ...(rate?.lowConfidence ? { lowConfidence: true } : {}), node: r.node, runtimeMs: r.ms, ...(r.repeatFocus === undefined ? {} : { repeatFocus: r.repeatFocus, repeatFocusShape: r.repeatFocusShape }) };
  });
  const sweepRows = sweeps.map((r) => ({ atMs: ms(r.t, w), trigger: r.trigger, url: r.url, lists: r.lists, counts: r.counts, census: r.census, keysSent: r.keys, notDelivered: r.notDelivered, runtimeMs: r.ms }));
  const flagRows = flags.map((r) => ({ flag: r.flag as string, atMs: ms(r.t, w), detail: r.detail as string, node: r.node }));
  const json = {
    label: LABEL, test: w.title, emulator, treeSource: "devtools", ...(note.agreement ? { agreement: note.agreement } : {}),
    notes: [TREE_NOTE],
    predictedSpeech: predicted, sweeps: sweepRows, flags: flagRows,
  };
  return { text: textOf(w, mine, emulator, note), json, flags: flagRows.map(({ flag, detail }) => ({ flag, detail })) };
}

function textOf(w: Window, mine: RuntimeRecord[], emulator: BundleManifest | null, note: RunNote): string {
  const lines = [LABEL.toUpperCase(), `test: ${w.title}`];
  if (emulator) lines.push(`emulator: NVDA ${emulator.nvda.release} (${emulator.nvda.commit.slice(0, 8)}), Chromium ${emulator.chromiumTables} mapping tables, bundle ${emulator.name}`);
  if (note.agreement) lines.push(note.agreement.line);
  lines.push("");
  const speech = mine.filter((r) => r.kind === "speech");
  if (!speech.length) lines.push("(no speech was predicted while this test ran)");
  for (const r of speech) {
    const rate = shapeRateFor(note.agreement, r.shape);
    lines.push(`${seconds(r.t, w)}  ${String(r.cause).padEnd(6)}  ${r.text}${rate ? `  [${shapeNote(rate)}]` : ""}`);
  }
  for (const r of mine.filter((x) => x.kind === "sweep")) lines.push("", ...sweepLines(r, w));
  const flags = mine.filter((r) => r.kind === "flag");
  lines.push("", flags.length ? "Flags:" : "Flags: none");
  for (const f of flags) lines.push(`  ${seconds(f.t, w)}  ${f.flag}: ${f.detail}`);
  return `${lines.join("\n")}\n`;
}

function sweepLines(r: RuntimeRecord, w: Window): string[] {
  const lists = r.lists as Record<string, string[]>;
  const out = [`${seconds(r.t, w)}  sweep (${r.trigger}) ${r.url}: ${Object.entries(r.counts as Record<string, number>).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`).join(", ") || "nothing found"}`];
  for (const [kind, items] of Object.entries(lists)) if (items.length) out.push(`    ${kind}: ${items.join(" | ")}`);
  return out;
}

export const annotationsFor = (flags: Output["flags"]) => flags.map((f) => ({ type: ANNOTATION, description: `${f.flag}: ${f.detail}` }));
export const attachments = (o: Output) => [
  { name: ATTACH_TEXT, contentType: "text/plain", body: Buffer.from(o.text) },
  { name: ATTACH_JSON, contentType: "application/json", body: Buffer.from(JSON.stringify(o.json, null, 2)) },
];

/** Every key anywhere in `value` that is an evidence field name: there must be none. */
export function evidenceFieldsIn(value: unknown, path = ""): string[] {
  if (Array.isArray(value)) return value.flatMap((v, i) => evidenceFieldsIn(v, `${path}[${i}]`));
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([k, v]) => [...((EVIDENCE_FIELDS as readonly string[]).includes(k) ? [`${path}.${k}`] : []), ...evidenceFieldsIn(v, `${path}.${k}`)]);
  }
  return [];
}
