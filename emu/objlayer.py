"""Layer 5 groundwork (spike #5661): an IAccessible2 facade over the stand-in's platform nodes, so NVDA's REAL NVDAObjects.IAccessible classes
(the Chrome overlay: ia2Web, chromium) can be instantiated on Linux. Everything the facade answers comes from standin.PN (layer 2)."""
import json, types, collections, ctypes
import boot, standin
import IAccessibleHandler  # NVDA imports this before NVDAObjects.IAccessible (circular otherwise)
from standin import CONST, T

HWND = 0x1000
COMErr = boot.COMError

def _esc(s): return ''.join('\\' + c if c in '\\:;,=' else c for c in str(s))

class Facade(boot._IAccessible2_2, boot.IUnknown):
    """What Chromium's AXPlatformNodeWin answers over IAccessible / IAccessible2, as comtypes would present it."""
    def __init__(self, pn, world): self.pn = pn; self.world = world
    # --- IAccessible (childID is always 0: Chromium exposes no simple children)
    def accName(self, c=0): return self.pn.name()
    def accValue(self, c=0): return self.pn.value() or None
    def accDescription(self, c=0): return self.pn.description()
    def accKeyboardShortcut(self, c=0): return self.pn.keyboard_shortcut()
    def accRole(self, c=0): return CONST[T['msaa'].get(self.pn.role, 'ROLE_SYSTEM_CLIENT')]
    def accState(self, c=0): return self.pn.msaa_state()
    @property
    def accChildCount(self): return len(self.pn.pkids)
    def accChild(self, c):
        # IAccessible2 unique ID -> object (Chromium resolves a unique ID passed as childID); an unknown id is E_INVALIDARG
        if c == 0: return self
        pn = self.world.by_ix.get(c)
        if pn is None: raise COMErr(-2147024809)
        return self.world.facade(pn)
    @property
    def accParent(self): return self.world.facade(self.pn.parent) if self.pn.parent else None
    def accLocation(self, c=0):
        l = self.pn.raw.get('location') or {}
        return (l.get('left', 0), l.get('top', 0), l.get('width', 0), l.get('height', 0))
    def __eq__(self, o): return isinstance(o, Facade) and o.pn.ix == self.pn.ix
    def __hash__(self): return hash(self.pn.ix)
    def relationTargetsOfType(self, rtype, maxRelations=1):
        # IAccessible2_2::relationTargetsOfType. Forward targets are read from the automation node where it has them (labelledBy) and from the
        # reverse list on the target otherwise (an error message node lists the nodes it is the error message for: `errorMessageFor`).
        ids = self.world.relations(self.pn, str(getattr(rtype, 'value', rtype)))
        fs = [self.world.facade(self.world.by_ix[i]) for i in ids if i in self.world.by_ix][:maxRelations]
        return (fs, len(fs))

    def children_for_enum(self, start, count): return [self.world.facade(k) for k in self.pn.pkids[start:start + count]]
    def accNavigate(self, direction, c=0):
        # oleacc NAVDIR_*: NEXT 5, PREVIOUS 6, FIRSTCHILD 7, LASTCHILD 8 (Chromium answers these over its platform tree)
        pn = self.pn; par = pn.parent; sib = par.pkids if par else []
        tgt = None
        if direction == 5 and pn in sib and sib.index(pn) + 1 < len(sib): tgt = sib[sib.index(pn) + 1]
        elif direction == 6 and pn in sib and sib.index(pn) > 0: tgt = sib[sib.index(pn) - 1]
        elif direction == 7 and pn.pkids: tgt = pn.pkids[0]
        elif direction == 8 and pn.pkids: tgt = pn.pkids[-1]
        if tgt is None: return None
        return self.world.facade(tgt)
    @property
    def accSelection(self): return None
    def accDefaultAction(self, c=0): return self.pn.raw.get('defaultActionVerb') or None
    def accDoDefaultAction(self, c=0): raise NotImplementedError('actions are driven through the browser session')
    # --- IAccessible2
    def role(self): return self.pn.ia2_role()
    @property
    def states(self): return self.pn.ia2_state()
    @property
    def uniqueID(self): return self.pn.ix
    @property
    def windowHandle(self): return HWND
    @property
    def attributes(self): return ''.join(f'{_esc(k)}:{_esc(v)};' for k, v in self.pn.ia2_attrs().items())
    @property
    def locale(self): return types.SimpleNamespace(language=self.pn.raw.get('language', 'en'), country='', variant='')
    @property
    def indexInParent(self):
        p = self.pn.parent
        return p.pkids.index(self.pn) if p else -1
    @property
    def groupPosition(self): return (self.pn.raw.get('hierarchicalLevel') or 0, self.pn.raw.get('setSize') or 0, self.pn.raw.get('posInSet') or 0)
    @property
    def nRelations(self): return 0
    SUPPORTED = ('_IAccessible', '_IAccessible2', '_IAccessible2_2', 'IAccessible', 'IAccessible2', 'IAccessible2_2', 'IServiceProvider', '_IAccessibleText', 'IAccessibleText')
    def QueryInterface(self, iface):
        name = getattr(iface, '__name__', str(iface)).rsplit('.', 1)[-1]
        if name in ('_IAccessibleText', 'IAccessibleText'): return TextFacade(self)
        if name == 'IAccessibleHypertext': return HypertextFacade(self)
        if name == 'IAccessibleHyperlink' and self.pn.parent is not None:
            hl = HypertextFacade(self.world.facade(self.pn.parent)); offs, kids = hl._embeds()
            if self.pn in kids: return HyperlinkFacade(self, offs[kids.index(self.pn)])
            raise COMErr()
        if name == 'IAccessibleTable2' and self.pn.role in standin.Builder.TABLE_ROLES: return TableFacade(self)
        if name == 'IAccessibleAction': return ActionFacade(self)      # BrowserAccessibilityComWin::get_nActions / get_name / doAction (browser_accessibility_com_win.cc:725-915)
        if name in self.SUPPORTED: return self
        raise COMErr()      # e.g. IAccIdentity: Chromium does not implement it
    def QueryService(self, *a): raise COMErr()      # Chromium answers E_NOINTERFACE for IHTMLElement and friends
    def scrollTo(self, *a):
        if getattr(self.world, 'scroll_cb', None): self.world.scroll_cb(self.pn.ix)
    def accSelect(self, flags, child=0):
        # SELFLAG_TAKEFOCUS (1): the browser session focuses the node (NVDAObjects.IAccessible.IAccessible.setFocus); the harness reads the new focus afterwards
        if flags & 1 and getattr(self.world, 'focus_cb', None): self.world.focus_cb(self.pn.ix)


