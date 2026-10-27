"""The tree of one page, read again at the cost of what changed (A11-229).

A read of `Accessibility.getFullAXTree` and `DOMSnapshot.captureSnapshot` is proportional to the page (0.5 s and 0.2 s for the 16,000 nodes of a Wikipedia table), and the middleware read both after each key, so that a walk
through a page of 1,700 tab stops was a walk of hours. A key moves the focus. It rarely changes the page. So the page keeps what the last full read gave (`Page`), and a later read first asks the page, with the probe cdp.py's listener
installs, whether anything but the focus, the value of a form control and the `title`, `class`, `style` or `data-*` of an element could have changed since:

    the document is the one that was read, no element, other attribute or text was changed (`muts`), no element has another box, `display` or `visibility` (`layout`), the page has no shadow tree, each of its frames
    says the same of itself, and fewer than MAX_RUN reads have been made from the full read.

Then the AX tree is refreshed where it can have changed and nowhere else (see `update`), the style a :focus rule or a class changes is read again for the elements it can have changed it in, and the list of nodes is brought up to date
(`Converter.patch`: the nodes that can have changed are made again, the rest is the list made before) or, when the shape of the tree changed, made again from the AX nodes held: no DOM snapshot and no whole AX tree is fetched.
Anything else is a full read, which is always safe: a first read, a new document, a change the probe or the AX tree reports that this does not know how to take, a node it was not told of, a frame that changed, a read that fails half way.

What an incremental read does not see, and keeps as it was until the next full read (a mutation, a box that moved, MAX_RUN reads): the look (colours, fonts) of an element outside the focus chain that a rule restyles
because the focus moved or something was checked (a sibling of the focused element, `input:focus + .hint`; `input:checked + label`; `:visited`), or that CSS alone changes (a :hover rule, an animation); the text that a
pseudo-element generates; a click listener the page adds with script after it has loaded; a closed shadow tree; and a node the browser makes later with no event and no change of the page. The last is why a document just come is read
whole until two reads agree (`settle`). None of the others is something NVDA says in the settings the emulator is run with. `verify` reads the page from scratch after each incremental read and says where the two trees differ.
"""
import json, time

import axtree

MAX_RUN = 25      # incremental reads in a row before a full one
FUTILE = 4      # full reads in a row that the probe asked for (a page that never stops changing) after which the probe is not asked for a while: it costs a fifth of a full read on a page that only changes
MAX_BACKOFF = 32      # the most reads in a row made without the probe
HEAVY = 3000      # elements of a page that is dear to read: one still loading is waited for (at most LOAD_WAIT seconds) and read once, loaded, not twice
LOAD_WAIT = 4.0
AFTER_BACK_OFF = 'a page that was read without the probe'
MAX_SETTLE = 3      # whole reads of a young document that are compared with the one before; after them the tree is trusted whether the last two agreed or not
MAX_VISITS = 400      # elements the focus has been on, since the last read, that are read again; more is a full read
MAX_SUBTREE = 400      # nodes below a control or an element whose class changed that are read again at most; an element that holds more is a full read
COSMETIC = ['color', 'background-color', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration-line']      # axtree.py STYLES but `display` and `visibility`, which the probe's `layout` covers
PROBE = "window.__aeProbe ? window.__aeProbe(%s, %s) : null"
FORM_TAGS = ('input', 'select', 'textarea')
FRAME_TAGS = ('iframe', 'frame', 'object', 'embed')
RELATIONS = ('labelledby', 'describedby', 'details', 'errormessage')      # the AX properties that say a node is named or described by another


class Stale(Exception):
    """The cached tree cannot be brought up to date from the parts of it that changed: the page is read from scratch. The reason is the message."""


def focused(node): return any(p['name'] == 'focused' and p['value'].get('value') for p in node.get('properties', []))


def differences(a, b, limit=5):
    """Where two converted trees differ: [[ix, role, [[field, a, b], ...]], ...], at most `limit` nodes, and a note for a difference in the number of nodes or in the fields of the tree."""
    out = []
    if len(a['nodes']) != len(b['nodes']): out.append(['count', len(a['nodes']), len(b['nodes'])])
    for x, y in zip(a['nodes'], b['nodes']):
        if x == y: continue
        out.append([x['ix'], x['role'], [[k, x.get(k), y.get(k)] for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)][:6]])
        if len(out) >= limit: break
    for k in ('focusIx', 'url', 'title', 'sel'):
        if a.get(k) != b.get(k): out.append([k, a.get(k), b.get(k)])
    return out


