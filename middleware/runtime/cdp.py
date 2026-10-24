"""The second thing the runtime hears from the test's browser: the keys the test presses, as the page receives them.

The companion extension sees the tree but not the keyboard, and it sees the focus only as often as the browser sends tree updates, which batch: a test that presses Tab three times in ten
milliseconds leaves the extension one update for the three (measured: a stop of seven was missing from its tree updates). The page itself sees every focus move and every key, so: an extension's content scripts do not run in the off-the-record contexts that `browser.newContext()` makes (measured:
`chrome.extension.isAllowedIncognitoAccess()` is false, and no content script ran), and Playwright's contexts are those. So this connects to the browser's DevTools port
(the middleware adds `--remote-debugging-port` beside Playwright's pipe), attaches to every page and installs a listener that reports each trusted `keydown` and each `focusin`. Nothing is sent to a page but that listener.
"""
import json, threading, time, urllib.request
from wsclient import WebSocket

LISTENER = r"""(() => {
  if (window.__aeKeys) return; window.__aeKeys = true;
  const words = x => (x || '').replace(/\s+/g, ' ').trim();
  const visible = el => !el.checkVisibility || el.checkVisibility({visibilityProperty: true});
  const names = el => {      // what the element's accessible name may be made of; the runtime matches one of them to the tree's node
    const out = [el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('alt'), el.getAttribute('placeholder'), el.value && /^(button|submit|reset)$/.test(el.type) ? el.value : null, words(el.textContent).slice(0, 200)];
    for (const l of (el.labels || [])) out.push(words(l.textContent));
    for (const id of words(el.getAttribute('aria-labelledby')).split(' ')) { const r = id && document.getElementById(id); if (r) out.push(words(r.textContent)); }
    return out.map(words).filter(Boolean);
  };
  const where = () => { const a = document.activeElement; return a ? {tag: a.tagName, type: a.type || null, editable: !!(a.isContentEditable || /^(INPUT|TEXTAREA)$/.test(a.tagName))} : null; };
  const send = o => { try { window.__ae(JSON.stringify({t: Date.now(), url: location.href, ...o})); } catch (x) {} };
  addEventListener('keydown', e => { if (e.isTrusted) send({e: 'keydown', key: e.key, code: e.code, ctrl: e.ctrlKey, alt: e.altKey, meta: e.metaKey, shift: e.shiftKey, at: where()}); }, true);
  addEventListener('focusin', e => { const el = e.target; if (e.isTrusted && el && el.nodeType === 1) send({e: 'focusin', tag: el.tagName.toLowerCase(), id: el.id || null, role: el.getAttribute('role'), names: names(el), inDialog: !!el.closest('dialog, [role="dialog"], [role="alertdialog"]')}); }, true);

  // Live regions. The tree reaches the extension some tens of milliseconds after the page changes, and a test that ends on the change closes the page first; the page's own change does not wait.
  // These are the rules of nvdaHelper/remote/ia2LiveRegions.cpp (NVDA 2026.1.1, winEventProcHook, :147-189 and :233-255) on the DOM that Chromium's events are made from.
  const IMPLIED = {alert: 'assertive', status: 'polite', log: 'polite'};
  const liveOf = el => {      // container-live: the nearest ancestor-or-self that sets it; "off" ends the search
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const attr = n.getAttribute('aria-live');
      if (attr) return attr === 'off' ? null : {el: n, politeness: attr === 'rude' ? 'assertive' : attr};
      const implied = IMPLIED[n.getAttribute('role')];
      if (implied) return {el: n, politeness: implied};
    }
    return null;
  };
  const relevant = el => { const r = (el.closest('[aria-relevant]') || {getAttribute: () => null}).getAttribute('aria-relevant'); return !r || r === 'all' ? {additions: true, text: true} : {additions: r.includes('additions'), text: r.includes('text')}; };
  new MutationObserver(records => {
    const said = new Map();      // region element -> {politeness, parts}
    for (const m of records) {
      const target = m.type === 'characterData' ? m.target.parentElement : m.target;
      const region = target && liveOf(target);
      if (!region || !visible(region.el) || region.el.isContentEditable || target.closest('[aria-busy="true"]')) continue;
      const allow = relevant(region.el);
      let text = '';
      if (m.type === 'characterData' && allow.text) text = m.target.data;
      else if (m.type === 'childList' && allow.additions) text = [...m.addedNodes].map(n => n.nodeType === 3 ? n.data : n.nodeType === 1 && visible(n) ? n.textContent : '').join(' ');
      if (!words(text)) continue;
      const entry = said.get(region.el) || {politeness: region.politeness, parts: [], atomic: target.closest('[aria-atomic="true"]')};      // an atomic region says all it holds (:233-235)
      entry.parts.push(words(text)); said.set(region.el, entry);
    }
    for (const entry of said.values()) send({e: 'live', politeness: entry.politeness, text: entry.atomic ? words(entry.atomic.textContent) : entry.parts.join(' ')});
  }).observe(document, {childList: true, subtree: true, characterData: true});

  // Dialogs that are open, and fields with an error message. The flags are made from what appeared; they are reported when the set changes.
  let digest = '';
  const observe = () => {
    const dialogs = [...document.querySelectorAll('dialog[open], [role="dialog"], [role="alertdialog"]')].filter(visible).map(el => ({tag: el.tagName.toLowerCase(), id: el.id || null, names: names(el).slice(0, 3)}));
    const errors = [...document.querySelectorAll('[aria-invalid]:not([aria-invalid="false"])')].map(el => {
      const ids = words(el.getAttribute('aria-errormessage')) || words(el.getAttribute('aria-describedby'));
      const text = words(ids.split(' ').map(id => { const r = document.getElementById(id); return r && visible(r) ? r.textContent : ''; }).join(' '));
      return {tag: el.tagName.toLowerCase(), id: el.id || null, names: names(el).slice(0, 3), text};
    }).filter(x => x.text);
    const now = JSON.stringify([dialogs, errors]);
    if (now !== digest) { digest = now; send({e: 'observe', dialogs, errors}); }
  };
  let pending = false;
  new MutationObserver(() => { if (!pending) { pending = true; queueMicrotask(() => { pending = false; observe(); }); } }).observe(document, {childList: true, subtree: true, attributes: true, characterData: true});
  addEventListener('load', observe);
})()"""