class ActionFacade:
    """IAccessibleAction of one node: the one action is the node's default action verb ("click", "press", "clickAncestor"...); doAction asks the browser to perform it."""
    def __init__(self, f): self.f = f
    def _names(self):
        v = self.f.pn.raw.get('defaultActionVerb'); return [v] if v and v != 'none' else []
    def nActions(self): return len(self._names())
    def name(self, i):
        n = self._names()
        if not 0 <= i < len(n): raise COMErr(-2147024809)
        return n[i]
    def doAction(self, i):
        if not 0 <= i < len(self._names()): raise COMErr(-2147024809)
        if getattr(self.f.world, 'action_cb', None): self.f.world.action_cb(self.f.pn.ix)


class TextFacade(boot._IAccessibleText):
    """The IAccessibleText interface of one node. It is a separate object from the node's IAccessible2 because comtypes gives each
    interface its own members, and `attributes` means a string on IAccessible2 and a method on IAccessibleText."""
    def __init__(self, f): self.f = f
    def accLocation(self, *a): return self.f.accLocation(*a)
    # --- IAccessibleText over the node's hypertext (ax_platform_node_base.cc UpdateComputedHypertext). Boundaries come from the offsets
    # chrome.automation exposes (lineStartOffsets, wordStarts/Ends, sentenceStarts/Ends); they are exact only for a node whose hypertext
    # is its own text (an atomic text field or a text leaf). A container with embedded objects needs the children's offsets: NOT PORTED.
    @property
    def nCharacters(self): return len(self.f.pn.hypertext())
    def text(self, start, end):
        t = self.f.pn.hypertext(); return t[start:(len(t) if end < 0 else end)]
    @property
    def caretOffset(self):
        r = self.f.pn.raw
        if r.get('textSelStart') is not None and self.f.pn.state.get('focused'): return r['textSelStart']
        sel = getattr(self.f.world, 'sel', None)      # a richly editable root: the caret is the tree selection's focus (rootWebArea.focusObject/Offset)
        if sel and sel.get('focusIx', -1) >= 0 and self.f.pn.state.get('editable'):
            leaf = self.f.world.by_ix.get(sel['focusIx'])
            o = self.f.pn.offset_of(leaf, sel['focusOffset']) if leaf is not None else None
            if o is not None: return o
        return 0      # AXPlatformNodeWin::get_caretOffset (ax_platform_node_win.cc:4459): no visible caret or selection here -> *offset = 0 and S_FALSE, which NVDA reads as 0
    @property
    def nSelections(self):
        r = self.f.pn.raw; return 1 if r.get('textSelStart') is not None and r.get('textSelEnd') != r.get('textSelStart') else 0
    @property
    def selection(self):
        r = self.f.pn.raw; return [(min(r['textSelStart'], r['textSelEnd']), max(r['textSelStart'], r['textSelEnd']))]
    def setCaretOffset(self, o): pass
    def addSelection(self, *a): pass
    def removeSelection(self, *a): pass
    def characterExtents(self, offset, coord): return self.accLocation()
    def offsetAtPoint(self, x, y, coord): return 0
    def attributes(self, offset): return (0, self.nCharacters, '')
    def textAtOffset(self, offset, boundary):
        import os
        if os.environ.get('EMU_TRACE'): print('textAtOffset', self.f.pn.role, repr(self.f.pn.hypertext())[:60], offset, boundary, self.f.pn.raw.get('lineStartOffsets'), file=__import__('sys').stderr)
        t = self.f.pn.hypertext(); n = len(t); r = self.f.pn.raw
        if offset < 0 or offset > n: raise COMErr(-2147024809)
        if boundary == 0: return (offset, offset + 1, t[offset:offset + 1])
        if boundary == 5 or boundary == 3: return (0, n, t)
        starts = {4: self.f.pn.boundary_starts('line'), 1: self.f.pn.boundary_starts('word'), 2: r.get('sentenceStarts')}[boundary] or [0]
        s = max([x for x in starts if x <= offset] or [0]); e = min([x for x in starts if x > offset] or [n])
        return (s, e, t[s:e])
    TextAtOffset = textAtOffset
    SetCaretOffset = setCaretOffset
    Selection = selection
    NSelections = nSelections
    AddSelection = addSelection
    RemoveSelection = removeSelection
    OffsetAtPoint = offsetAtPoint
    NCharacters = nCharacters

    def QueryInterface(self, iface): return self.f.QueryInterface(iface)



