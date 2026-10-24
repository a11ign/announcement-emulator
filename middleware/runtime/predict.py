"""Layer 5 of the emulator, on a browser it did not launch (A11-208).

`emu/live.py` drives a Chrome it started and asks it for the tree after each key it sends. A running Playwright test sends its own keys, so this is given the tree after each
change instead (`emu/ext2/passive.js` posts it) and works out from two trees in a row what NVDA would have been told:

    a document loaded      NVDA's own treeInterceptor_gainFocus on a fresh buffer: the title, then the line the caret starts on
    the focus moved        NVDA's own event_gainFocus through the browse-mode buffer, as `LiveDoc.gain_focus` does
    something on the focus changed   NVDA's own event_stateChange on the focus and its ancestors, as `LiveDoc.settle` does
    a key was typed        NVDA's own speakTypedCharacters, when focus mode is on (the key comes from the page, through cdp.py)
    a live region changed  the rules of nvdaHelper/remote/ia2LiveRegions.cpp, applied to the page's own changes (the script cdp.py installs), spoken the way nvdaControllerInternal_reportLiveRegion
                           speaks (speech.speakText). The page reports them, and not the tree, because a test that ends on a change closes the page before the tree can say so

What the test's keys do is not modelled: they reach Chrome over the DevTools protocol and not through NVDA, so this is NVDA's answer to the browser's events, and not NVDA's answer
to the key. What that leaves out is listed in docs/playwright-middleware-spike.md.

Every record it emits is a prediction (ADR 0047): `kind` is `speech`, `observe`, `sweep` or `flag`, and none of them is named for an a11ign evidence field.
"""
import difflib, hashlib, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
for sub in ('emu', 'q3'): sys.path.insert(0, os.path.join(ROOT, sub))      # the bundle keeps the repository's own layout
os.environ.setdefault('EMU_NVDA_INI', os.path.join(ROOT, 'q3', 'nvda-fleet.ini'))      # the fleet's NVDA settings, as q3/emulate.py runs them
os.environ.setdefault('EMU_FLEET_VOICES', '1')
import flags

SWEEP_LIMIT = 12      # sweeps per run: each costs seconds on a real page, and a run that reaches more states than this is not one a transcript is read for
SETTLE_MS = 400      # an event of the page that no later tree has come to answer, after this long, is answered with the tree there is


def phrase(strings): return ', '.join(s for s in (re.sub(r'\s+', ' ', x).strip() for x in strings if isinstance(x, str)) if s)


class SnapshotSession:
    """What `session.Session` answers for a browser nobody here launched: the tree of one snapshot, and a refusal for each thing that would reach the page.
    Everything refused is counted, so that a sweep can say how many keys it did not deliver."""
    def __init__(self, snap):
        self.snap = snap; self.sel = snap['sel']; self.refused = []

    def dump(self): self.sel = self.snap['sel']; return self.snap['nodes'], self.snap['focusIx']
    def _refuse(self, what, *args, **kwargs): self.refused.append(what)
    def key(self, *a, **k): self._refuse('key')
    def focus(self, *a, **k): self._refuse('focus')
    def action(self, *a, **k): self._refuse('action')
    def scroll(self, *a, **k): self._refuse('scroll')
    def click(self, *a, **k): self._refuse('click')
    def eval(self, *a, **k): self._refuse('eval')
    def close(self): pass


def by_uid(snap): return {n['uid']: n for n in snap['nodes']}
def focus_node(snap): return next((n for n in snap['nodes'] if n['ix'] == snap['focusIx']), None)
def index_children(snap):
    """Lookups the dump does not carry: node by ix, children by ix, parent by ix (the dump lists a node's children by the ix of each)."""
    pos = {n['ix']: n for n in snap['nodes']}
    snap['_pos'] = pos
    snap['_index'] = {n['ix']: [pos[c] for c in n.get('childrenIx', []) if c in pos] for n in snap['nodes']}
    snap['_parent'] = {c['ix']: pos[ix] for ix, kids in snap['_index'].items() for c in kids}
    return snap