def ax_differences(held, now, limit=8):
    """Where two sets of AX nodes (by id) differ in what makes the tree: [[id, {field: [held, now]}], ...]. The ids of the nodes that have no element (the boxes a line of text is made of) are made again by the browser and are not a difference."""
    out = []
    for key, was in held.items():
        if key not in now or was == now[key]: continue
        bits = {x: [was.get(x), now[key].get(x)] for x in ('role', 'ignored', 'parentId', 'backendDOMNodeId', 'name') if was.get(x) != now[key].get(x)}
        if bits: out.append([key, bits])
        if len(out) >= limit: break
    return out


def signature(ax):
    """What the shape of a tree is, as a number: its nodes, which are left out of it, and which nodes each holds. The nodes that have no element (the boxes a line of text is made of) are made again by the browser with other ids and are left out."""
    return hash(tuple((n['nodeId'], bool(n.get('ignored')), tuple(c for c in n.get('childIds', []) if not c.startswith('-'))) for n in ax if not n['nodeId'].startswith('-')))


def related_by(nodes):
    """{the DOM node a node is named or described by: [the DOM nodes of those nodes]}"""
    out = {}
    for n in nodes:
        for p in n.get('properties', []):
            if p['name'] in RELATIONS:
                for target in p['value'].get('relatedNodes') or []:
                    if 'backendDOMNodeId' in target and n.get('backendDOMNodeId') is not None: out.setdefault(target['backendDOMNodeId'], []).append(n['backendDOMNodeId'])
    return out


class Page:
    """What is held of one page between reads: the AX nodes by id, the page's elements, the answer of the probe the last full read began with, and the frames: their ids, the AX nodes of their trees and what their probes said."""
    def __init__(self, ax, dom, probe, viewport, frames=None, frame_probes=None):
        self.signature = signature(ax)
        self.frames = frames or {}; self.frame_ids = list(self.frames); self.frame_probes = frame_probes or {}
        self.frame_ax = axtree.prefix_frames(self.frames)[0]      # the nodes of the frames' trees by their prefixed ids, as `Converter.patch` finds them
        self.ax = {n['nodeId']: n for n in ax}; self.dom = dom; self.probe = probe; self.run = 0; self.viewport = viewport
        self.node_of = {}      # the DOM nodes that have an AX node in the tree, and the node (the browser makes an ignored one up for any other when it is asked)
        for n in ax:
            if 'backendDOMNodeId' in n and (n['backendDOMNodeId'] not in self.node_of or not n.get('ignored')): self.node_of[n['backendDOMNodeId']] = n['nodeId']
        self.related = None      # {a DOM node: the DOM nodes whose AX nodes name or describe themselves by it}, made when a control changes
        self.focused = {n['nodeId'] for n in ax if focused(n)}      # the nodes the browser's tree has the focus on: the document, and the element (kept up to date by `Reader.hold`)
        self.root = next((n['nodeId'] for n in ax if 'parentId' not in n), None)
        self.index = {backend: i for i, backend in enumerate(dom.elements)}      # the number the probe gives an element
        self.controls = [backend for backend in dom.elements if dom.get(backend).get('tag') in FORM_TAGS]      # the form controls, in the order the probe digests them