class HypertextFacade:
    """IAccessibleHypertext of one node: its embedded objects, by character offset (ax_platform_node_base.cc UpdateComputedHypertext)."""
    def __init__(self, f): self.f = f
    def _embeds(self):
        pn = self.f.pn; text = pn.hypertext(); kids = [k for k in pn.pkids if not k.is_text]
        return [i for i, c in enumerate(text) if c == standin.EMBED], kids
    @property
    def nHyperlinks(self): return len(self._embeds()[1])
    def hyperlinkIndex(self, offset):
        offs, _ = self._embeds(); return offs.index(offset) if offset in offs else -1
    def hyperlink(self, i):
        offs, kids = self._embeds()
        if not (0 <= i < len(kids)): raise COMErr(-2147024809)
        return HyperlinkFacade(self.f.world.facade(kids[i]), offs[i])
    def QueryInterface(self, iface): return self.f.QueryInterface(iface)


class HyperlinkFacade:
    """IAccessibleHyperlink of an embedded object: where it sits in its parent's hypertext."""
    def __init__(self, f, start): self.f = f; self.startIndex = start; self.endIndex = start + 1
    def QueryInterface(self, iface):
        name = getattr(iface, '__name__', str(iface)).rsplit('.', 1)[-1]
        return self if name in ('IAccessibleHyperlink',) else self.f.QueryInterface(iface)


