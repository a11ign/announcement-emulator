// Layer 0/1 companion extension (emulator spike #5661): on request, dump the web area's chrome.automation tree and the focused node.
const COLLECTOR = 'http://127.0.0.1:__PORT__/';      // session.mjs writes the session's port here
let TARGET = '';
const post = (kind, body) => fetch(COLLECTOR + kind, {method: 'POST', body: JSON.stringify(body)}).catch(() => {});
importScripts('tree.js');      // IX, uid, number, describe, walk
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
    if (j.history) { for (const url of j.history) await chrome.history.addUrl({url}); }      // the fleet's browser has visited the pages it captured: visited links are part of what NVDA says
    if (j.action !== undefined) { for (const [node, i] of IX) if (i === j.action) { node.doDefault(); break; } }      // IAccessibleAction::doAction(0): the node's default action
    if (j.scroll !== undefined) { for (const [node, i] of IX) if (i === j.scroll) { node.makeVisible(); break; } }      // IAccessible2::scrollTo: scroll the node into view
    if (j.focus !== undefined) { for (const [node, i] of IX) if (i === j.focus) { node.focus(); break; } }      // accSelect(SELFLAG_TAKEFOCUS): focus the node by its index in the last dump
  } catch (e) {}
}, 200);
