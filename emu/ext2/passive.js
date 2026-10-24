// Passive mode of the companion extension (A11-208). Not the extension's service worker unless a copy of the extension says so: the middleware's private copy names this file in its
// manifest, so a session of session.mjs (which keeps bg.js) behaves exactly as before.
//
// bg.js dumps when it is asked, 200 ms at a time. A test that is running does not wait for anyone, so this dumps when the page changes: it is told by chrome.automation's tree-change
// observer, takes the focus at that moment, and posts the page's tree with it. The runtime that reads the posts turns the difference between two of them into the events NVDA
// would have been given (focus moved, a document loaded, a live region spoke).
importScripts('tree.js');      // IX, uid, number, describeParts, finish, walk
const COLLECTOR = 'http://127.0.0.1:__PORT__/';      // the middleware writes its runtime's port here, in its own copy
const VERIFY = '__VERIFY__' === '1';      // check every cached dump against a dump read from scratch, and post a `verify` when they differ (the tests turn it on)
const post = (kind, body) => fetch(COLLECTOR + kind, {method: 'POST', body: JSON.stringify(body)}).catch(() => {});

const CACHE = new WeakMap();      // node -> describeParts(node), kept until the observer says the node changed
const DIRTY = new Set();      // nodes changed since their parts were read
const PAGES = new Map();      // top document's root -> {changed: types seen since the last post, last: the last post's body without its time}
const QUEUE = []; let busy = false, seq = 0, posted = 0, bytes = 0;

const isDocument = n => n && n.role === 'rootWebArea' && n.url !== undefined && !/^(chrome|chrome-extension|devtools):/.test(n.url);
// An iframe's document is a tree of its own whose parent is the iframe node of the document that holds it: climb to the document the browser shows, which hangs from a webView. A document that has
// no parent yet (an iframe's, in the moment before the tree links it in) is nobody's page.
function topDocument(n) {
  let r = n && n.root;
  for (let hops = 0; r && r.parent && hops < 32; hops++) { const up = r.parent.root; if (up && up !== r && up.role === 'rootWebArea') r = up; else break; }
  return isDocument(r) && r.parent && r.parent.role === 'webView' ? r : null;
}

function parts(n) {
  if (!CACHE.has(n) || DIRTY.has(n)) { CACHE.set(n, describeParts(n)); DIRTY.delete(n); }
  return CACHE.get(n);
}
function walkCached(n, depth, acc) { acc.push({depth, ix: IX.get(n), uid: uid(n), ...finish(parts(n))}); for (const c of n.children) walkCached(c, depth + 1, acc); return acc; }

function snapshot(item) {
  const web = item.page, t0 = performance.now();
  // The document's own fields carry the selection, the word breaks and the focus state, which move without a change being reported on it; the focused node's selection too.
  DIRTY.add(web); if (item.focus) DIRTY.add(item.focus);
  IX.clear(); number(web);
  const nodes = walkCached(web, 0, []);
  const ms = performance.now() - t0;
  const f = item.focus, ix = o => o && IX.has(o) ? IX.get(o) : -1;
  // the focus inside this document: the browser's focus if it is in here; if not, the element the document itself has focused (a page that is not the active one)
  let focusIx = ix(f);
  if (focusIx < 0) { const own = nodes.find(n => n.state && n.state.focused && n.role !== 'rootWebArea'); focusIx = own ? own.ix : -1; }
  const body = {url: web.url, title: web.name, focusIx, sel: {anchorIx: ix(web.anchorObject), anchorOffset: web.anchorOffset, focusIx: ix(web.focusObject), focusOffset: web.focusOffset}, nodes};
  const state = PAGES.get(web) || {changed: new Set(), last: null};
  PAGES.set(web, state);
  const text = JSON.stringify(body);
  if (VERIFY) verify(web, nodes);
  if (state.last === text) return;      // nothing a screen reader could see moved
  state.last = text;
  const out = {kind: 'snap', seq: ++seq, t: item.t, page: uid(web), why: item.why, ms: Math.round(ms * 10) / 10, ...body};
  posted++; bytes += text.length;
  post('snap', out);
}