class Reader:
    """Reads the tree of one page, fully or incrementally. `converter` is the page's: it numbers the nodes, and a node keeps its number from one read to the next."""
    def __init__(self, converter=None, verify=False, keep=None):
        self.converter = converter or axtree.Converter(); self.page = None; self.verify = verify; self.keep = keep      # keep(raw): called with what each full read was given (AE_RAW)
        self.force = None      # why the next read is a full one, when something other than the probe has said so (the browser: a document loaded)
        self.hints = {}      # AX nodes the browser said have changed (`Accessibility.nodesUpdated`), by id, to be used by the next incremental read
        self.visits = set()      # the DOM nodes that took the focus since the last read (the page's `focusin` events): the browser's tree remembers where the focus has been
        self.cost = {}; self.mismatches = []; self.ax_found = []; self.touched = set(); self.contexts = lambda frame: None; self.checking = False
        self.futile = 0      # full reads in a row that a change of the page asked for
        self.skip = 0      # reads still to be made whole without asking the probe
        self.urgent_since = None      # when the whole read of a page's first tree began, while it is being made: the predictor waits for it (cdp.py `Cdp.wait_for_first_reads`)
        self.unsettled = 0      # the whole reads of a document that has just come, since the first, while the tree they gave was not the tree the read before gave

    # ---- what the browser says without being asked
    def updated(self, nodes):
        for n in nodes: self.hints[n['nodeId']] = n

    def loaded(self): self.force = 'loadComplete'

    def visited(self, backends): self.visits |= set(backends)

    # ---- the read
    def read(self, call_many, contexts=lambda frame: None):
        """The converted tree of the page now. `contexts(frame)` is the execution context a frame's script runs in, for the probe. `self.cost` says how it was made and what it cost; `self.mismatches` what `verify` found different
        in it from a read from scratch."""
        began = time.perf_counter(); self.mismatches = []; self.ax_found = []; self.contexts = contexts
        if self.skip > 0 and self.page is not None:      # a page that changes all the time: read whole, as it was before the probe, and look again in a while
            self.skip -= 1
            converted = self.full(call_many, 'a page that keeps changing', None, None, asked=False)
        else:
            before = [self.page.probe.get('active', -1), *(self.page.index[b] for b in self.visits if b in self.page.index)] if self.page and self.page.probe else -1      # where the focus was and where it has been: their look is read again
            probe, state = self.look(call_many, self.page is None, before)
            reason = self.force or self.reason(probe, state)
            if reason in ('first', 'document'): probe, state = self.after_load(call_many, probe, state, before)
            converted = None
            if reason is None:
                try: converted = self.refresh(call_many, probe, state); self.futile = 0
                except (Stale, KeyError, RuntimeError, TimeoutError) as e: reason = f'stale: {type(e).__name__} {e}'
            if converted is None:
                self.back_off(reason)
                converted = self.full(call_many, reason, probe, state)
        self.cost['totalMs'] = round((time.perf_counter() - began) * 1000, 1)
        return converted

    def after_load(self, call_many, probe, state, before):
        """The first read of a document of HEAVY elements or more that is still loading waits for it, up to LOAD_WAIT seconds: a read of twenty thousand nodes takes seconds, the tree of a page that has not loaded is not
        spoken from (predict.py) and the page is read again as soon as it has, so that a test that is over before the second read is over has no prediction at all."""
        began = time.time()
        while probe is not None and probe.get('elements', 0) >= HEAVY and state['page']['readyState'] != 'complete' and time.time() - began < LOAD_WAIT:
            time.sleep(0.1)
            probe, state = self.look(call_many, self.page is None, before)
        return probe, state

    def back_off(self, reason):
        """A page that changed again and again is read whole, so the probe, which walks all its elements, is of no use: it is left out for 1, 2, 4... reads (MAX_BACKOFF) after FUTILE full reads in a row that its changes asked for."""
        if reason in ('first', 'document', 'loadComplete', 'settling', 'no probe', 'keyframe') or self.page is None: self.futile = 0; return
        if reason == AFTER_BACK_OFF: return      # the first read after the probe was left out is whole, for there is nothing to compare with: it says nothing of the page
        self.futile += 1
        if self.futile >= FUTILE: self.skip = min(2 ** (self.futile - FUTILE), MAX_BACKOFF)

    def look(self, call_many, baseline, before):
        """The probe, and the state of the page the conversion needs: asked together, with the probes of the frames the last read held."""
        held = [f for f in (self.page.frame_ids if self.page else []) if self.contexts(f) is not None]
        probe, page, metrics, tree = call_many([('Runtime.evaluate', {'expression': PROBE % ('true' if baseline else 'false', json.dumps(before)), 'returnByValue': True}), ('Runtime.evaluate', {'expression': axtree.PAGE_JS, 'returnByValue': True}),
                                                ('Page.getLayoutMetrics', {}), ('Page.getFrameTree', {})])
        if 'value' not in page.get('result', {}): raise ValueError('the page has no state to read (it is closing)')
        value = probe.get('result', {}).get('value')
        frames = self.frame_probes(call_many, held, 'false')
        return (json.loads(value) if value else None), {'page': json.loads(page['result']['value']), 'viewport': metrics.get('cssVisualViewport') or metrics.get('visualViewport'), 'frames': axtree.frame_ids(tree), 'frame_probes': frames}

    def reason(self, probe, state):
        """Why the page has to be read from scratch, or None when it can be brought up to date."""
        if self.page is None: return 'first'
        if probe is None: return 'no probe'
        if self.page.probe is None: return AFTER_BACK_OFF      # it was read whole without the probe: there is nothing to compare with
        if state['frames'] != self.page.frame_ids: return 'frames'
        for frame in state['frames']:
            if self.frame_changed(frame, state['frame_probes'].get(frame)): return 'a frame changed'
        if probe['doc'] != self.page.probe['doc']: return 'document'
        if self.unsettled: return 'settling'      # the browser may not have made all its tree of a document it was asked for just now: the next whole read is compared with this one
        if probe['muts'] != self.page.probe['muts']: return 'mutation'
        if probe['soft'] is None: return 'an element that is gone'
        if probe['layout'] != 0: return 'layout'
        if probe['shadows'] or self.page.dom.shadowed: return 'shadow tree'
        if probe['active'] == -2: return 'focus in a shadow tree'
        if probe['elements'] != len(self.page.dom.elements): return 'elements'
        if len(probe['forms']) != len(self.page.probe['forms']): return 'forms'
        if self.page.run >= MAX_RUN: return 'keyframe'
        return None

    def frame_changed(self, frame, now):
        """Whether a frame can have changed since the full read: it has no probe, or its document, its elements, its layout, its forms or its focus are not what they were. A frame is read again whole."""
        was = self.page.frame_probes.get(frame)
        if now is None or was is None: return True
        return (now['doc'] != was['doc'] or now['muts'] != was['muts'] or now['soft'] != [] or now['layout'] != 0 or now['shadows'] or now['elements'] != was['elements'] or now['forms'] != was['forms'] or now['active'] != was['active'])

    # ---- a full read
    def full(self, call_many, reason, probe=None, state=None, asked=True):
        self.urgent_since = time.time() if reason in ('first', 'document') else None
        try: return self.read_whole(call_many, reason, probe, state, asked)
        finally: self.urgent_since = None

    def read_whole(self, call_many, reason, probe, state, asked):
        began = time.perf_counter()
        if asked and reason != 'first' and probe is not None: self.commit(call_many)      # what the probe saw is what the read that follows is of
        frame_probes = self.baselines(call_many, state['frames']) if state else {}
        raw = axtree.fetch(call_many)
        if self.keep: self.keep(raw)
        fetched = time.perf_counter()
        raw['_dom'] = axtree.Dom(raw['dom'], raw.get('listeners', ()))
        converted = self.converter.convert(raw, retain=True)
        done = time.perf_counter()
        before = self.page
        self.page = Page(raw['ax'], raw['_dom'], probe if asked else None, raw['viewport'], raw.get('frames'), frame_probes)
        self.settle(reason, before)
        self.force = None; self.hints = {}; self.visits = set()
        self.cost = {'how': 'full', 'reason': reason, 'fetchMs': round((fetched - began) * 1000, 1), 'convertMs': round((done - fetched) * 1000, 1), 'nodes': len(converted['nodes'])}
        return converted

    def settle(self, reason, before):
        """A document just come is read whole until two reads in a row give the same shape of tree (MAX_SETTLE at most): the browser makes some of its tree after the load, with no event, and an incremental read would keep the
        tree it had. The first read of a document has nothing to be compared with; one the browser says is the load's end, or that is made because the tree had not settled, is compared with the one before."""
        if reason in ('first', 'document'): self.unsettled = 1; return
        if reason == 'loadComplete' and not self.unsettled: self.unsettled = 1
        elif self.unsettled: self.unsettled += 1
        else: return
        if (before is not None and before.signature == self.page.signature) or self.unsettled > MAX_SETTLE: self.unsettled = 0

    @staticmethod
    def commit(call_many):
        """The page takes what the last probe saw as what has been read."""
        call_many([('Runtime.evaluate', {'expression': 'window.__aeCommit && window.__aeCommit()'})])

    def baselines(self, call_many, frames):
        """The probe of each frame, taken as the state the full read that follows is of; None for a frame that has no script context here or no probe."""
        found = self.frame_probes(call_many, [f for f in frames if self.contexts(f) is not None], 'true')
        return {f: found.get(f) for f in frames}

    def frame_probes(self, call_many, frames, baseline):
        """The probe of each of the frames, asked in the frame's script context: None for one that does not answer (a context the browser took away while the read was made), whose frame is then read whole."""
        if not frames: return {}
        try: answers = call_many([('Runtime.evaluate', {'expression': PROBE % (baseline, '-1'), 'returnByValue': True, 'contextId': self.contexts(f)}) for f in frames])
        except RuntimeError: return {f: None for f in frames}
        return {f: (json.loads(a['result']['value']) if a.get('result', {}).get('value') else None) for f, a in zip(frames, answers)}

    # ---- an incremental read
    def refresh(self, call_many, probe, state):
        began = time.perf_counter(); self.cost = {}
        converted, targets, changed, refreshed = self.update(call_many, probe, state)
        done = time.perf_counter()
        self.commit(call_many)
        self.page.probe = probe; self.page.run += 1
        self.cost = {**self.cost, 'how': 'incremental', 'reason': None, 'fetchMs': round((refreshed - began) * 1000, 1), 'convertMs': round((done - refreshed) * 1000, 1), 'nodes': len(converted['nodes']), 'refreshed': targets, 'controls': changed}
        if self.verify: converted = self.check(call_many, converted, probe)
        return converted

    def update(self, call_many, probe, state):
        """The held page brought up to date with what the probe says and converted: the tree, how many AX nodes were read again, how many controls changed, and when the reading was done."""
        page = self.page
        changed = [i for i, (a, b) in enumerate(zip(page.probe['forms'], probe['forms'])) if a != b]
        if len(page.controls) != len(probe['forms']): raise Stale('the form controls are not those of the page')
        for index in (probe['active'], page.probe['active']):      # the focus entering or leaving a frame is in the frame's tree, which is not read again here
            if index >= 0 and page.dom.get(page.dom.elements[index]).get('tag') in FRAME_TAGS: raise Stale('the focus is on a frame')
        if len(self.visits) > MAX_VISITS: raise Stale('the focus has been on a great many elements')
        restyled = self.restyle(page, probe); self.touched = set()
        softened = self.rewrite(page, probe)
        below = [page.controls[i] for i in changed] + softened      # the elements whose subtree is read again
        targets = self.nodes_to_read(probe, changed, softened)
        reshaped = self.read_nodes(call_many, targets, below)
        refreshed = time.perf_counter()
        return self.convert_again(reshaped, restyled, state), len(targets), len(changed), refreshed

    def nodes_to_read(self, probe, changed, softened):
        """The DOM nodes whose AX nodes are read again, in a fixed order: the document; the nodes the browser's tree has the focus on; the element that has the focus and the one that had it, and the elements above them; every
        element the focus has been on since the last read, and the ones above them (the browser's tree keeps what the focus did to them, which the layout does not); a control whose value changed and what is named or described
        by it; an element whose `title`, `class` or `style` changed and the ones above it. Only DOM nodes that have an AX node in the tree: the browser makes an ignored one up for any other."""
        page = self.page; targets = set()
        def want(backend):
            if backend is not None and backend in page.node_of: targets.add(backend)
        def want_chain(backend):
            while backend is not None and backend in page.dom.by_backend: want(backend); backend = page.dom.get(backend).get('up')
        want(page.ax[page.root].get('backendDOMNodeId'))
        for node_id in page.focused: want(page.ax[node_id].get('backendDOMNodeId'))
        for index in (probe['active'], page.probe['active']):
            if index >= 0: want_chain(page.dom.elements[index])
        for backend in [*self.visits, *softened]: want_chain(backend)
        named_by = [page.controls[i] for i in changed] + softened      # what is named or described by a control whose value changed, or by an element whose title changed, is read again
        if named_by and page.related is None: page.related = related_by(page.ax.values())
        for backend in named_by:
            want(backend)
            for dependent in page.related.get(backend, ()): want(dependent)
        self.visits = set()
        return sorted(targets)      # the same questions in the same order whatever order the sets above were walked in: a recorded read can be played again

    def read_nodes(self, call_many, targets, below):
        """Reads the AX nodes of `targets` again, and everything below the elements of `below`, into the held page. True if the shape of the tree below any of those elements changed (a node came or went, or was left out of the
        tree or put in it)."""
        page = self.page
        for node in self.hints.values():      # what the browser said has changed is used, and replaced by what is read now
            if node['nodeId'] in page.ax: self.put(node, False)
        self.hints = {}
        shapes = {backend: self.shape(backend) for backend in below}
        answers = call_many([('Accessibility.getPartialAXTree', {'backendNodeId': backend, 'fetchRelatives': False}) for backend in targets])
        held = set(below)
        for backend, answer in zip(targets, answers):
            for node in answer['nodes']:
                try: self.put(node, backend in held)
                except Stale as e: raise Stale(f'{e} (read for a <{page.dom.get(backend).get("tag")}>, {len(answer["nodes"])} nodes answered, ignored={node.get("ignored")})')
        for backend in below: self.reread_below(call_many, backend)
        reshaped = any(self.shape(backend) != shape for backend, shape in shapes.items())
        if below: page.ax = self.reachable(page); page.focused &= page.ax.keys()
        return reshaped

    def convert_again(self, reshaped, restyled, state):
        """The list of nodes for the held page: the one made before brought up to date when the shape of the tree is what it was and only the focus, the look, the names and the page's state changed, else made again from the AX nodes held."""
        page = self.page; converted = None
        if not reshaped:
            try: converted = self.converter.patch({**page.ax, **page.frame_ax} if page.frame_ax else page.ax, self.touched, restyled, page.dom, state['page'], state['viewport'])
            except axtree.Unpatchable as e: self.cost['unpatchable'] = str(e)
        self.cost['patched'] = converted is not None
        if converted is None:
            raw = {'ax': list(page.ax.values()), '_dom': page.dom, 'dom': None, 'viewport': state['viewport'], 'page': state['page'], 'frames': page.frames, 'listeners': ()}
            converted = self.converter.convert(raw, retain=True)
        return converted

    def put(self, node, may_change_below):
        """An AX node read again replaces the one held. It must be one that is held, and its children the same, unless it is a control whose value changed or an element whose class changed (what is below is read again)."""
        old = self.page.ax.get(node['nodeId'])
        if old is None: raise Stale(f'a node the page did not have: {node["nodeId"]}')
        if not may_change_below and (old.get('childIds') != node.get('childIds') or old.get('ignored') != node.get('ignored') or old.get('parentId') != node.get('parentId')): raise Stale('the structure of the tree changed')
        self.hold(node)

    def hold(self, node):
        """An AX node read again takes the place of the one held."""
        page = self.page; page.ax[node['nodeId']] = node; self.touched.add(node['nodeId'])
        if 'backendDOMNodeId' in node: page.node_of.setdefault(node['backendDOMNodeId'], node['nodeId'])
        if focused(node): page.focused.add(node['nodeId'])
        else: page.focused.discard(node['nodeId'])

    def shape(self, backend):
        """The shape of the tree below the AX node of a DOM node: each node with whether it is left out and which nodes it holds, as it is held."""
        page = self.page; out = set(); stack = [page.node_of.get(backend)]
        while stack:
            n = page.ax.get(stack.pop())
            if n is None: continue
            out.add((n['nodeId'], n.get('ignored'), tuple(n.get('childIds', [])))); stack.extend(n.get('childIds', []))
            if len(out) > 4 * MAX_SUBTREE: break
        return frozenset(out)

    def reread_below(self, call_many, backend):
        """Everything below a form control whose value changed, or an element whose class changed: its text is made of nodes that come and go as the value does, and a class can show or hide what is in an element."""
        page = self.page; top = page.ax.get(page.node_of.get(backend))
        if top is None: raise Stale('an element with no AX node')
        frontier = [top]; seen = 0
        while frontier:
            answers = call_many([('Accessibility.getChildAXNodes', {'id': n['nodeId']}) for n in frontier])
            frontier = []
            for answer in answers:
                for child in answer['nodes']:
                    self.hold(child); frontier.append(child); seen += 1
            if seen > MAX_SUBTREE: raise Stale('an element that holds a great deal')

    @staticmethod
    def reachable(page):
        """The AX nodes that can be reached from the document: what a control held before its value changed is gone."""
        out = {}; stack = [page.root]
        while stack:
            n = page.ax.get(stack.pop())
            if n is None or n['nodeId'] in out: continue
            out[n['nodeId']] = n; stack.extend(n.get('childIds', []))
        return out

    @staticmethod
    def rewrite(page, probe):
        """The attributes the page says an element has now (a `title`, `class`, `style` or `data-*` one changed), in the elements held. The text below the element must be drawn where the snapshot has it drawn, or not
        drawn where it has none: a class can show text that was not shown, and then the snapshot has no box or style for it. Returns the DOM nodes."""
        out = []
        for index, tag, attrs, texts in probe['soft']:
            backend = page.dom.elements[index]; held = page.dom.get(backend)
            if held.get('tag') != tag: raise Stale('an element is not the one the page numbers')
            below = Reader.texts_below(page.dom, backend)
            if len(below) != len(texts): raise Stale('the text below an element is not the text the page has')
            for text, drawn in zip(below, texts):
                box = page.dom.get(text).get('bounds')
                if (box is None) != (drawn is None) or (box is not None and any(abs(a - b) > 1 for a, b in zip(box, drawn))): raise Stale('text is drawn where it was not')
            held['attrs'] = attrs; out.append(backend)
        return out

    @staticmethod
    def texts_below(dom, backend):
        """The text nodes below an element, in document order, as the page's tree walker lists them: not the ones of a pseudo-element."""
        out = []; stack = list(reversed(dom.get(backend)['children']))
        while stack:
            node = dom.get(stack.pop())
            if node.get('pseudo'): continue
            if node.get('type') == 3: out.append(node['backend'])
            else: stack.extend(reversed(node['children']))
        return out

    def restyle(self, page, probe):
        """The style the focused element has now, with the ones above it and below it (a :focus rule changes it, and what inherits it), in the elements held, in their pseudo-elements and in the text each holds: a text takes
        the style of the element or pseudo-element it is in. Returns the DOM nodes it set the style of."""
        dom = page.dom; touched = set()
        if probe['looks'] is None: raise Stale('the focus chain holds a great deal')
        for index, tag, values, pseudo in probe['looks']:
            backend = dom.elements[index]; held = dom.get(backend)
            if held.get('tag') != tag: raise Stale('an element is not the one the page numbers')
            if 'style' not in held: continue
            self.set_style(dom, backend, values, touched)
            for child in held['children']:
                kid = dom.get(child)
                if not kid.get('pseudo'): continue
                if kid['pseudo'] not in pseudo or 'style' not in kid: raise Stale(f'a ::{kid["pseudo"]} the page does not describe')
                self.set_style(dom, child, pseudo[kid['pseudo']], touched)
        return touched

    @staticmethod
    def set_style(dom, backend, values, touched):
        """The style of an element or a pseudo-element, and of the text directly below it."""
        style = dict(zip(axtree.STYLES, values)); held = dom.get(backend)
        for node in [backend, *(child for child in held['children'] if dom.get(child).get('type') == 3 and 'style' in dom.get(child))]:
            for name in COSMETIC: dom.get(node)['style'][name] = style[name]
            touched.add(node)

    # ---- the check
    def check(self, call_many, converted, probe):
        """`verify`: the page read from scratch, as the next full read would, and where it differs from `converted`. Only a page that did not change while it was read is compared (the probe says so), and the browser's tree
        follows a move of the focus a moment after the page's: a difference is then looked at again with the held page brought up to date once more, and counts only if it is still there. The tree used is the one read
        from scratch, and the page is held as it says, when the two differ."""
        self.checking = True
        try: return self.compare(call_many, converted, probe)
        finally: self.checking = False

    def compare(self, call_many, converted, probe):
        raw = axtree.fetch(call_many)
        raw['_dom'] = axtree.Dom(raw['dom'], raw.get('listeners', ()))
        after = self.look(call_many, False, probe['active'])[0]
        if after is None or after['muts'] != probe['muts'] or after['active'] != probe['active'] or after['forms'] != probe['forms'] or after['layout'] != 0: self.cost['verified'] = 'the page changed'; return converted
        twin = axtree.Converter(); twin.uids = dict(self.converter.uids); twin.next_uid = self.converter.next_uid
        fresh = twin.convert(raw)
        found = differences(converted, fresh)
        if found:
            try: again = self.update(call_many, after, {'viewport': raw['viewport'], 'page': raw['page']})[0]
            except (Stale, KeyError, RuntimeError, TimeoutError): again = None
            found = differences(again, fresh) if again is not None else found
        self.cost['verified'] = 'differs' if found else 'same'
        if found:
            self.mismatches = found; self.ax_found = ax_differences(self.page.ax, {n['nodeId']: n for n in raw['ax']})
            self.converter.uids = twin.uids; self.converter.next_uid = twin.next_uid
            self.page = Page(raw['ax'], raw['_dom'], self.page.probe, raw['viewport'], raw.get('frames'), self.page.frame_probes)
            self.converter.convert(raw, retain=True)      # what a later patch brings up to date is the page as it is
            return fresh
        return converted