class Cdp:
    """Calls `on_event(event)` for each trusted keydown and focusin in any page of the browser listening on `port`. Reconnects when the browser is launched again (a Playwright worker is restarted)."""
    def __init__(self, port, on_event):
        self.port, self.on_event = port, on_event
        self.ws = None; self.next_id = 0; self.stopped = False; self.installed = set(); self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True, name='cdp'); self.thread.start()

    def _send(self, method, params=None, session=None):
        with self.lock:
            self.next_id += 1
            message = {'id': self.next_id, 'method': method, 'params': params or {}}
            if session: message['sessionId'] = session
            self.ws.send(json.dumps(message))

    def _connect(self):
        while not self.stopped:
            try:
                version = json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/version', timeout=1))
                return WebSocket(version['webSocketDebuggerUrl'])
            except (OSError, ValueError, KeyError): time.sleep(0.02)      # Playwright makes its first page a few hundred ms after the browser starts; this is there before it

    def _run(self):
        while not self.stopped:
            self.ws = self._connect()
            if self.ws is None: return
            self.installed.clear()
            try:
                self._send('Target.setAutoAttach', {'autoAttach': True, 'waitForDebuggerOnStart': False, 'flatten': True})
                self._send('Target.setDiscoverTargets', {'discover': True})
                while True: self._handle(json.loads(self.ws.recv()))
            except (ConnectionError, OSError): pass
            finally: self.ws.close()

    def _handle(self, m):
        method = m.get('method')
        if method == 'Target.attachedToTarget' and m['params']['targetInfo']['type'] == 'page': self._install(m['params']['sessionId'], m['params']['targetInfo']['targetId'])
        elif method == 'Target.targetCreated' and m['params']['targetInfo']['type'] == 'page' and m['params']['targetInfo']['targetId'] not in self.installed:
            self._send('Target.attachToTarget', {'targetId': m['params']['targetInfo']['targetId'], 'flatten': True})
        elif method == 'Runtime.bindingCalled' and m['params']['name'] == '__ae':
            try: self.on_event(json.loads(m['params']['payload']))
            except ValueError: pass

    def _install(self, session, target):
        if target in self.installed: return
        self.installed.add(target)
        self._send('Runtime.enable', {}, session)      # without it the browser does not send `Runtime.bindingCalled`
        self._send('Runtime.addBinding', {'name': '__ae'}, session)
        self._send('Page.enable', {}, session)      # the script below is run on each new document only while the Page domain is enabled
        self._send('Page.addScriptToEvaluateOnNewDocument', {'source': LISTENER}, session)
        self._send('Runtime.evaluate', {'expression': LISTENER}, session)      # the document already there
        self._send('Runtime.runIfWaitingForDebugger', {}, session)

    def stop(self):
        self.stopped = True
        if self.ws: self.ws.close()
