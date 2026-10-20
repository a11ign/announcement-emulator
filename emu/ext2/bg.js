// Layer 0/1 companion extension (emulator spike #5661): on request, dump the web area's chrome.automation tree and the focused node.
const COLLECTOR = 'http://127.0.0.1:__PORT__/';      // session.mjs writes the session's port here
let TARGET = '';
const post = (kind, body) => fetch(COLLECTOR + kind, {method: 'POST', body: JSON.stringify(body)}).catch(() => {});
const IX = new Map();
function number(n) { if (!IX.has(n)) IX.set(n, IX.size); for (const c of n.children) number(c); }
function describe(node) {
  const out = {};
  for (const k in node) {
    let v; try { v = node[k]; } catch (e) { continue; }
    if (typeof v === 'function') continue;
    if (v && typeof v === 'object' && !Array.isArray(v)) { if (k !== 'state' && k !== 'location' && k !== 'unclippedLocation') continue; }
    if (Array.isArray(v) && v.length && typeof v[0] === 'object') { if (v[0] && 'role' in v[0]) out[k + 'Ix'] = v.map(x => IX.has(x) ? IX.get(x) : -1); else { try { out[k] = JSON.parse(JSON.stringify(v)); } catch (e) {} } continue; }
    out[k] = v;
  }
  return out;
}
function walk(n, depth, acc) { acc.push({depth, ix: IX.get(n), ...describe(n)}); for (const c of n.children) walk(c, depth + 1, acc); return acc; }
function findWeb(n) { if (n.role === 'rootWebArea' && n.url && n.url.startsWith(TARGET)) return n; for (const c of n.children) { const r = findWeb(c); if (r) return r; } }
function dump(seq) {
  chrome.automation.getDesktop((desktop) => {
    IX.clear(); number(desktop);
    const web = findWeb(desktop);
    if (!web) { const urls = []; (function f(n) { if (n.role === 'rootWebArea') urls.push(n.url); for (const c of n.children) f(c); })(desktop); post('dump', {seq, error: 'no web area for ' + TARGET + ' among ' + JSON.stringify(urls)}); return; }
    chrome.automation.getFocus((f) => {
      const ix = o => o && IX.has(o) ? IX.get(o) : -1;
      post('dump', {seq, focusIx: ix(f), sel: {anchorIx: ix(web.anchorObject), anchorOffset: web.anchorOffset, focusIx: ix(web.focusObject), focusOffset: web.focusOffset}, nodes: walk(web, 0, [])});
    });
  });
}
chrome.runtime.onInstalled.addListener(() => { chrome.tabs.create({url: chrome.runtime.getURL('page.html'), active: false}); });
setInterval(async () => {
  try {
    const j = await (await fetch(COLLECTOR + 'poll')).json(); TARGET = j.target || ''; if (j.dump) dump(j.dump);
    if (j.action !== undefined) { for (const [node, i] of IX) if (i === j.action) { node.doDefault(); break; } }      // IAccessibleAction::doAction(0): the node's default action
    if (j.scroll !== undefined) { for (const [node, i] of IX) if (i === j.scroll) { node.makeVisible(); break; } }      // IAccessible2::scrollTo: scroll the node into view
    if (j.focus !== undefined) { for (const [node, i] of IX) if (i === j.focus) { node.focus(); break; } }      // accSelect(SELFLAG_TAKEFOCUS): focus the node by its index in the last dump
  } catch (e) {}
}, 200);
