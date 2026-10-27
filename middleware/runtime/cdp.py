"""What the runtime hears from the test's browser: the keys the test presses and the changes the page makes, as the page reports them, and the accessibility tree, read through the browser's DevTools port.

The middleware adds `--remote-debugging-port` beside Playwright's pipe, and this connects to it, attaches to every page (the contexts a suite opens with `browser.newContext()` included) and installs a listener that reports
each trusted `keydown`, each `focusin`, each live region that changed and a note that something did, for the tree to be read again after (`Cdp`, incremental.py, axtree.py). The page itself sees every focus move and every key, which a tree
that is read after the fact does not: a test that presses Tab three times in ten milliseconds leaves one tree update for the three. Nothing is sent to a page but that listener, and, for each `focusin`, questions that change nothing:
which DOM node the element is and what the browser calls it (`Resolution`).
"""
import json, os, re, threading, time, urllib.request
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
  // A note that something changed, for the runtime to read the tree again after (the tree comes through this port: axtree.py). One note at a time, a moment after the change.
  let ticking = false, again = null;
  const tick = why => { if (ticking) { again = why; return; } ticking = true; send({e: 'tick', why}); setTimeout(() => { ticking = false; if (again) { const w = again; again = null; tick(w); } }, 20); };
  for (const type of ['input', 'change', 'keyup', 'load', 'hashchange', 'popstate', 'pageshow', 'readystatechange', 'scroll']) addEventListener(type, () => tick(type), true);
  tick('installed');
  addEventListener('keydown', e => { if (e.isTrusted) send({e: 'keydown', key: e.key, code: e.code, ctrl: e.ctrlKey, alt: e.altKey, meta: e.metaKey, shift: e.shiftKey, at: where()}); }, true);
  // The element that took the focus is kept, numbered, until the runtime has asked the browser which DOM node it is (cdp.py `_resolve`): the focus may have moved on by then, and the names above are only a guess at the tree's.
  const focused = window.__aeFocused = new Map(); let focusSeq = 0;
  addEventListener('focusin', e => {
    const el = e.target;
    if (!e.isTrusted || !el || el.nodeType !== 1) return;
    focused.set(++focusSeq, el); if (focused.size > 64) focused.delete(focused.keys().next().value);
    send({e: 'focusin', seq: focusSeq, tag: el.tagName.toLowerCase(), id: el.id || null, role: el.getAttribute('role'), names: names(el), inDialog: !!el.closest('dialog, [role="dialog"], [role="alertdialog"]')});
  }, true);

  // Live regions. The tree is read some tens of milliseconds after the page changes, and a test that ends on the change closes the page first; the page's own change does not wait.
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

  // What the runtime asks of the page before it reads the tree again (incremental.py): could anything but the focus and the value of a control have changed since the last read?
  //   muts      a count of the document's mutations: the elements, the text, and every attribute but the ones in SOFT
  //   soft      the elements whose `title`, `class`, `style` or `data-*` attribute changed and nothing else did, with all their attributes: a name or a look, which can be read again alone
  //   layout    how many elements have another box, `display` or `visibility` than at the last commit (the elements of the document, in document order, are numbered 0..n-1)
  //   forms     a digest of each form control's value, in document order
  //   active    the number of the element that has the focus (-1: none, -2: one this cannot number: in a shadow tree)
  //   looks     the computed style (axtree.py STYLES) of the focused element, the elements above it and below it, those of the elements that had the focus (`before`: a number or a list) and of the ones in `soft`, and of what is below
  //             them: which is what a :focus rule or a class changes
  // `baseline` takes what it sees as the state the runtime has read; otherwise the runtime says so with `__aeCommit` once it has used the answer, and until then the next answer is about the same state.
  let mutations = 0;
  const SOFT = name => name === 'title' || name === 'class' || name === 'style' || name.startsWith('data-');
  const soft = new Set(); let reported = new Map();      // reported: each element the runtime was told of, with the attributes it had then
  const signature = el => JSON.stringify([...el.attributes].map(a => [a.name, a.value]));
  const tally = records => { for (const r of records) { if (r.type === 'attributes' && r.target.nodeType === 1 && SOFT(r.attributeName)) soft.add(r.target); else mutations++; } };
  const counter = new MutationObserver(tally);
  const counted = root => counter.observe(root, {childList: true, subtree: true, attributes: true, characterData: true, attributeOldValue: false});
  counted(document);
  const documentId = Math.random().toString(36).slice(2);
  const LOOK = ['display', 'color', 'background-color', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration-line', 'visibility'];      // the computed styles axtree.py STYLES reads
  let committed = null, latest = null;
  const lookOf = (el, pseudo) => { const cs = getComputedStyle(el, pseudo); return LOOK.map(name => cs.getPropertyValue(name)); };
  const pseudoLooks = el => { const out = {}; for (const kind of ['before', 'after', 'marker']) { const content = getComputedStyle(el, '::' + kind).content; if (kind === 'marker' || (content && content !== 'none' && content !== 'normal')) out[kind] = lookOf(el, '::' + kind); } return out; };      // the pseudo-elements that are generated: their style may follow the element's

  // A digest of the box, the `display` and the `visibility` of each element, in document order, and which element has the focus.
  const boxesOf = els => {
    const boxes = new Int32Array(els.length), sx = scrollX, sy = scrollY;      // a box is where it is on the page, as DOMSnapshot says: a fixed or sticky one moves with the scroll
    const words = new Map(); const word = s => { let id = words.get(s); if (id === undefined) words.set(s, id = words.size + 1); return id; };
    let shadows = 0, active = -1; const focus = document.activeElement;
    for (let i = 0; i < els.length; i++) {
      const el = els[i], r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      let h = Math.round((r.x + sx) * 64);
      h = (Math.imul(h, 31) + Math.round((r.y + sy) * 64)) | 0; h = (Math.imul(h, 31) + Math.round(r.width * 64)) | 0; h = (Math.imul(h, 31) + Math.round(r.height * 64)) | 0;
      h = (Math.imul(h, 31) + word(cs.display)) | 0; h = (Math.imul(h, 31) + word(cs.visibility)) | 0;
      boxes[i] = h;
      if (el.shadowRoot) { shadows++; counted(el.shadowRoot); }
      if (el === focus) active = i;
    }
    if (focus && active < 0 && focus !== document.body && focus !== document.documentElement) active = -2;
    return {boxes, shadows, active};
  };

  // What the elements in `soft` have now and what the focus did: [looks, softs]. `looks` is null when it would be more than 1500 elements (not a focus rule's work), `softs` when an element is gone or holds more than 400 texts.
  const describe = (els, active, before) => {
    const at = new Map(), reached = new Set(), sx = scrollX, sy = scrollY; let softs = [];
    const index = el => { if (!at.size) for (let k = 0; k < els.length; k++) at.set(els[k], k); return at.get(el); };
    for (const i of [active, ...(Array.isArray(before) ? before : Number.isInteger(before) ? [before] : [])]) {
      if (i < 0) continue;
      for (let el = els[i]; el; el = el.parentElement) reached.add(index(el));      // the element, and the ones above it
      for (const el of els[i].querySelectorAll('*')) reached.add(index(el));      // and the ones below it, which inherit
    }
    for (const el of reported.keys()) {
      const i = index(el);
      if (i === undefined) { softs = null; break; }      // an element that is no longer in the document: that is a mutation the runtime has to read
      const texts = [];      // the text below it, in order: where each is drawn, or null where it is not (a class can show text that was not shown, and no element's box says so)
      for (const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); walker.nextNode();) {
        const range = document.createRange(); range.selectNodeContents(walker.currentNode);
        if (!range.getClientRects().length) texts.push(null); else { const b = range.getBoundingClientRect(); texts.push([b.x + sx, b.y + sy, b.width, b.height]); }
      }
      if (texts.length > 400) { softs = null; break; }
      softs.push([i, el.localName, Object.fromEntries([...el.attributes].map(a => [a.name, a.value])), texts]);
      reached.add(i); for (const below of el.querySelectorAll('*')) reached.add(index(below));
    }
    const looks = reached.size > 1500 ? null : [...reached].map(i => [i, els[i].localName, lookOf(els[i]), pseudoLooks(els[i])]);
    return [looks, softs];
  };

  // A digest of the value of each form control, in document order.
  const formsOf = () => [...document.querySelectorAll('input, select, textarea')].map(el => {
    let a = 7; const eat = s => { for (let i = 0; i < s.length; i++) a = (Math.imul(a, 31) + s.charCodeAt(i)) | 0; };
    if (el.tagName === 'SELECT') { eat(String(el.selectedIndex)); for (const o of el.selectedOptions) eat(o.value + '|'); }
    else { eat(el.type === 'checkbox' || el.type === 'radio' ? (el.checked ? 'on' : 'off') + (el.indeterminate ? '~' : '') : String(el.value)); }
    return a;
  });

  window.__aeProbe = (baseline, before) => {
    tally(counter.takeRecords());
    const els = document.querySelectorAll('*'), {boxes, shadows, active} = boxesOf(els);
    if (baseline) { committed = boxes; soft.clear(); }
    latest = boxes;
    let layout = -1;      // -1: there is nothing to compare with (or the document has other elements)
    if (!baseline && committed && committed.length === els.length) { layout = 0; for (let i = 0; i < els.length; i++) if (committed[i] !== boxes[i]) layout++; }
    reported = new Map([...soft].map(el => [el, signature(el)]));
    const [looks, softs] = describe(els, active, before);
    return JSON.stringify({doc: documentId, muts: mutations, soft: softs, elements: els.length, layout, shadows, active, looks, forms: formsOf()});
  };
  window.__aeCommit = () => { if (latest) committed = latest; for (const [el, was] of reported) if (signature(el) === was) soft.delete(el); reported = new Map(); };      // an element that changed again since it was told of stays
})()"""


RAW_LOG = os.environ.get('AE_RAW')      # a file to append the raw answers of each tree read to: how a DevTools fixture is made
CONVERSATION_LOG = os.environ.get('AE_CONVERSATION')      # a file to append one line to for each tree read: the commands it sent, what the browser answered, and the tree it made (middleware/runtime/fixtures/incremental)
PROFILE_LOG = os.environ.get('AE_PROFILE')      # a file to append one line to for each tree read: what it cost (the round trip to the browser, the conversion, the whole read) and how it was made (A11-229)


def browser_build(version):
    """The Chromium build a browser names in `/json/version`'s `Browser` field ('HeadlessChrome/156.0.8078.4', 'Chrome/156.0.8078.4', 'Edg/155.0.4283.1'), or None when it names none."""
    found = re.search(r'/(\d+\.\d+\.\d+\.\d+)\b', version or '')
    return found.group(1) if found else None