def find_content_descendant(world, f, what):
    """nvdaHelper/remote/IA2Support.cpp findContentDescendant (229-312): the deepest object holding the first/caret/last/selection
    character, found by walking the hypertext into embedded objects. what: 0 first, 1 caret, 2 last, 3 selection start, 4 selection end."""
    t = f.QueryInterface(boot._IAccessibleText) if True else None
    n = t.nCharacters
    if what == 0: offset = 0
    elif what == 1: offset = t.caretOffset
    elif what == 2: offset = n - 1 if n > 0 else 0
    else:
        if t.nSelections == 0: offset = -1
        else:
            s0, e0 = t.selection[0]; offset = s0 if what == 3 else e0 - 1
    if offset == -1: return None
    ht = HypertextFacade(f); hi = ht.hyperlinkIndex(offset)
    if hi >= 0:
        child = ht.hyperlink(hi).f
        r = find_content_descendant(world, child, what)
        if r is None and what == 1: r = find_content_descendant(world, child, 0)
        if r is not None: return r
    return (f.pn.ix, offset)


class TableFacade:
    """IAccessibleTable2 of one table node (what NVDA's _getTableCellAt calls): the cell covering a physical coordinate."""
    def __init__(self, f): self.f = f
    def QueryInterface(self, iface): return self.f.QueryInterface(iface)
    @property
    def nRows(self): return self.f.pn.raw.get('tableRowCount') or 0
    @property
    def nColumns(self): return self.f.pn.raw.get('tableColumnCount') or 0
    def cellAt(self, row, col):
        def walk(pn):
            for k in pn.kids:
                r = k.raw
                if k.role in standin.Builder.CELL_ROLES and r.get('tableCellRowIndex') is not None:
                    r0, c0 = r['tableCellRowIndex'], r['tableCellColumnIndex']
                    if r0 <= row < r0 + (r.get('tableCellRowSpan') or 1) and c0 <= col < c0 + (r.get('tableCellColumnSpan') or 1): return k
                if k.role not in standin.Builder.CELL_ROLES:
                    hit = walk(k)
                    if hit is not None: return hit
        hit = walk(self.f.pn)
        if hit is None: raise COMErr(-2147024809)
        return self.f.world.facade(hit)


class World:
    def __init__(self, root_pn):
        self.root = root_pn; self.by_ix = {}; self._f = {}; self._index(root_pn)
    def _index(self, pn):
        self.by_ix[pn.ix] = pn
        for k in pn.kids: self._index(k)
    FORWARD = {'labelledBy': 'labelledByIx', 'describedBy': 'describedByIx', 'details': 'detailsIx', 'error': 'errorMessageIx', 'controllerFor': 'controlsIx'}
    REVERSE = {'details': 'detailsForIx', 'error': 'errorMessageForIx', 'labelledBy': 'labelForIx', 'describedBy': 'descriptionForIx'}
    def reverse_relation(self, key):
        """The nodes that name each node in their own `key` list, in the order of `by_ix`, each once: made once for the tree (`by_ix` does not change after it is indexed), as standin.Builder does (A11-229)."""
        held = self.__dict__.setdefault('_reverse', {})
        if key not in held:
            found = {}
            for n in self.by_ix.values():
                for target in dict.fromkeys(n.raw.get(key) or []): found.setdefault(target, []).append(n.ix)
            held[key] = found
        return held[key]

    def relations(self, pn, rtype):
        f = pn.raw.get(self.FORWARD.get(rtype, '')) or []
        if f: return [i for i in f if i >= 0]
        r = self.REVERSE.get(rtype)
        return list(self.reverse_relation(r).get(pn.ix, ())) if r else []
    def facade(self, pn):
        if pn.ix not in self._f: self._f[pn.ix] = Facade(pn, self)
        return self._f[pn.ix]
