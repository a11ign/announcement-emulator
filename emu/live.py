"""Layer 0 + 5 for focus-driven keys: a live Chrome session whose Tab (and later other keys) is real, whose tree is re-read after each key,
and whose focus change is delivered to NVDA's own browse-mode event_gainFocus. The buffer is REBUILT from each new tree (NVDA updates
incrementally from events); the caret is carried over as storage.cpp does when it replaces a subtree: to the deepest field it was in that the new buffer still has (Buffer.correct_selection)."""
import time, hashlib, ctypes, weakref, boot
import driver, objlayer, standin, session, capture, textInfos, controlTypes, globalVars
import NVDAObjects.IAccessible as NI
import treeInterceptorHandler
from objlayer import HWND

L = driver.L
ARROWS = {'upArrow': ('ArrowUp', 0), 'downArrow': ('ArrowDown', 0), 'leftArrow': ('ArrowLeft', 0), 'rightArrow': ('ArrowRight', 0),
          'control+leftArrow': ('ArrowLeft', 2), 'control+rightArrow': ('ArrowRight', 2), 'home': ('Home', 0), 'end': ('End', 0), 'control+home': ('Home', 2), 'control+end': ('End', 2)}

class LiveDoc:
    def __init__(self, case_html=None, url=None, port=8765, history=None):
        """A system test's page (`case_html`, wrapped as ChromeLib._writeTestFile wraps it), or a live address (`url`)."""
        if url is None:
            key = hashlib.sha1(case_html.encode()).hexdigest()[:12]
            page = capture.CACHE / f'live-{key}.html'
            page.write_text(capture.WRAP.format(title='NVDA Browser Test Case', case=case_html))
            self.s = session.Session(page, port=port); time.sleep(1.5)
        else:
            self.s = session.Session(url=url, port=port); self.navigated = self.s.navigate(url)
            if history:      # addresses the browser has visited before: a link to one is announced `visited`. The page is loaded again so that its links are styled by them.
                self.s.add_history(history); self.s.reload()
        self.b = None; self.world = None; self.focus_ix = None; self._scrolled = False
        boot.click_hook = self._click_cb
        self.refresh()
        self.b._hadFirstGainFocus = True
        globalVars.focusObject = self.root_obj; globalVars.focusAncestors = []; globalVars.focusDifferenceLevel = 0   # focus starts on the document
        import api; api.setNavigatorObject(self.root_obj, isFocus=True)      # NVDA starts with the navigator object on the focus

    def refresh(self):
        nodes, focus_ix = self.s.dump()
        root = standin.build_platform_tree(nodes)
        self.world = objlayer.World(root); self.world.focus_cb = self._focus_cb; self.world.action_cb = self._action_cb; self.world.scroll_cb = self._scroll_cb; self.world.sel = self.s.sel; self.focus_ix = focus_ix; L.world = self.world
        def _fcd(binding, hwnd, uid, what, idRef, offRef, _w=self.world):
            r = objlayer.find_content_descendant(_w, _w.facade(_w.by_ix[uid]), what)
            if r is None: return 0
            standin._set(idRef, r[0]); standin._set(offRef, r[1]); return 0
        L.nvdaInProcUtils_IA2Text_findContentDescendant = _fcd
        import IAccessibleHandler
        # AccessibleObjectFromEvent(window, OBJID_CLIENT, uniqueID) -> (IAccessible, childID): Chromium resolves a unique ID as childID
        def _aofe(window, objectID, childID, _w=self.world):
            pn = _w.by_ix.get(childID)
            return (_w.facade(pn), 0) if pn is not None else None
        IAccessibleHandler.accessibleObjectFromEvent = _aofe
        L.register_tree((HWND, root.ix), nodes)
        h = L.VBuf_createBuffer(None, HWND, root.ix, 'gecko_ia2')
        vh = L.VBufRemote_bufferHandle_t(); vh.value = h
        first = self.b is None
        carried = [] if first else L.buffers[self.b._h].selection_identifiers()      # the fields the caret is in, to find again in the new buffer
        if first:
            self.b = driver.EmuBuffer.__new__(driver.EmuBuffer)
            self.b.__init__(vh, root.raw.get('url'), root.raw.get('name'))
        sel = (0, 0) if first else L.buffers[self.b._h].sel
        self.b.VBufHandle = vh; self.b._h = h; L.buffers[h].sel = sel
        L.buffers[h].correct_selection(carried)      # storage.cpp:742-760: the caret goes to the deepest field it was in that is still there, not to the number it had
        self.root_obj = self.obj(root.ix)
        self.b.rootNVDAObject = self.root_obj; self.b.rootDocHandle = HWND; self.b.rootID = root.ix
        treeInterceptorHandler.runningTable.add(self.b)
        self.b._emuLive = self
        return nodes

    def obj(self, ix):
        pn = self.world.by_ix[ix]
        o = NI.IAccessible(windowHandle=HWND, IAccessibleObject=self.world.facade(pn), IAccessibleChildID=0, event_windowHandle=HWND, event_objectID=-4, event_childID=ix)
        return o      # its tree interceptor is found the way NVDA finds it: ChromeVBuf.__contains__ (an object inside role=application is NOT in the buffer)

    def set_focus(self, obj):
        """api.setFocusObject (api.py), reduced to the part that decides the ancestors NVDA will report: the focus line is the new object's
        container chain, joined to the old line where they meet, and focusDifferenceLevel is the index at which the new part starts."""
        old = list(globalVars.focusAncestors) + ([globalVars.focusObject] if globalVars.focusObject else [])
        ancestors, tmp, level = [], obj, 0
        while tmp:
            hit = next((i for i in range(len(old) - 1, -1, -1) if tmp == old[i]), None)
            if hit is not None:
                orig = old[:hit + 1]
                if ancestors and orig: ancestors[0].container = orig[-1]
                ancestors = orig + ancestors; level = hit + 1
                break
            ancestors.insert(0, tmp)
            c = tmp.container; tmp.container = c; tmp = c
        del ancestors[-1]
        globalVars.focusAncestors = ancestors; globalVars.focusDifferenceLevel = level; globalVars.focusObject = obj
        import api, config      # eventHandler.doPreGainFocus: the navigator object follows the focus when the review cursor is set to
        if config.conf['reviewCursor']['followFocus']: api.setNavigatorObject(obj, isFocus=True)

    def gain_focus(self):
        obj = self.obj(self.focus_ix)
        self.set_focus(obj)
        self.b.event_gainFocus(obj, lambda: obj.event_gainFocus())

    def place_caret(self, text_marker):
        for s, e, t in driver.lines(self.b):
            if text_marker in t: driver.set_caret(self.b, s); return
        raise RuntimeError('marker not found')

    def press(self, key):
        i = len(driver.SPY.sequences)
        browser_keys = {'tab': ('Tab', 0), 'shift+tab': ('Tab', 8), 'enter': ('Enter', 0), 'space': ('Space', 0)}
        if key in ('tab', 'shift+tab', 'enter', 'space') and not self.b.passThrough: self.browse_mode_script_key(key)
        elif key in browser_keys and not self.b.passThrough or key in ('tab', 'shift+tab'):
            name, mods = browser_keys[key]; self.s.key(name, mods); self.refresh(); self.gain_focus()
        elif key in browser_keys:        # focus mode: the key goes to the page
            name, mods = browser_keys[key]; self.s.key(name, mods); self.settle()
        elif key in ARROWS and self.b.passThrough: self.focus_mode_arrow(key)
        else:
            r = driver.press(self.b, key)
            if self._scrolled: self._scrolled = False; self.refresh_in_place()      # the browser scrolled for NVDA (IA2 scrollTo): the offscreen states and the actions that depend on them change
            return r
        driver._flush(); return driver.SPY.text_since(i)

    def _focus_sig(self):
        """What identifies the focused node across two reads of the tree (node indexes are renumbered at every read, and the API exposes no
        node id): role, name, tag."""
        n = self.world.by_ix.get(self.focus_ix)
        return (n.role, n.raw.get('name'), n.raw.get('htmlTag')) if n is not None else None

    def settle(self, moves_focus=False, acted=False):
        """Read the tree after an input and deliver what Chromium would have raised, in its order: a focus event if the focus moved (it did when
        the input was a focus request, or when the focused node is no longer the same one), then, if the input performed an action, a
        state-change event on each node that may have changed, which NVDAObject.event_stateChange speaks for the focus and its ancestors
        as the difference from what was last spoken."""
        old = globalVars.focusObject; before = self._focus_sig()
        self.refresh()
        moved = moves_focus or self._focus_sig() != before
        if moved: self.gain_focus()
        if acted or not moved:
            for o in [globalVars.focusObject] + list(globalVars.focusAncestors):
                try: ix = o.IAccessibleObject.pn.ix
                except AttributeError: continue
                if not moved:
                    o.IAccessibleObject = self.world.facade(self.world.by_ix[ix]); o._treeInterceptor = weakref.ref(self.b) if o is old else getattr(o, '_treeInterceptor', None)
                o.invalidateCache(); o.event_stateChange()

    def refresh_in_place(self):
        """Re-read the tree when nothing but the page's scroll position moved: the focus chain keeps its nodes (same indexes), pointed at the new tree."""
        self.refresh()
        for o in [globalVars.focusObject] + list(globalVars.focusAncestors):
            try: ix = o.IAccessibleObject.pn.ix
            except AttributeError: continue
            if ix in self.world.by_ix: o.IAccessibleObject = self.world.facade(self.world.by_ix[ix]); o.invalidateCache()

    def _click_cb(self, x, y):
        # node locations are screen coordinates; the browser takes viewport coordinates: subtract the top web area's origin (measured: 10, 153 in this window)
        loc = self.world.root.raw.get('location') or {}
        self._focus_requested = True; self._acted = True; self.s.click(x - loc.get('left', 0), y - loc.get('top', 0))

    scroll_browser = True      # False: NVDA's scrollIntoView (IA2 scrollTo) is not delivered to the browser; the Q3 sweeps do that to run in seconds, not minutes

    _pending_scroll = None      # the node NVDA last asked the browser to scroll into view while scroll_browser was off, by its uid: an index names a node of one read of the tree only

    def _scroll_cb(self, ix):
        if not self.scroll_browser: self._pending_scroll = self.world.by_ix[ix].uid; return
        self.s.scroll(ix); self._scrolled = True

    SCROLL_SETTLE = 1.5      # seconds: a page's handlers for the scroll run before the tree is read again (ICO's listener is rate-limited to 500 ms)

    def deliver_pending_scroll(self):
        """Scroll the browser to where NVDA's caret last asked it to (IA2 scrollTo), once, and read the tree again. With scroll_browser off a key does not scroll,
        so this is the one scroll that puts the page where the fleet's sits when its read-through ends and the sweeps begin. Returns whether the page was scrolled:
        not when there was no request, or the node it named is no longer in the tree."""
        uid, self._pending_scroll = self._pending_scroll, None
        node = next((pn for pn in self.world.by_ix.values() if uid is not None and pn.uid == uid), None)
        if node is None: return False
        self.s.scroll(node.ix); time.sleep(self.SCROLL_SETTLE); self.refresh_in_place()
        return True

    def _action_cb(self, ix):
        self._focus_requested = True; self._acted = True; self.s.action(ix)

    def _focus_cb(self, ix):
        self._focus_requested = True; self._focus_moved = True; self.s.focus(ix)

    def browse_mode_script_key(self, key):
        """Tab, Enter and Space in browse mode are NVDA's own scripts (script_tab, script_activatePosition...): _tabOverride finds the next focusable node from the virtual caret
        and focuses it (obj.setFocus -> accSelect -> the browser), or else the key is sent on (gesture.send) to the browser. Either way the
        tree is re-read and the focus event NVDA would have received is delivered."""
        import scriptHandler
        name, mods = {'tab': ('Tab', 0), 'shift+tab': ('Tab', 8), 'enter': ('Enter', 0), 'space': ('Space', 0)}[key]
        g = driver.Gesture(key); self._focus_requested = False; self._focus_moved = False; self._acted = False
        def send(_=None): self.s.key(name, mods); self._focus_requested = True; self._focus_moved = key in ('tab', 'shift+tab')
        g.send = send
        sc = scriptHandler._getObjScript(self.b, g, [])
        if sc is None: send(); sc = lambda _g: None
        sc(g)
        if self._focus_requested: self.settle(moves_focus=self._focus_moved, acted=self._acted)

    def focus_mode_arrow(self, key):
        """An arrow key in focus mode goes to the page: NVDA's own EditableText script on the focused object runs, calls gesture.send()
        (here: the key goes to Chrome and the tree is re-read, the focused object pointed at the new tree's node), and then compares
        the caret before and after and speaks it with NVDA's own caret-moved helper."""
        name, mods = ARROWS[key]; obj = globalVars.focusObject
        g = driver.Gesture(key)
        def send(_=None):
            self.s.key(name, mods); self.refresh(); self.repoint(obj)
        g.send = send
        sc = obj.getScript(g)
        if sc is None: raise NotImplementedError(f'no object script for {key} on {type(obj).__mro__[:3]}')
        sc(g)

    def repoint(self, obj):
        """The focused NVDAObject keeps its identity across a refresh; its IAccessible is the new tree's facade for the same node."""
        ix = obj.event_childID; obj.IAccessibleObject = self.world.facade(self.world.by_ix[ix])
        obj._treeInterceptor = weakref.ref(self.b)

    def close(self): self.s.close()
