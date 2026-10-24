// The tree-dump code of the companion extension (emulator spike #5661), shared by bg.js (a dump on request) and passive.js (A11-208: a dump after each change).
// Nothing here talks to the collector; both service workers load it with importScripts.
const IX = new Map();
const UID = new WeakMap(); let nextUid = 0;      // unlike IX, never cleared: Chromium keeps one AutomationNode for an AX node for as long as the node lives, so its id says "the same node" across two dumps (IX is renumbered at every dump)
const uid = n => { if (!UID.has(n)) UID.set(n, nextUid++); return UID.get(n); };
function number(n) { if (!IX.has(n)) IX.set(n, IX.size); for (const c of n.children) number(c); }
// A node's fields in two parts: what it says about itself (`plain`), and the fields that name other nodes (`refs`, which become indexes of the dump being made).
// Reading every field of a node costs about 0.65 ms (measured on a 668-node page), so passive.js keeps `describeParts` of a node that has not changed and calls `finish` again.
function describeParts(node) {
  const plain = {}, refs = [];
  for (const k in node) {
    let v; try { v = node[k]; } catch (e) { continue; }
    if (typeof v === 'function') continue;
    if (v && typeof v === 'object' && !Array.isArray(v)) { if (k !== 'state' && k !== 'location' && k !== 'unclippedLocation') continue; }
    if (Array.isArray(v) && v.length && typeof v[0] === 'object') { if (v[0] && 'role' in v[0]) refs.push([k + 'Ix', v]); else { try { plain[k] = JSON.parse(JSON.stringify(v)); } catch (e) {} } continue; }
    plain[k] = v;
  }
  return {plain, refs};
}
function finish(parts) {
  const out = {...parts.plain};
  for (const [k, v] of parts.refs) out[k] = v.map(x => IX.has(x) ? IX.get(x) : -1);
  return out;
}
const describe = node => finish(describeParts(node));
function walk(n, depth, acc) { acc.push({depth, ix: IX.get(n), uid: uid(n), ...describe(n)}); for (const c of n.children) walk(c, depth + 1, acc); return acc; }
