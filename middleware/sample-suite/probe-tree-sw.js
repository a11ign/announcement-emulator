// The service worker of probe-tree.mjs (A11-208, the macOS probe): which trees does chrome.automation give this platform's Chrome? The desktop's (getDesktop, what passive.js reads), and the tab's own (getTree(tabId)).
// It posts what it found to the probe's server; it reads nothing the middleware needs. (Its first version took a callback with no tree for no callback at all: passive.js did, too, and threw on it.)
importScripts('tree.js');
const C = 'http://127.0.0.1:__PORT__/';
const DESKTOP = '__DESKTOP__' === '1';      // whether the manifest of this copy asks for the desktop tree
const post = (kind, body) => fetch(C + kind, { method: 'POST', body: JSON.stringify(body) }).catch(() => {});
// Calls fn(callback) and says what came back in `ms`: the value, a timeout, or what it threw.
const within = (ms, fn) => new Promise((resolve) => {
  const timer = setTimeout(() => resolve({ timedOut: true }), ms);
  try { fn((value) => { clearTimeout(timer); resolve({ value, lastError: chrome.runtime.lastError ? chrome.runtime.lastError.message : null }); }); } catch (e) { clearTimeout(timer); resolve({ threw: String(e) }); }
});
const nodes = (root) => { const all = []; (function visit(n) { all.push(n); for (const c of n.children) visit(c); })(root); return all; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const platform = await new Promise((r) => chrome.runtime.getPlatformInfo(r));
  post('hello', { os: platform.os, arch: platform.arch, automation: typeof chrome.automation, getDesktop: typeof chrome.automation?.getDesktop, getTree: typeof chrome.automation?.getTree, api: chrome.automation ? Object.keys(chrome.automation).sort() : null, desktopDeclared: DESKTOP });
  // that the worker is running while it waits: a tick each second (a worker that is stopped, or blocked by the call, posts none)
  let ticks = 0; const beat = setInterval(() => post('beat', { n: (ticks += 1) }), 1000);
  if (DESKTOP) {
    post('desktop-asked', { t: Date.now() });
    const desktop = await within(5000, (cb) => chrome.automation.getDesktop(cb));
    // answered with a tree, answered with none (and what the browser said was wrong), or not answered
    post('desktop', desktop.timedOut || desktop.threw ? desktop : desktop.value ? { children: desktop.value.children.length, roles: desktop.value.children.map((c) => c.role) } : { calledBackWithNoTree: true, lastError: desktop.lastError });
  }

  clearInterval(beat); post('beats', { n: ticks });
  let tab;      // the page the probe opened: the one tab that is not the browser's or an extension's
  for (let i = 0; i < 50 && !tab; i++) { tab = (await chrome.tabs.query({})).find((t) => !/^(chrome|chrome-extension|devtools):/.test(t.url || t.pendingUrl || 'chrome:') || t.active); if (!tab) await sleep(200); }
  post('tab', tab ? { id: tab.id, status: tab.status } : { missing: true });
  if (!tab) return;
  const events = {};
  const tree = typeof chrome.automation.getTree === 'function' ? await within(8000, (cb) => chrome.automation.getTree(tab.id, cb)) : { threw: 'chrome.automation.getTree is not a function' };
  if (tree.timedOut || tree.threw) { post('tree', tree); return; }
  const root = tree.value;
  chrome.automation.addTreeChangeObserver('allTreeChanges', (change) => { events[change.type] = (events[change.type] ?? 0) + 1; });
  const all = nodes(root), button = all.find((n) => n.role === 'button'), input = all.find((n) => n.role === 'textField');
  post('tree', { rootRole: root.role, rootUrl: (root.url ?? '').slice(0, 40), parentRole: root.parent?.role ?? null, nodes: all.length, roles: all.map((n) => n.role), buttonName: button?.name,
    buttonKeys: button ? Object.keys(describe(button)).sort() : null, rootKeys: Object.keys(describe(root)).sort() });
  // The page script focuses the button and types into the field once it has seen this; what the tab's tree reports of that.
  await sleep(4000);
  const focus = await within(2000, (cb) => chrome.automation.getFocus(cb));
  post('after', { events, focusRole: focus.value?.role ?? null, focusName: focus.value?.name ?? null, focusFocused: focus.value?.state?.focused ?? null, inputValue: input?.value ?? null,
    inputKeysHaveValue: input ? 'value' in describe(input) : null });
})();