def tree_signature(snap):
    """What a screen reader reads of a state: roles and names, in order. Two states with the same signature are one state to a sweep."""
    rows = [(n['role'], n.get('name') or '', n.get('value') or '') for n in snap['nodes'] if n['role'] not in ('inlineTextBox', 'lineBreak')]
    return hashlib.sha1(json.dumps(rows).encode()).hexdigest()[:16]


def without_fragment(url): return (url or '').split('#')[0]


class Page:
    def __init__(self, uid):
        self.uid = uid; self.last = None; self.root_uid = None; self.url = None; self.loaded = False; self.spoke_load = False; self.focus_uid = None
        self.observed = set(); self.swept = set(); self.reports_focus = False; self.sweep_wanted = None


def normal(text): return re.sub(r'\s+', ' ', text or '').strip()


def match_focus(snap, event):
    """The node of the tree the page's `focusin` is about: an element of that tag (and id), whose accessible name is one of the strings the page could make it from; the node the
    tree itself has focused if several fit. None if the tree does not have it (yet)."""
    names = {normal(n) for n in event.get('names', [])}
    fits = [n for n in snap['nodes'] if n.get('htmlTag') == event['tag'] and (not event.get('id') or n.get('htmlId') == event['id'])
            and ((normal(n.get('name')) in names) or (not names and not normal(n.get('name'))) or event.get('role'))]
    if len(fits) > 1:
        own = [n for n in fits if n['ix'] == snap['focusIx']]
        fits = own or fits
    return fits[0] if fits else None