class Cdp:
    """Calls `on_event(event)` for each trusted keydown and focusin in any page of the browser listening on `port`. Reconnects when the browser is launched again (a Playwright worker is restarted).

    It is also where the trees come from (axtree.py, the only tree source): each note that a page changed makes it read the page's accessibility tree and
    DOM through the same port (incremental.py: whole, or from what changed when only the focus did), and `on_tree(snapshot)` is called with the node list the emulator reads. With `verify`, each incremental read is
    checked against one from scratch, and `on_verify(record)` is called where they differ. `on_connect()` is called each time the browser is reached (the first, and again after a launch)."""
    def __init__(self, port, on_event, on_tree, on_attach=lambda target, browser: None, on_connect=lambda: None, verify=False, on_verify=lambda body: None):
        self.port, self.on_event, self.on_attach, self.on_tree, self.on_connect = port, on_event, on_attach, on_tree, on_connect
        self.verify, self.on_verify = verify, on_verify
        self.ws = None; self.browser = None; self.next_id = 0; self.stopped = False; self.installed = set(); self.lock = threading.Lock(); self.outbox = []; self.out = threading.Lock(); self.target_of = {}; self.url_of = {}
        self.replies = {}; self.wanted = {}; self.wake = threading.Condition(); self.seq = 0; self.page_numbers = {}; self.readers = {}; self.generation = 0; self.hints = {}; self.loaded = set(); self.visited = {}; self.contexts = {}; self.reading = {}; self.reads = {'full': 0, 'incremental': 0, 'verified': 0, 'differing': 0, 'fullMs': 0.0, 'incrementalMs': 0.0}
        self.thread = threading.Thread(target=self._run, daemon=True, name='cdp'); self.thread.start()
        self.trees = threading.Thread(target=self._trees, daemon=True, name='trees'); self.trees.start()

    def _send(self, method, params=None, session=None):
        with self.lock:
            self.next_id += 1
            message = {'id': self.next_id, 'method': method, 'params': params or {}}
            if session: message['sessionId'] = session
            self.ws.send(json.dumps(message))
            return self.next_id

    def _post(self, method, params, session, then=None):
        """Sends a command that is answered into a slot (`replies`), under the lock that numbers them; `then(message)` is called from the thread that reads the socket when the answer comes. Returns the command's number and its slot."""
        with self.lock:
            self.next_id += 1
            slot = {'event': threading.Event(), 'session': session, **({'then': then} if then else {})}; self.replies[self.next_id] = slot
            message = {'id': self.next_id, 'method': method, 'params': params or {}}
            if session: message['sessionId'] = session
            self.ws.send(json.dumps(message))
            return self.next_id, slot

    def call_many(self, commands, session=None, timeout=20):
        """Commands sent at once, and their answers in the order they were sent: one round trip to the browser and not one for each. Called by a thread other than the one that reads the socket (`_run`, which hands the answers over)."""
        slots = [(method, *self._post(method, params, session)) for method, params in commands]
        out = []
        for method, ident, slot in slots:
            if not slot['event'].wait(timeout): self.replies.pop(ident, None); raise TimeoutError(f'{method} did not answer in {timeout} s')
            if 'error' in slot['message']: raise RuntimeError(f'{method}: {slot["message"]["error"].get("message")}')
            out.append(slot['message']['result'])
        return out

    def _connect(self):
        while not self.stopped:
            try:
                version = json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/version', timeout=1))
                self.browser = browser_build(version.get('Browser'))      # the build that is running, which is not always the one Playwright's browsers.json names (a team's channel or executablePath)
                return WebSocket(version['webSocketDebuggerUrl'])
            except (OSError, ValueError, KeyError): time.sleep(0.02)      # Playwright makes its first page a few hundred ms after the browser starts; this is there before it

    def _run(self):
        while not self.stopped:
            self.ws = self._connect()
            if self.ws is None: return
            self.installed.clear(); self.target_of.clear(); self.url_of.clear(); self.generation += 1
            with self.wake: self.wanted.clear()      # the tree reader takes from it under this lock
            gone = list(self.replies.values()); self.replies.clear()
            for slot in gone: self._complete(slot, {'error': {'message': 'the browser went away'}})
            try:
                self.on_connect()
                # A page is held until its listener is in, so that a test that is quick still has its first tree read (everything but a page is let go at once, below)
                self._send('Target.setAutoAttach', {'autoAttach': True, 'waitForDebuggerOnStart': True, 'flatten': True})
                self._send('Target.setDiscoverTargets', {'discover': True})
                while True: self._handle(json.loads(self.ws.recv()))
            except (ConnectionError, OSError): pass
            finally: self.ws.close()

    def _handle(self, m):
        if 'id' in m:
            slot = self.replies.pop(m['id'], None)
            if slot: self._complete(slot, m)
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
            gone = m['params'].get('sessionId')
            self.readers.pop((self.generation, self.target_of.pop(gone, None)), None)      # its uids are of no use to a page that is gone
            with self.wake: self.wanted.pop(gone, None)
            for ident, slot in list(self.replies.items()):
                if slot.get('session') == gone: self.replies.pop(ident, None); self._complete(slot, {'error': {'message': 'the page was closed'}})
        elif method == 'Runtime.executionContextCreated':      # the script context of each frame: the probe of incremental.py is asked in it
            context = m['params']['context']; frame = (context.get('auxData') or {}).get('frameId')
            if frame and (context.get('auxData') or {}).get('isDefault'):
                with self.wake: self.contexts.setdefault(m.get('sessionId'), {})[frame] = context['id']
        elif method == 'Runtime.executionContextDestroyed':
            with self.wake:
                for held in self.contexts.values():
                    for frame, ident in list(held.items()):
                        if ident == m['params'].get('executionContextId'): del held[frame]
        elif method == 'Runtime.executionContextsCleared':
            with self.wake: self.contexts.pop(m.get('sessionId'), None)
        elif method == 'Accessibility.nodesUpdated':      # a node the reader asked after has changed, whatever raised no event of the page's (a CSS rule, the browser's own state): read again, with what the browser says
            session = m.get('sessionId')
            with self.wake: self.hints.setdefault(session, []).append(m['params'].get('nodes') or [])
            self._want(session, 'nodesUpdated')
        elif method == 'Accessibility.loadComplete':
            session = m.get('sessionId')
            with self.wake: self.loaded.add(session)
            self._want(session, 'loadComplete')
        elif method == 'Runtime.bindingCalled' and m['params']['name'] == '__ae':
            try: event = json.loads(m['params']['payload'])
            except ValueError: return
            session = m.get('sessionId')
            if event.get('e') == 'tick': self._want(session, event.get('why', 'tick')); return      # a note for the tree reader, not an event for the predictor
            event['pageUrl'] = self.url_of.get(self.target_of.get(session))      # the address of the page the frame is in: a frame's own address is not the page's
            if event.get('e') == 'focusin' and type(event.get('seq')) is int: self._resolve(session, m['params'].get('executionContextId'), event)      # told on, and the tree read, once the browser has said which DOM node it is
            else: self._deliver(event); self._want(session, event.get('e'))

    @staticmethod
    def _complete(slot, message):
        slot['message'] = message; slot['event'].set()
        if slot.get('then'):
            try: slot['then'](message)
            except Exception: import traceback; traceback.print_exc()      # the reader of the socket must outlive what an answer is used for

    def _deliver(self, event, pending=False):
        """Hands an event to `on_event` in the order the page made them: one that waits for the browser's answer (a `focusin`, see `Resolution`) holds back the events after it, so that a key typed after a focus move is heard after it. Returns the entry to `_release`."""
        entry = {'event': event, 'ready': not pending}
        with self.out: self.outbox.append(entry); self._flush()
        return entry

    def _release(self, entry):
        with self.out: entry['ready'] = True; self._flush()

    def _flush(self):
        while self.outbox and self.outbox[0]['ready']: self.on_event(self.outbox.pop(0)['event'])

    def _resolve(self, session, context, event):
        """Tells on a `focusin` after asking the browser which element it is: see `Resolution`."""
        Resolution(self, session, event, self._deliver(event, pending=True)).start(context)

    def _want(self, session, why):
        if not session: return
        with self.wake: self.wanted.setdefault(session, set()).add(why); self.wake.notify()

    def _read(self, session, target, generation):
        """The converted tree of one page. The page's reader (incremental.py) is taken before the read: a page that is closed while it is read forgets its reader (`Target.detachedFromTarget`), and a tree made by a new one
        numbers every node again, which the predictor takes for a new document and speaks again."""
        import incremental
        reader = self.readers.get((generation, target)) or incremental.Reader(verify=self.verify, keep=self._keep if RAW_LOG else None)
        told = self._tell(reader, session)
        talk = []
        def ask(commands):
            answers = self.call_many(commands, session)
            if CONVERSATION_LOG and not reader.checking: talk.append([commands, answers])      # what `verify` asks for itself is not part of the read
            return answers
        with self.wake: contexts = dict(self.contexts.get(session, {}))      # the socket's reader changes them while this reads
        self.reading[session] = reader
        try: converted = reader.read(ask, contexts.get)
        finally: self.reading.pop(session, None)
        self._account(target, reader, converted)
        if CONVERSATION_LOG: self._talk(target, reader, talk, contexts, converted, told)
        if session in self.target_of: self.readers.setdefault((generation, target), reader)      # a page that went while it was read leaves nothing behind
        self.last_cost = dict(reader.cost)
        return converted

    def wait_for_first_reads(self, limit=6.0):
        """Returns when no page is being read for the first time, or `limit` seconds after the oldest such read began. The predictor's work (speech, sweeps) and the reading of a tree share one Python's lock: a page of twenty thousand
        nodes is read in 1.5 s alone and 4 s beside a sweep, which is longer than a test that walks it lasts, and a page that is closed before it has been read has no prediction at all."""
        while True:
            since = min((r.urgent_since for r in list(self.reading.values()) if r.urgent_since is not None), default=None)
            if since is None or time.time() - since > limit: return
            time.sleep(0.02)

    def _tell(self, reader, session):
        """What the browser said of the page since its last read, given to the reader (and returned as it was said, for AE_CONVERSATION)."""
        with self.wake: hints = self.hints.pop(session, ()); visits = self.visited.pop(session, ()); loaded = session in self.loaded; self.loaded.discard(session)      # what the reader of the socket has put down since the last read
        for nodes in hints: reader.updated(nodes)
        reader.visited(visits)
        if loaded: reader.loaded()
        return {'hints': list(hints), 'visits': sorted(visits), 'loaded': loaded}

    def _account(self, target, reader, converted):
        """The counts of the run's reads (the run summary's `treeReads`), and a record where `verify` found the incremental tree differ from a read from scratch."""
        how = reader.cost.get('how'); self.reads[how] += 1; self.reads[how + 'Ms'] = round(self.reads[how + 'Ms'] + reader.cost.get('totalMs', 0), 1)
        if reader.mismatches: self.reads['differing'] += 1; self.on_verify({'ok': False, 'page': target, 'diff': reader.mismatches, 'ax': reader.ax_found, 'nodes': len(converted['nodes'])})
        elif self.verify and how == 'incremental' and reader.cost.get('verified') == 'same': self.reads['verified'] += 1

    def _keep(self, raw):
        """AE_RAW=<file>: what each read was given, whole, one line each (as AE_RECORD keeps what the runtime was told), for the fixtures `test_axtree.py` converts."""
        with self.out, open(RAW_LOG, 'a') as f: f.write(json.dumps(raw, separators=(',', ':')) + '\n')

    def _talk(self, target, reader, talk, contexts, converted, told):
        """AE_CONVERSATION=<file>: each read as it was had, for a test to have it again: what the browser said since the last read, the commands sent and the answers, and the tree made. Every read is kept, so that the reader's
        state is the same when they are played in order; `verified` says whether `verify` found an incremental read the same as one from scratch."""
        with self.out, open(CONVERSATION_LOG, 'a') as f:
            f.write(json.dumps({'page': target, 'how': reader.cost.get('how'), 'reason': reader.cost.get('reason'), 'verified': reader.cost.get('verified'), 'contexts': contexts, 'told': told, 'conversation': talk, 'tree': converted}, separators=(',', ':')) + '\n')

    def _profile(self, page, why, took):
        """AE_PROFILE=<file>: one line for each tree read, with what it cost."""
        with self.out, open(PROFILE_LOG, 'a') as f: f.write(json.dumps({'at': round(time.time() * 1000), 'page': page, 'why': why, 'totalMs': round(took * 1000, 1), **self.last_cost}, separators=(',', ':')) + '\n')

    def _trees(self):
        """Reads the trees of the pages that have changed, one page at a time, and rests as long as a read took when that was more than a tenth of a second (so that reading is at most half the time of a busy page)."""
        while not self.stopped:
            with self.wake:
                while not self.wanted and not self.stopped: self.wake.wait(0.5)
                session, why = next(iter(self.wanted.items())) if self.wanted else (None, None)
                if session: self.wanted.pop(session, None)
            if not session: continue
            target = self.target_of.get(session)
            if target is None: continue
            started = time.time(); generation = self.generation
            try: converted = self._read(session, target, generation)
            except (RuntimeError, TimeoutError, ConnectionError, OSError, ValueError): continue      # the page is gone, or navigating: the next note reads it again
            except Exception:      # a tree this cannot convert is one tree lost, and not the end of the trees
                import traceback; traceback.print_exc(); continue
            if generation != self.generation: continue
            if len(converted['nodes']) <= 1: continue      # a document with nothing in it yet (the blank page a navigation starts from): its language, which the page has not set yet, would be taken for the page's
            self.seq += 1
            number = self.page_numbers.setdefault((generation, target), len(self.page_numbers))
            took = time.time() - started
            if PROFILE_LOG: self._profile(number, sorted(w for w in why if w), took)
            self.on_tree({'kind': 'snap', 'seq': self.seq, 't': round(started * 1000), 'page': number, 'why': sorted(w for w in why if w), 'ms': round(took * 1000, 1), **converted})
            if took > 0.1: time.sleep(min(took, 0.5))      # a page that is slow to read is not read more than half the time; a quick one is read again at once, because a test that is quick is closed in a few tens of milliseconds

    def _install(self, session, target):
        if target in self.installed: return
        self.installed.add(target); self.on_attach(target, self.browser)
        self._send('Runtime.enable', {}, session)      # without it the browser does not send `Runtime.bindingCalled`
        self._send('Runtime.addBinding', {'name': '__ae'}, session)
        self._send('Accessibility.enable', {}, session)      # the browser then says when a node it was asked about has changed (nodesUpdated) and when a document has loaded (loadComplete), and answers getChildAXNodes
        self._send('Page.enable', {}, session)      # the script below is run on each new document only while the Page domain is enabled
        self._send('Page.addScriptToEvaluateOnNewDocument', {'source': LISTENER}, session)
        self._send('Runtime.evaluate', {'expression': LISTENER}, session)      # the document already there
        self._send('Runtime.runIfWaitingForDebugger', {}, session)

    def stop(self):
        self.stopped = True
        with self.wake: self.wake.notify()
        if self.ws: self.ws.close()


