// Q1 probe: dump the full chrome.automation tree of the active tab to a local collector.
const COLLECTOR = 'http://127.0.0.1:8765/';
async function post(kind, body) {
  try { await fetch(COLLECTOR + kind, {method:'POST', body: JSON.stringify(body)}); } catch (e) {}
}
// Every attribute the automation API exposes on a node, by property enumeration of the prototype chain.
function describe(node) {
  const out = {};
  for (const k in node) {
    let v; try { v = node[k]; } catch (e) { continue; }
    if (typeof v === 'function') continue;
    if (v && typeof v === 'object' && !Array.isArray(v)) { if (k !== 'state' && k !== 'htmlAttributes' && k !== 'location' && k !== 'unclippedLocation') continue; }
    if (Array.isArray(v) && v.length && typeof v[0] === 'object') { if (v[0] && 'role' in v[0]) out[k + 'Ix'] = v.map(x => IX.has(x) ? IX.get(x) : -1); continue; }
    out[k] = v;
  }
  return out;
}
const IX = new Map();
function number(n) { if (!IX.has(n)) IX.set(n, IX.size); for (const c of n.children) number(c); }
function walk(n, depth, acc) {
  if (depth === 0) { IX.clear(); number(n); }
  acc.push({depth, ix: IX.get(n), ...describe(n)});
  for (const c of n.children) walk(c, depth + 1, acc);
  return acc;
}
async function dump(tabId, url) {
  post('hello', {automationType: typeof chrome.automation, keys: Object.keys(chrome.automation||{}), own: Object.getOwnPropertyNames(chrome.automation||{})});
  chrome.automation.getTree(tabId, (root) => {
    if (!root) { post('error', {msg: 'getTree returned no root', lastError: chrome.runtime.lastError?.message}); return; }
    const go = () => post('tree', {url, nodes: walk(root, 0, [])});
    if (root.docLoaded) go(); else root.addEventListener('loadComplete', go, false);
  });
}
chrome.runtime.onInstalled.addListener(() => { post('installed', {}); chrome.tabs.create({url: chrome.runtime.getURL('page.html'), active: false}).then(t=>post('tabcreated',{id:t.id,url:t.url}),e=>post('tabcreate-error',{m:String(e)})); });
post('sw-start',{type: typeof chrome.automation, keys: Object.keys(chrome.automation||{}), own: Object.getOwnPropertyNames(chrome.automation||{}), proto: Object.getOwnPropertyNames(Object.getPrototypeOf(chrome.automation||{}))});
// The driver asks for a dump by navigating to a page and POSTing /want; the extension polls.
setInterval(async () => {
  try {
    const r = await fetch(COLLECTOR + 'poll'); const j = await r.json();
    if (j.tabUrl) { const tabs = await chrome.tabs.query({}); const t = tabs.find(t => t.url && t.url.startsWith(j.tabUrl)); if (t) dump(t.id, t.url); else post('error', {msg: 'no tab for ' + j.tabUrl}); }
  } catch (e) {}
}, 1000);

// Desktop probe: root of the whole browser UI; web contents hang below it.
chrome.automation.getDesktop((root) => {
  post('desktop-root', {role: root.role, childCount: root.children.length, docUrl: root.docUrl});
  setTimeout(() => {
    const acc = walk(root, 0, []);
    post('desktop-tree', {n: acc.length, roles: [...new Set(acc.map(a => a.role))].slice(0, 80), webDocs: acc.filter(a => a.role === 'rootWebArea').map(a => ({url: a.url, name: a.name})), nodes: acc});
  }, 4000);
});

chrome.automation.getDesktop((root) => setTimeout(() => {
  const web = (function find(n) { if (n.role === 'rootWebArea' && n.url) return n; for (const c of n.children) { const r = find(c); if (r) return r; } })(root);
  let p = Object.getPrototypeOf(web), names = [];
  while (p && p !== Object.prototype) { names.push(...Object.getOwnPropertyNames(p)); p = Object.getPrototypeOf(p); }
  const probe = {}; for (const k of ['htmlAttributes', 'markers', 'inPageLinkTarget', 'tooltip', 'ariaAtomic', 'checkedStateDescription', 'doDefault', 'getTextAlign', 'textAlign', 'textDirection', 'textPosition', 'textStyle', 'listStyle', 'wordStarts', 'unclippedBoundsForRange', 'boundsForRange', 'firstChild', 'nextSibling', 'previousSibling', 'parent', 'root', 'tableCellColumnIndex', 'accessKey', 'keyShortcuts', 'autoComplete', 'restriction', 'readOnly', 'detectedLanguage', 'language', 'nonAtomicTextFieldRoot', 'lineStartOffsets', 'clickable', 'visibility']) { try { probe[k] = typeof web[k] + ':' + (k in web); } catch (e) { probe[k] = 'throws'; } }
  post('proto-names', {names, probe});
}, 5000));