class Predictor:
    def __init__(self, emit, sweeps=True, report_focus=False):
        import boot      # NVDA and its stand-ins; takes seconds
        boot.FAKE_APP_MODULE.__dict__.setdefault('_browseModeRememberedCaretPositions', {})      # what a buffer asks the app module for when a document first has the focus
        import driver, live, livepage, sweep
        self.boot, self.driver, self.live, self.livepage, self.sweep = boot, driver, live, livepage, sweep
        self.emit_record = emit; self.records = []; self.pages = {}; self.doc = None; self.doc_page = None; self.sweeps = sweeps; self.events = []
        self.report_focus = report_focus; self.pending_sweeps = []; self.sweep_count = 0; self.skipped_sweeps = 0
        self.stats = {'snapshots': 0, 'speechMs': 0.0, 'sweeps': [], 'keys': 0, 'focusEvents': 0, 'unresolvedFocus': 0}

    # ---- output
    def emit(self, record):
        self.records.append(record); self.emit_record(record)

    def spoken_since(self, start):
        """The utterances NVDA made since `start`: each speech sequence, its strings joined as Guidepup logs them."""
        return [p for p in (phrase(seq) for seq in self.driver.SPY.sequences[start:]) if p]

    def speak(self, cause, t, page, node, action, report=False):
        """Run `action` (something NVDA does) and record what it said. With `report`, and the runtime started to measure agreement, also what NVDA says when asked to repeat the focus (NVDA+Tab),
        which is the phrase the fleet's focus probe records for a Tab (screenreader-worker `reportFocusedControl`)."""
        start = len(self.driver.SPY.sequences); t0 = time.perf_counter()
        action(); self.driver._flush()
        ms = (time.perf_counter() - t0) * 1000; self.stats['speechMs'] += ms
        utterances = self.spoken_since(start)
        repeated = self.repeat_focus() if report and self.report_focus else None
        if not utterances: return None
        text = utterances[0] if len(utterances) == 1 else ' | '.join(utterances)
        import shapes
        record = {'kind': 'speech', 'cause': cause, 't': t, 'page': page.uid, 'url': page.url, 'text': text, 'utterances': utterances,
                  'shape': list(shapes.shape_of(utterances[0])), 'node': node, 'ms': round(ms, 1), **({'repeatFocus': repeated, 'repeatFocusShape': list(shapes.shape_of(repeated))} if repeated is not None else {})}
        self.emit(record)
        return record

    def repeat_focus(self):
        """NVDA+Tab on the focus, as the worker presses it; what it said is not part of the run's speech."""
        start = len(self.driver.SPY.sequences)
        self.driver.press(self.doc.b, 'nvda+tab'); self.driver._flush()
        phrases = self.spoken_since(start)
        del self.driver.SPY.sequences[start:]
        return phrases[-1] if phrases else ''

    # ---- documents
    def muted(self, action):
        """Run something NVDA would say and discard what it said: the state of a buffer that is being built again must be what it was, and nobody is to hear it."""
        start = len(self.driver.SPY.sequences)
        action(); self.driver._flush()
        del self.driver.SPY.sequences[start:]

    def document_for(self, page, snap, at_root=False):
        """The NVDA document for this page's snapshot: the one in use when it is the same page, else a new one, built without a sound, with the focus where the page last had it
        (the document itself for a page that has just loaded)."""
        if self.doc is not None and self.doc_page == page.uid:
            self.doc.s.snap = snap; return self.doc
        self.doc = self.live.LiveDoc(session=SnapshotSession(snap)); self.doc_page = page.uid
        self.doc.b._initialScrollObj = None
        f = (by_uid(snap).get(page.focus_uid) if page.focus_uid is not None else None) or focus_node(snap)
        if not at_root and f is not None and f['role'] != 'rootWebArea':
            self.muted(lambda: (self.doc.set_focus(self.doc.obj(f['ix'])), self.doc.b.event_gainFocus(self.doc.obj(f['ix']), lambda: None)))      # focus mode if the focus is in a field, as NVDA decides on the event
        return self.doc

    def node_info(self, node):
        return {'role': node['role'], 'name': node.get('name'), 'uid': node['uid']} if node else None

    def on_snapshot(self, snap):
        self.stats['snapshots'] += 1
        index_children(snap)
        t = snap['t']
        page = self.pages.setdefault(snap['page'], Page(snap['page']))
        root = snap['nodes'][0]
        new_document = page.last is None or page.root_uid != root['uid']
        route_change = not new_document and (root.get('docUrl') or snap['url']) != page.url      # a new address in the same document, a fragment too: a single-page app's route
        if new_document:
            if self.doc_page == page.uid: self.doc = None; self.doc_page = None
            page.root_uid = root['uid']; page.loaded = False; page.spoke_load = False; page.focus_uid = None; page.observed = set(); page.last = None; page.reports_focus = False; page.sweep_wanted = None
            self.emit({'kind': 'observe', 'what': 'navigation', 't': t, 'page': page.uid, 'url': snap['url'], 'node': None, 'text': snap['url']})
        page.url = root.get('docUrl') or snap['url']
        loaded = root.get('docLoaded', True)
        if loaded and not page.spoke_load and len(snap['nodes']) <= 1:      # the blank page a browser opens a tab with: nothing is there to hear
            page.last = snap; return
        if loaded and not page.spoke_load:
            page.spoke_load = True
            doc = self.document_for(page, snap, at_root=True)
            earliest = min([t] + [e['t'] for e in self.events if without_fragment(e.get('url')) == without_fragment(page.url)])      # the document loaded before anything the page did in it
            self.speak('load', earliest - 1, page, self.node_info(root), lambda: self.load_speech(doc))
            page.focus_uid = root['uid']      # a document has the focus when it has loaded; if the test's first key was faster than the extension, the focus is already on a control, and that is a move
            self.schedule_sweep(page, snap, t, 'load')
        elif loaded:
            self.document_for(page, snap)
            if route_change: self.schedule_sweep(page, snap, t, 'route')
        page.last = snap
        self.sweep_dialog(page)
        if loaded:
            self.events_until(t)
            if not page.reports_focus: self.sampled_focus(page, snap, t)      # no page script is telling of the focus: the tree's focus, as of this snapshot
            elif (focus_node(snap) or {}).get('uid') == page.focus_uid: self.speak('state', t, page, self.node_info(focus_node(snap)), lambda: self.doc.settle(acted=True))

    def sampled_focus(self, page, snap, t):
        f = focus_node(snap)
        if f is not None and f['uid'] != page.focus_uid: self.move_focus(page, snap, f, t)
        else: self.speak('state', t, page, self.node_info(f), lambda: self.doc.settle(acted=True))

    def move_focus(self, page, snap, node, t, in_dialog=False):
        """NVDA's own event_gainFocus for `node`, as the focus of `snap`."""
        self.document_for(page, snap)
        self.doc.s.snap = dict(snap, focusIx=node['ix'])
        self.speak('focus', t, page, dict(self.node_info(node), inDialog=in_dialog), lambda: (self.doc.refresh(), self.doc.gain_focus()), report=True)
        self.doc.s.snap = snap
        page.focus_uid = node['uid']

    def load_speech(self, doc):
        """The document has loaded and has the focus: NVDA's treeInterceptor_gainFocus for the first time (browseMode.py:1639-1700), with the fleet's autoSayAllOnPageLoad off."""
        doc.b._hadFirstGainFocus = False
        doc.b.event_treeInterceptor_gainFocus()

    def speak_live(self, text, politeness):
        import speech
        from speech.priorities import Spri
        speech.speakText(text, priority=Spri.NEXT if politeness == 'assertive' else Spri.NORMAL)      # NVDAHelper/__init__.py:268-300

    # ---- what the page itself reports: the focus and the keys (cdp.py)
    def on_page_event(self, event):
        """A trusted `focusin` or `keydown` from a page. It waits for the first tree at or after its time: the tree is what NVDA's answer is made from."""
        self.events.append(event); self.events.sort(key=lambda e: e['t'])

    def page_at(self, url):
        pages = [p for p in self.pages.values() if p.spoke_load and p.last is not None and without_fragment(p.url) == without_fragment(url)]
        return max(pages, key=lambda p: p.last['t']) if pages else None

    def events_until(self, t, final=False):
        """Answer the page's events that happened by `t` (all of them at the end), each against the newest tree of its page. A focus the tree does not have yet is tried again with the next tree."""
        waiting = []
        for e in self.events:
            page = self.page_at(e.get('url'))
            needs_tree = e['e'] in ('focusin', 'keydown')
            if page is None or (needs_tree and not final and (e['t'] > t or e['t'] > page.last['t'])):
                waiting.append(e); continue
            if not self.answer(page, e, final): waiting.append(dict(e, tries=e.get('tries', 0) + 1))
        self.events = waiting

    def settle_events(self, now):
        """Answer the events that have waited SETTLE_MS for a tree, with the newest one of their page."""
        cutoff = now * 1000 - SETTLE_MS
        keep = [e for e in self.events if e['t'] >= cutoff]
        self.events = [e for e in self.events if e['t'] < cutoff]
        self.events_until(float('inf'), final=True)
        self.events += keep; self.events.sort(key=lambda e: e['t'])

    def answer(self, page, e, final):
        if e['e'] == 'focusin':
            self.stats['focusEvents'] += 1
            node = match_focus(page.last, e)
            if node is None:
                if final or e.get('tries', 0) >= 2: self.stats['unresolvedFocus'] += 1; return True
                return False
            page.reports_focus = True
            if node['uid'] != page.focus_uid: self.move_focus(page, page.last, node, e['t'], in_dialog=bool(e.get('inDialog')))
            return True
        if e['e'] == 'live': self.speak('live', e['t'], page, None, lambda: self.speak_live(e['text'], e['politeness']))
        elif e['e'] == 'observe': self.observed(page, e)
        else: self.on_key(page, e)
        return True

    def observed(self, page, e):
        """Dialogs that are open and error messages that are showing, as the page reports them when they change: the ones not reported before are new."""
        for kind, items in (('dialog', e['dialogs']), ('error', e['errors'])):
            for item in items:
                key = (kind, item['tag'], item['id'], tuple(item['names']), item.get('text'))
                if key in page.observed: continue
                page.observed.add(key)
                if kind == 'dialog': page.sweep_wanted = ('dialog', e['t']); self.sweep_dialog(page)      # a dialog is a state of the page: swept when a tree shows it
                self.emit({'kind': 'observe', 'what': kind, 't': e['t'], 'page': page.uid, 'node': {'role': item['tag'], 'name': (item['names'] or [None])[0], 'uid': None}, 'text': item.get('text') or (item['names'] or [''])[0]})

    def on_key(self, page, event):
        """A trusted keydown. In focus mode on an editable field NVDA echoes a printable key; elsewhere the key is a command, and not modelled."""
        self.stats['keys'] += 1
        if event.get('ctrl') or event.get('alt') or event.get('meta') or len(event.get('key') or '') != 1: return
        self.document_for(page, page.last)      # a sweep may have used the buffer since the last event
        if not (event.get('at') or {}).get('editable') or not self.doc.b.passThrough: return
        import speech.speech
        self.speak('typed', event['t'], page, self.node_info(focus_node(page.last)), lambda: speech.speech.speakTypedCharacters(event['key']))

    # ---- sweeps
    def sweep_dialog(self, page):
        """The first tree at or after the page's report of a dialog that has a dialog in it."""
        if not page.sweep_wanted or page.last is None or page.last['t'] < page.sweep_wanted[1]: return
        if any(n['role'] in ('dialog', 'alertDialog') for n in page.last['nodes']):
            self.schedule_sweep(page, page.last, page.last['t'], page.sweep_wanted[0]); page.sweep_wanted = None

    def schedule_sweep(self, page, snap, t, trigger):
        if not self.sweeps: return
        key = (page.url, tree_signature(snap))
        if key in page.swept: return
        page.swept.add(key)
        if self.sweep_count + len(self.pending_sweeps) >= SWEEP_LIMIT: self.skipped_sweeps += 1; return
        self.pending_sweeps.append((page.uid, snap, t, trigger))

    def run_sweep(self, budget=120):
        """One pending sweep, over the snapshot it was scheduled with: the worker's structure sweep (q3/sweep.py, unchanged) over a page whose browser takes no key.
        Nothing is delivered to the test's browser; the sweep skips the lazy-content scroll and the activation of `collapsed` controls (docs/playwright-middleware-spike.md)."""
        if not self.pending_sweeps: return False
        page_uid, snap, t, trigger = self.pending_sweeps.pop(0)
        t0 = time.perf_counter(); self.sweep_count += 1
        session = SnapshotSession(snap)
        doc = self.livepage.LivePage(session=session); doc.b._initialScrollObj = None
        self.doc = None; self.doc_page = None      # the buffer in use is replaced; the next event builds its own
        w = self.sweep.Walker(doc, self.driver)
        for key in ('escape', 'control+end'): w.perform(key)      # the worker's sweeps begin where its read-through ended, at the bottom: previous-direction first collects the whole page
        structure, marks = self.sweep.structure_sweep(w, time.time() + budget)
        ms = (time.perf_counter() - t0) * 1000
        counts = {k: len(v) for k, v in structure.items()}
        self.stats['sweeps'].append(round(ms))
        self.emit({'kind': 'sweep', 't': t, 'page': page_uid, 'url': snap['url'], 'trigger': trigger, 'lists': structure, 'counts': counts, 'keys': w.actions, 'errors': w.errors,
                   'stops': {m['type']: [m['prevStop'], m['nextStop']] for m in marks}, 'notDelivered': len(session.refused), 'ms': round(ms)})
        return True

    # ---- the end
    def finish(self):
        self.events_until(float('inf'), final=True)
        while self.run_sweep(): pass
        for f in flags.derive_flags(self.records): self.emit(f)
        return {'snapshots': self.stats['snapshots'], 'speechMs': round(self.stats['speechMs']), 'sweepMs': self.stats['sweeps'], 'keys': self.stats['keys'], 'focusEvents': self.stats['focusEvents'],
                'unresolvedFocus': self.stats['unresolvedFocus'], 'skippedSweeps': self.skipped_sweeps}
