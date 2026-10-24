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
  // Only where the tree comes from this port and not from the extension (axtree.py): a note that something changed, for the runtime to read the tree again after. One note at a time, a moment after the change.
  const TICKS = __TICKS__; let ticking = false, again = null;
  const tick = why => { if (!TICKS) return; if (ticking) { again = why; return; } ticking = true; send({e: 'tick', why}); setTimeout(() => { ticking = false; if (again) { const w = again; again = null; tick(w); } }, 20); };
  for (const type of ['input', 'change', 'keyup', 'load', 'hashchange', 'popstate', 'pageshow', 'readystatechange', 'scroll']) addEventListener(type, () => tick(type), true);
  tick('installed');
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
  new MutationObserver(() => { tick('mutation'); if (!pending) { pending = true; queueMicrotask(() => { pending = false; observe(); }); } }).observe(document, {childList: true, subtree: true, attributes: true, characterData: true});
  addEventListener('load', observe);
})()"""


class Cdp:
    """Calls `on_event(event)` for each trusted keydown and focusin in any page of the browser listening on `port`. Reconnects when the browser is launched again (a Playwright worker is restarted).

    With `on_tree` it is also where the trees come from (a platform where the extension is given none: axtree.py): each note that a page changed makes it read the page's accessibility tree and
    DOM through the same port, and `on_tree(snapshot)` is called with what the extension would have posted. `on_connect()` is called each time the browser is reached (the first, and again after a launch)."""
    def __init__(self, port, on_event, on_attach=lambda target: None, on_tree=None, on_connect=lambda: None):
        self.port, self.on_event, self.on_attach, self.on_tree, self.on_connect = port, on_event, on_attach, on_tree, on_connect
        self.ws = None; self.next_id = 0; self.stopped = False; self.installed = set(); self.lock = threading.Lock(); self.target_of = {}; self.url_of = {}
        self.replies = {}; self.wanted = {}; self.wake = threading.Condition(); self.seq = 0; self.page_numbers = {}; self.converters = {}; self.generation = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name='cdp'); self.thread.start()
        if on_tree: self.trees = threading.Thread(target=self._trees, daemon=True, name='trees'); self.trees.start()

    def _send(self, method, params=None, session=None):
        with self.lock:
            self.next_id += 1
            message = {'id': self.next_id, 'method': method, 'params': params or {}}
            if session: message['sessionId'] = session
            self.ws.send(json.dumps(message))
            return self.next_id

    def call(self, method, params=None, session=None, timeout=20):
        """A command and its answer. For a thread that is not the one reading the socket (that one is `_run`, which hands the answer over)."""
        slot = {'event': threading.Event(), 'session': session}
        with self.lock:
            self.next_id += 1; ident = self.next_id; self.replies[ident] = slot
            message = {'id': ident, 'method': method, 'params': params or {}}
            if session: message['sessionId'] = session
            self.ws.send(json.dumps(message))
        if not slot['event'].wait(timeout): self.replies.pop(ident, None); raise TimeoutError(f'{method} did not answer in {timeout} s')
        if 'error' in slot['message']: raise RuntimeError(f'{method}: {slot["message"]["error"].get("message")}')
        return slot['message']['result']

    def call_many(self, commands, session=None, timeout=20):
        """Several commands sent at once, and their answers in the order they were sent: one round trip to the browser and not one for each."""
        slots = []
        with self.lock:
            for method, params in commands:
                slot = {'event': threading.Event(), 'session': session}; self.next_id += 1; self.replies[self.next_id] = slot; slots.append((self.next_id, method, slot))
                message = {'id': self.next_id, 'method': method, 'params': params or {}}
                if session: message['sessionId'] = session
                self.ws.send(json.dumps(message))
        out = []
        for ident, method, slot in slots:
            if not slot['event'].wait(timeout): self.replies.pop(ident, None); raise TimeoutError(f'{method} did not answer in {timeout} s')
            if 'error' in slot['message']: raise RuntimeError(f'{method}: {slot["message"]["error"].get("message")}')
            out.append(slot['message']['result'])
        return out

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
            self.installed.clear(); self.target_of.clear(); self.url_of.clear(); self.wanted.clear(); self.generation += 1
            for slot in list(self.replies.values()): slot['message'] = {'error': {'message': 'the browser went away'}}; slot['event'].set()
            self.replies.clear()
            try:
                self.on_connect()
                # Where the trees come from this port, a page is held until its listener is in, so that a test that is quick still has its first tree read (everything but a page is let go at once, below)
                self._send('Target.setAutoAttach', {'autoAttach': True, 'waitForDebuggerOnStart': bool(self.on_tree), 'flatten': True})
                self._send('Target.setDiscoverTargets', {'discover': True})
                while True: self._handle(json.loads(self.ws.recv()))
            except (ConnectionError, OSError): pass
            finally: self.ws.close()

    def _handle(self, m):
        if 'id' in m:
            slot = self.replies.pop(m['id'], None)
            if slot: slot['message'] = m; slot['event'].set()
            return
        method = m.get('method')
        if method == 'Target.targetInfoChanged' and m['params']['targetInfo']['type'] == 'page': self.url_of[m['params']['targetInfo']['targetId']] = m['params']['targetInfo']['url']
        if method == 'Target.attachedToTarget' and m['params']['targetInfo']['type'] != 'page' and m['params'].get('waitingForDebugger'):
            self._send('Runtime.runIfWaitingForDebugger', {}, m['params']['sessionId'])      # a frame of another site, a worker: not read here, and not to be kept waiting
        if method == 'Target.attachedToTarget' and m['params']['targetInfo']['type'] == 'page':
            self.target_of[m['params']['sessionId']] = m['params']['targetInfo']['targetId']; self.url_of[m['params']['targetInfo']['targetId']] = m['params']['targetInfo']['url']
            self._install(m['params']['sessionId'], m['params']['targetInfo']['targetId'])
        elif method == 'Target.targetCreated' and m['params']['targetInfo']['type'] == 'page' and m['params']['targetInfo']['targetId'] not in self.installed:
            self._send('Target.attachToTarget', {'targetId': m['params']['targetInfo']['targetId'], 'flatten': True})
        elif method == 'Target.detachedFromTarget':      # a page that is closed answers nothing more: what is waiting for it is told so
            gone = m['params'].get('sessionId'); self.wanted.pop(gone, None)
            for ident, slot in list(self.replies.items()):
                if slot.get('session') == gone: self.replies.pop(ident, None); slot['message'] = {'error': {'message': 'the page was closed'}}; slot['event'].set()
        elif method == 'Runtime.bindingCalled' and m['params']['name'] == '__ae':
            try: event = json.loads(m['params']['payload'])
            except ValueError: return
            session = m.get('sessionId')
            if event.get('e') == 'tick': self._want(session, event.get('why', 'tick')); return      # a note for the tree reader, not an event for the predictor
            event['pageUrl'] = self.url_of.get(self.target_of.get(session))      # the address of the page the frame is in: a frame's own address is not the page's
            self.on_event(event)
            self._want(session, event.get('e'))

    def _want(self, session, why):
        if not self.on_tree or not session: return
        with self.wake: self.wanted.setdefault(session, set()).add(why); self.wake.notify()

    def _trees(self):
        """Reads the trees of the pages that have changed, one page at a time, and rests as long as a read took (so that reading is at most half the time of a busy page)."""
        import axtree
        while not self.stopped:
            with self.wake:
                while not self.wanted and not self.stopped: self.wake.wait(0.5)
                session, why = next(iter(self.wanted.items())) if self.wanted else (None, None)
                if session: del self.wanted[session]
            if not session: continue
            target = self.target_of.get(session)
            if target is None: continue
            started = time.time(); generation = self.generation
            try:
                raw = axtree.fetch(lambda commands: self.call_many(commands, session))
                converted = self.converters.setdefault((generation, target), axtree.Converter()).convert(raw)
            except (RuntimeError, TimeoutError, ConnectionError, OSError, ValueError): continue      # the page is gone, or navigating: the next note reads it again
            except Exception:      # a tree this cannot convert is one tree lost, and not the end of the trees
                import traceback; traceback.print_exc(); continue
            if generation != self.generation: continue
            if len(converted['nodes']) <= 1: continue      # a document with nothing in it yet (the blank page a navigation starts from): the extension posts none either, and its language, which the page has not set yet, would be taken for the page's
            self.seq += 1
            number = self.page_numbers.setdefault((generation, target), len(self.page_numbers))
            took = time.time() - started
            self.on_tree({'kind': 'snap', 'seq': self.seq, 't': round(started * 1000), 'page': number, 'why': sorted(w for w in why if w), 'ms': round(took * 1000, 1), **converted})
            time.sleep(min(took, 0.5))

    def _install(self, session, target):
        if target in self.installed: return
        self.installed.add(target); self.on_attach(target)
        listener = LISTENER.replace('__TICKS__', 'true' if self.on_tree else 'false')
        self._send('Runtime.enable', {}, session)      # without it the browser does not send `Runtime.bindingCalled`
        self._send('Runtime.addBinding', {'name': '__ae'}, session)
        self._send('Page.enable', {}, session)      # the script below is run on each new document only while the Page domain is enabled
        self._send('Page.addScriptToEvaluateOnNewDocument', {'source': listener}, session)
        self._send('Runtime.evaluate', {'expression': listener}, session)      # the document already there
        self._send('Runtime.runIfWaitingForDebugger', {}, session)

    def stop(self):
        self.stopped = True
        with self.wake: self.wake.notify()
        if self.ws: self.ws.close()