class Resolution:
    """Tells on one `focusin` after asking the browser which element it was, as the event arrives and without holding up the tree: the DOM node (`DOM.describeNode`; the number the accessibility tree holds as
    `backendDOMNodeId`), and the role and name the browser computed for it (`Accessibility.getPartialAXTree`). Matching by these is exact where the page script's guess at a name is not (a name that CSS or a hidden span adds
    to is not in the element's own text). Two round trips, asked before the tree is read again so that the read does not hold them up. A page that is closed first, an element that is gone, a browser that does not answer
    within WAIT seconds (a page stopped in an alert, a socket that dropped) leave the event as the page sent it. Every answer is handled on the thread that reads the socket; the timer is the only other."""
    WAIT = 1.5

    def __init__(self, cdp, session, event, entry):
        self.cdp, self.session, self.event, self.entry = cdp, session, event, entry
        self.context = None; self.held = None; self.answers = {}; self.told = False; self.lock = threading.Lock()
        self.timer = threading.Timer(self.WAIT, self.tell); self.timer.daemon = True

    def start(self, context):
        self.context = context; self.timer.start()
        expression = f'window.__aeFocused && window.__aeFocused.get({self.event["seq"]})'      # the element the listener kept (LISTENER)
        self.ask('Runtime.evaluate', {'expression': expression, **({'contextId': context} if context is not None else {})}, self.on_element)

    def ask(self, method, params, then):
        try: self.cdp._post(method, params, self.session, then)
        except (OSError, ConnectionError, AttributeError): self.tell()

    def on_element(self, message):
        self.held = ((message.get('result') or {}).get('result') or {}).get('objectId')
        if not self.held: return self.tell()
        self.ask('DOM.describeNode', {'objectId': self.held}, lambda reply: self.on_answer('node', reply))
        self.ask('Accessibility.getPartialAXTree', {'objectId': self.held, 'fetchRelatives': False}, lambda reply: self.on_answer('ax', reply))

    def on_answer(self, name, reply):
        self.answers[name] = reply.get('result')
        if len(self.answers) < 2: return
        try:
            self.cdp._send('Runtime.releaseObject', {'objectId': self.held}, self.session)
            self.cdp._send('Runtime.evaluate', {'expression': f'window.__aeFocused && window.__aeFocused.delete({self.event["seq"]})', **({'contextId': self.context} if self.context is not None else {})}, self.session)      # the page is not kept holding the element
            self.event.update(self.what_is(self.answers['node'], self.answers['ax']))
        finally: self.tell()

    def tell(self):
        with self.lock:
            if self.told: return
            self.told = True
        self.timer.cancel(); self.cdp._release(self.entry)
        if self.event.get('backendNodeId') is not None:      # the reader reads the nodes the focus has been on again
            with self.cdp.wake: self.cdp.visited.setdefault(self.session, set()).add(self.event['backendNodeId'])
        self.cdp._want(self.session, 'focusin')      # and now the tree is read

    @staticmethod
    def what_is(node, ax):
        """What the browser said of an element: `{backendNodeId, axName, axRole}`, with what it could not say left out."""
        import axtree
        backend = ((node or {}).get('node') or {}).get('backendNodeId')
        if backend is None: return {}
        own = next((n for n in (ax or {}).get('nodes') or [] if n.get('backendDOMNodeId') == backend and not n.get('ignored')), None)
        if own is None: return {'backendNodeId': backend}
        return {'backendNodeId': backend, 'axName': own['name'].get('value', '') if isinstance(own.get('name'), dict) else '', 'axRole': axtree.role_of(own)}