// Every dump the cache made must equal one read from scratch. Run only when a test asks for it (VERIFY).
function verify(web, cached) {
  IX.clear(); number(web);
  const fresh = walk(web, 0, []);
  // Where a node is on the screen moves when something above it grows, and is reported on the node that grew: the emulator reads it only to click, which a passive run never does.
  const same = (a, b) => { const x = {...a}, y = {...b}; for (const k of ['location', 'unclippedLocation']) { delete x[k]; delete y[k]; } return JSON.stringify(x) === JSON.stringify(y); };
  const at = cached.findIndex((n, i) => !fresh[i] || !same(n, fresh[i]));
  if (at >= 0 || cached.length !== fresh.length) {
    const c = cached[at] || {}, f = fresh[at] || {}, keys = [...new Set([...Object.keys(c), ...Object.keys(f)])].filter(k => JSON.stringify(c[k]) !== JSON.stringify(f[k]));
    post('verify', {ok: false, at, role: f.role, diff: keys.map(k => [k, c[k], f[k]]), count: [cached.length, fresh.length]});
  } else post('verify', {ok: true, nodes: cached.length});
}

async function drain() {
  if (busy) return; busy = true;
  try { while (QUEUE.length) { const item = QUEUE.shift(); try { snapshot(item); } catch (e) { post('error', {message: String(e && e.stack || e)}); } } }
  finally { busy = false; }
}

// The focus is read at the moment of the change, then the dump is taken from the queue: a test that presses Tab ten times in ten milliseconds leaves ten items with ten focuses.
function flush(why) {
  const pages = [...PAGES.keys()].filter(w => PAGES.get(w).changed.size);
  if (!pages.length) return;
  const t = Date.now(), reasons = new Map(pages.map(w => [w, [...PAGES.get(w).changed]]));
  for (const w of pages) PAGES.get(w).changed.clear();
  chrome.automation.getFocus(f => { for (const w of pages) QUEUE.push({page: w, focus: f, t, why: reasons.get(w)}); drain(); });
}

function onChange(change) {
  const n = change.target;
  if (change.type === 'subtreeUpdateEnd') { flush(); return; }
  const web = topDocument(n);
  if (!web) return;
  // A node that changed changes what its ancestors say too (their text, their word breaks), and nothing reports that.
  for (let a = n, hops = 0; a && hops < 64; a = a.parent, hops++) DIRTY.add(a);
  if (!PAGES.has(web)) PAGES.set(web, {changed: new Set(), last: null});
  PAGES.get(web).changed.add(change.type);
}

post('hello', {t: Date.now(), automation: typeof chrome.automation, getDesktop: chrome.automation ? typeof chrome.automation.getDesktop : null});      // the worker is up; whether the platform gave it the API at all
// The first call to getDesktop is what makes Chromium build the platform tree at all.
chrome.automation.getDesktop(desktop => {
  chrome.automation.addTreeChangeObserver('allTreeChanges', onChange);
  const find = n => { if (isDocument(n) && n === topDocument(n)) { PAGES.set(n, {changed: new Set(['found']), last: null}); } for (const c of n.children) find(c); };
  find(desktop); flush();
  post('ready', {t: Date.now(), desktopChildren: desktop.children.length, documents: PAGES.size});      // what the platform gives chrome.automation: on macOS the browser is not drawn by Views and the desktop has no browser windows in it
});
// A service worker is stopped after thirty idle seconds, and a test can wait longer than that for a page: a request to the runtime every few seconds keeps this one alive and tells the runtime it is.
setInterval(() => { chrome.runtime.getPlatformInfo(() => {}); post('alive', {t: Date.now(), posted, bytes}); }, 5000);
