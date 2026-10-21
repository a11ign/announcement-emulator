"""Stage 2 stand-in for NVDAHelper.localLib (the 13 VBuf_* calls) for the announcement-emulator spike (#5661).

Layer 2 (Windows mapping): chrome.automation node -> what Chromium's AXPlatformNodeWin hands NVDA over IAccessible/IAccessible2.
    Role / state tables are GENERATED from Chromium 155.0.8059.84 ax_platform_node_win.cc (gen_tables.py); the rules for
    leaf, hypertext, value and state are ported from the same file / ax_node.cc / ax_platform_node_base.cc, with the C++ line
    each came from in the comment.
Layer 3 (buffer builder): a port of NVDA's nvdaHelper/vbufBackends/gecko_ia2/gecko_ia2.cpp fillVBuf and
    nvdaHelper/vbufBase/storage.cpp (markup, offsets, line offsets), at release-2026.1.1.

# NOT PORTED (each is marked where it would go): tables (table-*), aria details / error message, image maps, hyperlink
# `makeHyperlinkGetter` index quirks, text attributes (IAccessibleText::attributes: bold, lang runs...), selection
# updates, incremental re-render (reuse / invalidation), the renderSelectedItemOnly list/tree path, locale on text nodes.
"""
import ctypes, json, pathlib, re

HERE = pathlib.Path(__file__).parent
T = json.loads((HERE / 'tables.json').read_text())
CONST = {**T['ole'], **T['ia2_role'], **T['ia2_state']}
XML_ROLES = {'article': 'article', 'figure': 'figure', 'region': 'region', 'switch': 'switch', 'main': 'main', 'navigation': 'navigation',
             'header': 'banner', 'footer': 'contentinfo',      # Q3 (a11y-worker oracle, 2026-10-20): NVDA says "banner landmark" and "content info landmark" for a page-level <header> and <footer> with no role attribute, which chrome.automation reports as 'header' and 'footer'; a nested <header> is 'sectionHeader'. Inferred from the dev split's fleet transcripts, not read in Chromium's source.
             'banner': 'banner', 'treeGrid': 'treegrid', 'gridCell': 'gridcell', 'complementary': 'complementary', 'contentInfo': 'contentinfo', 'form': 'form', 'search': 'search'}
EMBED = '￼'
EMPTY_TEXT = ' '

# ---------------------------------------------------------------- layer 2: Windows mapping


class PN:
    """A platform node: one chrome.automation node as the Windows platform layer would expose it."""

    def __init__(self, raw, parent):
        self.raw, self.parent, self.kids = raw, parent, []
        self.role = raw['role']
        self.ix = raw['ix']

    def __repr__(self): return f'<PN {self.role} {self.raw.get("name", "")!r}>'

    # -- ax_node.cc AXNode::IsText / IsLeaf (ported)
    @property
    def is_text(self):
        # AXNode::IsText: a list marker is text unless it still has non-ignored descendants (ax_node.cc)
        if self.role == 'listMarker': return not [k for k in self.kids if k.role != 'inlineTextBox']
        return self.role in ('inlineTextBox', 'lineBreak', 'staticText')

    @property
    def state(self): return self.raw.get('state', {})

    @property
    def atomic_text_field(self):
        return self.role in ('textField', 'searchBox', 'textFieldWithComboBox', 'spinButton') and not self.state.get('richlyEditable')

    @property
    def is_leaf(self):
        if not self.kids: return True
        if self.atomic_text_field or self.is_text: return True
        if self.role == 'textField' or self.state.get('richlyEditable'): return False
        if self.role == 'button': return False
        if self.role == 'image': return self.raw.get('htmlTag') != 'img'      # ax_node.cc:2449: a leaf when role="img"/"image" is the author's. chrome.automation does not expose the role attribute, so it is RECONSTRUCTED: an image that is not an <img> element is an ARIA image (an <img> with children is an image map, which is not a leaf)
        if self.role in ('docCover', 'graphicsSymbol', 'meter', 'scrollBar', 'spinButton', 'slider', 'splitter', 'progressIndicator'): return True
        if self.role in ('checkBox', 'listBoxOption', 'menuListOption', 'menuItem', 'menuItemCheckBox', 'menuItemRadio', 'popUpButton',
                         'toggleButton', 'radioButton', 'switch', 'tab'):
            real = [k for k in self.kids if k.role != 'inlineTextBox']
            if len(real) > 2 or self.state.get('editable'): return False
            return bool(real) and real[0].is_text and (len(real) < 2 or real[1].is_text)
        return False

    def non_atomic_text_field(self):
        """A richly editable root: editable, richly editable, and its parent is not itself editable (AXNodeData::IsNonAtomicTextField)."""
        return bool(self.state.get('richlyEditable') and self.state.get('editable') and not (self.parent and self.parent.state.get('editable')))

    @property
    def pkids(self):
        """Children as the platform layer exposes them: none below a leaf; inline text boxes are not exposed."""
        return [] if self.is_leaf else [k for k in self.kids if k.role != 'inlineTextBox']

    def text_content(self):  # AXNode::GetTextContentUTF16
        if self.is_text: return self.raw.get('name', '')
        if self.atomic_text_field: return self.raw.get('value', '')
        return ''.join(k.text_content() for k in self.kids if k.role != 'inlineTextBox')

    def boundary_starts(self, which):
        """Offsets in this node's hypertext at which a line (`lineStartOffsets`) or word (`wordStarts`) begins. A leaf uses the API's own
        offsets for its text; a container composes its children's: a text child contributes its offsets shifted to where it sits, and an
        embedded object is a boundary before and after itself when it is block-level (lines) or always (words). This is a model of what
        Chromium's IAccessibleText answers for a container, not a port: the content-layer code is not in the files read."""
        key = {'line': 'lineStartOffsets', 'word': 'wordStarts'}[which]
        if self.is_leaf: return sorted(set([0] + list(self.raw.get(key) or [])))
        starts, pos, prev = {0}, 0, None
        for k in self.pkids:
            if k.is_text:
                # a text child's own offset 0 starts a line only if it is not on the previous inline sibling's line (the dump drops
                # nextOnLine/previousOnLine, so the boxes' vertical extents stand in for them)
                same_line = which == 'line' and prev is not None and prev.on_line_with(k)
                starts.update(pos + x for x in (k.raw.get(key) or []) if not (same_line and x == 0))
                pos += len(k.text_content()); prev = k
            else:
                inline = (k.raw.get('display') or 'block') in ('inline', 'inline-block', 'inline-flex')
                block = which == 'word' or not inline
                if block: starts.add(pos); starts.add(pos + 1)
                prev = k if inline else None
                pos += 1
        return sorted(x for x in starts if x <= pos)

    def text_attrs(self):
        """IAccessibleText attributes of this text node: ComputeTextAttributes, ax_platform_node_base.cc:2516-2615, in its order, for the
        attributes the chrome.automation node carries (colour and background as rgb(), font family, font size in points rounded to 0.5,
        bold / italic / line-through / underline from the text style, language). `invalid` is added per marker range in text_attr_runs.
        NOT produced: auto-generated (kNotUserSelectableStyle) and writing-mode (text direction, not in the API)."""
        def rgb(c):
            c &= 0xFFFFFFFF
            return f'rgb({(c >> 16) & 255},{(c >> 8) & 255},{c & 255})'
        def sanitize(v): return v      # Chromium backslash-escapes ':;=,' for the IA2 string and NVDA's parser removes the escapes: the stored value is the plain one
        def num(f): return str(int(f)) if f == int(f) else str(f)
        a, r = {}, self.raw
        if r.get('backgroundColor'): a['background-color'] = sanitize(rgb(r['backgroundColor']))
        if r.get('color'): a['color'] = sanitize(rgb(r['color']))
        if r.get('fontFamily'): a['font-family'] = sanitize(r['fontFamily'])
        if r.get('fontSize') is not None: a['font-size'] = num(round(r['fontSize'] * 72.0 / 96.0 * 2.0) / 2.0) + 'pt'
        if r.get('bold'): a['font-weight'] = 'bold'
        if r.get('italic'): a['font-style'] = 'italic'
        if r.get('lineThrough'): a['text-line-through-style'] = 'solid'
        if r.get('underline'): a['text-underline-style'] = 'solid'
        if r.get('language'): a['language'] = sanitize(r['language'])
        return a

    def text_attr_runs(self):
        """[(start, end, attrs)] over this node's hypertext: one run per text child (split at spelling/grammar marker ranges, which the
        API exposes as `markers` and Windows presents as the `invalid` text attribute), one per embedded object; a leaf is one run."""
        def split(k, base):
            n = len(k.text_content()); marks = sorted((m['startOffset'], m['endOffset'], 'spelling' if m['flags'].get('spelling') else 'grammar')
                                                      for m in (k.raw.get('markers') or []) if m['flags'].get('spelling') or m['flags'].get('grammar'))
            out, pos = [], 0
            for (ms, me, kind) in marks:
                if ms > pos: out.append((base + pos, base + ms, k.text_attrs()))
                out.append((base + ms, base + me, {**k.text_attrs(), 'invalid': kind})); pos = me
            if pos < n or not out: out.append((base + pos, base + n, k.text_attrs()))
            return out
        if self.is_leaf:
            return split(self, 0) if self.is_text and self.text_content() else []
        runs, pos = [], 0
        for k in self.pkids:
            if k.is_text: runs.extend(split(k, pos)); pos += len(k.text_content())
            else: runs.append((pos, pos + 1, {})); pos += 1
        return runs

    def offset_of(self, leaf, off):
        """The offset in this node's hypertext of `off` characters into the text node `leaf` beneath it, or the offset of the embedded
        object holding it (what IAccessibleText::caretOffset answers for a container whose caret sits in a descendant); None if not below."""
        if leaf is self: return off
        pos = 0
        for k in self.pkids:
            if k is leaf or (leaf.parent is k and leaf.role == 'inlineTextBox'): return pos + off if k.is_text else pos
            if not k.is_text and k.contains(leaf): return pos
            pos += len(k.text_content()) if k.is_text else 1
        return None

    def on_line_with(self, other):
        a, b = self.raw.get('location'), other.raw.get('location')
        return bool(a and b and a['top'] < b['top'] + b['height'] and b['top'] < a['top'] + a['height'])

    def contains(self, other):
        while other is not None:
            if other is self: return True
            other = other.parent
        return False

    def hypertext(self):  # AXPlatformNodeBase::UpdateComputedHypertext
        if self.is_leaf: return self.text_content()
        return ''.join(k.text_content() if k.is_text else EMBED for k in self.pkids)

    # -- IAccessible::get_accName / get_accValue / get_accDescription
    def name(self):
        n = self.raw.get('name', '')
        return n if (n or self.raw.get('nameFrom') not in (None, 'none')) else None

    def value(self):  # GetValueAttributeAsBstr
        if self.role == 'rootWebArea': return self.raw.get('url', '')
        if self.role == 'link': return self.raw.get('url', '')
        return self.raw.get('value', '')

    def description(self):
        return self.raw.get('description') or None

    # -- roles
    def ia2_role(self):
        """IAccessible2::role: IA2 role if the platform node has one, else the MSAA role (ax_platform_node_win.cc:2107)."""
        r = self.role
        conditional = {'form': 'IA2_ROLE_FORM' if self.raw.get('name') else 'IA2_ROLE_SECTION'}
        c = conditional.get(r) or T['ia2'].get(r) or T['msaa'].get(r)
        if r in ('disclosureTriangle', 'disclosureTriangleGrouped'): c = T['msaa'].get(r)      # ax_platform_node_win.cc:7298: IA2_ROLE_HEADING only when features::IsAccessibilityExposeSummaryAsHeadingEnabled(); the fleet's Edge announces a <summary> as `button`, so the feature is off (the generated table took the guarded branch as unconditional)
        if r in ('embeddedObject', 'pluginObject'): c = 'IA2_ROLE_SECTION' if self.pkids else 'IA2_ROLE_EMBEDDED_OBJECT'      # ax_platform_node_win.cc:7363 / 7433: GetChildCount() ? SECTION : EMBEDDED_OBJECT (the generated table has neither)
        if r == 'canvas': c = 'IA2_ROLE_CANVAS' if self.pkids else T['msaa'].get(r)      # :7269: only a canvas with fallback content (kCanvasHasFallback; approximated by having children) is IA2_ROLE_CANVAS
        if r == 'image': c = 'IA2_ROLE_IMAGE_MAP' if self.pkids else T['msaa'].get(r)      # ax_platform_node_win.cc:7389: `if (IsImageWithMap())`; the generated table took the conditional branch for every image
        if r == 'row': c = 'ROLE_SYSTEM_ROW'      # the generated table missed it: kRow is a braced conditional case (ax_platform_node_win.cc:6999), outline item inside a treegrid below
        if c is None: return 0
        if r == 'row':      # ax_platform_node_win.cc:6999 / IsInTreeGrid: a row whose parent (or grandparent, past a row group) is a treegrid is an outline item
            par = self.parent
            if par is not None and par.role == 'rowGroup': par = par.parent
            if par is not None and par.role == 'treeGrid': c = 'ROLE_SYSTEM_OUTLINEITEM'
        return CONST[c]

    # -- states (MSAAState / ComputeIA2State)
    def msaa_state(self):
        s, r = self.state, self.role
        out = 0
        if s.get('collapsed'): out |= CONST['STATE_SYSTEM_COLLAPSED']
        if s.get('expanded'): out |= CONST['STATE_SYSTEM_EXPANDED']
        if s.get('focusable'): out |= CONST['STATE_SYSTEM_FOCUSABLE']
        if self.raw.get('hasPopup'): out |= CONST['STATE_SYSTEM_HASPOPUP']
        if s.get('invisible'): out |= CONST['STATE_SYSTEM_INVISIBLE']
        if s.get('linked'): out |= CONST['STATE_SYSTEM_LINKED']
        if s.get('multiselectable'): out |= CONST['STATE_SYSTEM_MULTISELECTABLE']
        if s.get('offscreen'): out |= CONST['STATE_SYSTEM_OFFSCREEN']
        if s.get('protected'): out |= CONST['STATE_SYSTEM_PROTECTED']
        if self.raw.get('selected'): out |= CONST['STATE_SYSTEM_SELECTED']
        if s.get('visited'): out |= CONST['STATE_SYSTEM_TRAVERSED']
        ch = self.raw.get('checked')
        if ch == 'true':
            out |= CONST['STATE_SYSTEM_CHECKED']
            if r in ('toggleButton', 'switch'): out |= CONST['STATE_SYSTEM_PRESSED']
        elif ch == 'mixed': out |= CONST['STATE_SYSTEM_MIXED']
        rs = self.raw.get('restriction')
        if rs == 'disabled': out |= CONST['STATE_SYSTEM_UNAVAILABLE']
        elif rs == 'readOnly': out |= CONST['STATE_SYSTEM_READONLY']
        elif r in ('article', 'definition', 'descriptionList', 'document', 'graphicsDocument', 'image', 'list', 'listItem', 'pdfRoot',
                   'progressIndicator', 'rootWebArea', 'term', 'timer', 'toolbar', 'tooltip') and not s.get('richlyEditable'):
            out |= CONST['STATE_SYSTEM_READONLY']  # ShouldHaveReadonlyStateByDefault
        if s.get('focused'): out |= CONST['STATE_SYSTEM_FOCUSED']
        return out

    def ia2_state(self):
        s, r = self.state, self.role
        out = CONST['IA2_STATE_OPAQUE']
        if self.raw.get('checked') is not None: out |= CONST['IA2_STATE_CHECKABLE']
        inv = self.raw.get('invalidState')
        if inv and inv != 'false': out |= CONST['IA2_STATE_INVALID_ENTRY']
        if s.get('required'): out |= CONST['IA2_STATE_REQUIRED']
        if s.get('vertical'): out |= CONST['IA2_STATE_VERTICAL']
        if s.get('horizontal'): out |= CONST['IA2_STATE_HORIZONTAL']
        if s.get('editable'): out |= CONST['IA2_STATE_EDITABLE']
        if r in ('textField', 'searchBox', 'textFieldWithComboBox') or self.non_atomic_text_field():      # AXNodeData::IsTextField
            out |= CONST['IA2_STATE_MULTI_LINE'] if s.get('multiline') else CONST['IA2_STATE_SINGLE_LINE']
            if not s.get('invisible'): out |= CONST['IA2_STATE_SELECTABLE_TEXT']
        if self.raw.get('autoComplete'): out |= CONST['IA2_STATE_SUPPORTS_AUTOCOMPLETION']
        if r in ('treeItem', 'listBoxOption') and s.get('focusable'): out &= ~CONST['IA2_STATE_EDITABLE']
        if r in ('menuListPopup', 'menuListOption'): out &= ~CONST['IA2_STATE_EDITABLE']
        return out

    def ia2_attrs(self):
        """ComputeAttributes in ax_platform_node_base.cc, for the attributes the chrome.automation node carries.
        NOT AVAILABLE from the API: xml-roles (author role string), and any attribute drawn from htmlAttributes."""
        a, raw = {}, self.raw
        # xml-roles is Chromium's kRole string (the role=... attribute; ax_platform_node_base.cc:1073). chrome.automation does NOT expose it
        # (measured, Q1), so it is RECONSTRUCTED from the automation role for the roles NVDA reads it for (gecko_ia2.py:180-200, 474-535).
        # This over-reports where an element has the role natively and Chromium sets no kRole, and cannot see a role that differs.
        xr = XML_ROLES.get(self.role)
        if xr: a['xml-roles'] = xr
        if self.role == 'layoutTable': a['layout-guess'] = 'true'      # ax_platform_node_base.cc:1342
        if raw.get('display'): a['display'] = raw['display']
        if raw.get('htmlTag'): a['tag'] = raw['htmlTag']
        if raw.get('placeholder'): a['placeholder'] = raw['placeholder']
        if raw.get('roleDescription'): a['roledescription'] = raw['roleDescription']
        if raw.get('hierarchicalLevel'): a['level'] = str(raw['hierarchicalLevel'])
        if raw.get('setSize'): a['setsize'] = str(raw['setSize'])
        if raw.get('posInSet'): a['posinset'] = str(raw['posInSet'])
        if raw.get('checked') is not None: a['checkable'] = 'true'
        if self.state.get('invisible'): a['hidden'] = 'true'
        if raw.get('ariaCurrentState') in ('false', 'true', 'page', 'step', 'location', 'date', 'time'): a['current'] = raw['ariaCurrentState']      # ax_platform_node_base.cc:1301
        if self.role == 'image' and raw.get('url'): a['src'] = raw['url']      # ax_platform_node_base.cc:1459: IsImage(role) && kUrl; gecko_ia2.cpp:1264 names an unlabelled graphic from it
        if self.role in ('cell', 'gridCell', 'columnHeader', 'rowHeader', 'layoutTableCell'):      # ax_platform_node_base.cc:1349: aria-rowindex / aria-colindex, exposed only where they differ from the physical position
            ar, pr, ac, pc = raw.get('tableCellAriaRowIndex'), raw.get('tableCellRowIndex'), raw.get('tableCellAriaColumnIndex'), raw.get('tableCellColumnIndex')
            if ar is not None and pr is not None and ar - 1 != pr: a['rowindex'] = str(ar)
            if ac is not None and pc is not None and ac - 1 != pc: a['colindex'] = str(ac)
        if raw.get('liveStatus'): a['live'] = raw['liveStatus']
        if raw.get('liveRelevant'): a['relevant'] = raw['liveRelevant']
        if raw.get('liveAtomic'): a['atomic'] = 'true'
        df = {'ariaDescription': 'aria-description', 'buttonLabel': 'button-label', 'prohibitedNameRepair': 'prohibited-name-repair',
              'relatedElement': 'aria-describedby', 'rubyAnnotation': 'ruby-annotation', 'summary': 'summary', 'svgDescElement': 'svg-desc-element',
              'tableCaption': 'table-caption', 'title': 'tooltip', 'popoverTarget': 'tooltip', 'interestFor': 'tooltip'}.get(raw.get('descriptionFrom'))
        if raw.get('descriptionFrom') == 'ariaDescription' and raw.get('description'): a['description'] = raw['description']
        if df: a['description-from'] = df
        nf = {'attribute': 'attribute', 'caption': 'caption', 'contents': 'contents', 'placeholder': 'placeholder', 'relatedElement': 'related-element',
              'title': 'tooltip', 'value': 'value'}.get(raw.get('nameFrom'))
        if nf: a['name-from'] = nf
        if nf and nf != 'contents': a['explicit-name'] = 'true'
        hp = raw.get('hasPopup')
        if hp and hp != 'false': a['haspopup'] = hp
        sd = raw.get('sortDirection')      # ax_platform_node_base.cc:1381: only on a column or row header
        if self.role in ('columnHeader', 'rowHeader') and sd in ('unsorted', 'ascending', 'descending', 'other'): a['sort'] = 'none' if sd == 'unsorted' else sd
        dr = self.details_roles()
        if dr: a['details-roles'] = dr
        return a

    DETAILS_ROLE = {'comment': 'comment', 'definition': 'definition', 'docEndnote': 'doc-endnote', 'docFootnote': 'doc-footnote'}
    _ix_map = {}      # set by build_platform_tree: every node of the tree by its index, for the relations that name nodes

    def details_roles(self):
        """ComputeDetailsRoles, ax_platform_node_base.cc:2706-2767: for each aria-details target, comment / definition / doc-endnote /
        doc-footnote by its role; a group or region holding a comment (within 4 levels, 8 children each) is a comment; a popup is
        `popover`; anything else `*`. A sorted set, space separated."""
        def has_comment(n, depth):
            if n.role == 'comment': return True
            return depth > 0 and any(has_comment(k, depth - 1) for k in n.kids[:8])
        out = set()
        for i in self.raw.get('detailsIx') or []:
            t = self._ix_map.get(i)
            if t is None: continue
            if t.role in self.DETAILS_ROLE: out.add(self.DETAILS_ROLE[t.role])
            elif t.role in ('group', 'region') and any(has_comment(k, 3) for k in t.kids[:8]): out.add('comment')
            elif t.raw.get('isPopup') or t.raw.get('popup'): out.add('popover')
            else: out.add('*')
        return ' '.join(sorted(out))


def build_platform_tree(flat):
    """Rebuild the tree from the extractor's depth-first (depth, node) list."""
    stack, root, everything = [], None, []
    for raw in flat:
        while stack and stack[-1].raw['depth'] >= raw['depth']: stack.pop()
        pn = PN(raw, stack[-1] if stack else None)
        if stack: stack[-1].kids.append(pn)
        else: root = pn
        stack.append(pn); everything.append(pn)
    idx = {p.raw['ix']: p for p in everything}
    for p in everything: p._ix_map = idx
    return root


# ---------------------------------------------------------------- layer 3: storage (nvdaHelper/vbufBase/storage.cpp)

def _xml_char(c, in_attr=False):
    """appendCharToXML (storage.cpp): the characters it escapes."""
    o = ord(c)
    if c == '<': return '&lt;'
    if c == '>': return '&gt;'
    if c == '&': return '&amp;'
    if c == '"' and in_attr: return '&quot;'
    if o < 0x20 and c not in '\t\n\r': return f'<unich value="{o}" />'
    if 0xd800 <= o <= 0xdfff: return f'<unich value="{o}" />'
    return c


def _xml(s, in_attr=False): return ''.join(_xml_char(c, in_attr) for c in s)


class Field:
    def __init__(self, is_block=False):
        self.parent = None; self.kids = []; self.is_block = is_block; self.is_hidden = False; self.attrs = {}

    @property
    def length(self): raise NotImplementedError

    def index(self):
        return self.parent.kids.index(self) if self.parent else 0

    def offset_in_tree(self):
        o = 0
        if self.parent:
            for k in self.parent.kids:
                if k is self: break
                o += k.length
            o += self.parent.offset_in_tree()
        return o


class TextField(Field):
    def __init__(self, text):
        super().__init__(False); self.text = text; self.attrs = {}

    @property
    def length(self): return len(self.text)

    def markup(self, s, e):  # VBufStorage_textFieldNode_t::getTextInRange with markup
        return f'<text {self._opening(s, e)}>{_xml(self.text[s:e])}</text>'

    def _opening(self, s, e):
        return _common(self, s, e) + ''.join(f'{_name(k)}="{_xml(v, True)}" ' for k, v in self.attrs.items())


class Control(Field):
    def __init__(self, doc_handle, ID, is_block=True):
        super().__init__(is_block); self.id = (doc_handle, ID)

    @property
    def length(self): return sum(k.length for k in self.kids)

    def markup(self, s, e):  # VBufStorage_fieldNode_t::getTextInRange with markup
        if self.length == 0: return ''
        out = [f'<control controlIdentifier_docHandle="{self.id[0]}" controlIdentifier_ID="{self.id[1]}" {_common(self, s, e)}'
               + f'_childcount="{len(self.kids)}" _childcontrolcount="{sum(1 for k in self.kids if k.length > 0 and k.kids)}" '
               + f'_indexInParent="{self.index()}" _parentChildCount="{len(self.parent.kids) if self.parent else 1}" '
               + ''.join(f'{_name(k)}="{_xml(v, True)}" ' for k, v in self.attrs.items()) + '>']
        cs = 0
        for k in self.kids:
            ce = cs + k.length
            if ce > s and e > cs: out.append(k.markup(max(s, cs) - cs, min(e - cs, k.length)))
            cs = ce
        out.append('</control>')
        return ''.join(out)


def _name(k): return re.sub(r'[^A-Za-z0-9_:.\-]', '_', k)


def _common(f, s, e):
    return (f'_startOfNode="{1 if s == 0 else 0}" _endOfNode="{1 if e >= f.length else 0}" _offsetFromStartOfNode="{s}" '
            f'_offsetFromEndOfNode="{max(0, f.length - e)}" isBlock="{int(f.is_block)}" isHidden="{int(f.is_hidden)}" ')


class Buffer:
    def __init__(self): self.root = None; self.by_id = {}; self.sel = (0, 0)

    def text(self, s, e, markup):
        if self.root is None or s >= e: return ''
        e = min(e, self.root.length)
        if markup: return self.root.markup(s, e)
        out, o = [], 0
        def walk(n, base):
            if isinstance(n, TextField): out.append((base, n.text)); return
            for k in n.kids: walk(k, base); base += k.length
        walk(self.root, 0)
        return ''.join(t for _, t in out)[s:e]

    def all_text(self): return self.text(0, self.root.length if self.root else 0, False)

    def text_node_at(self, offset):
        """locateTextFieldNodeAtOffset -> (node, start, end)"""
        def go(n, base, off):
            if isinstance(n, TextField): return n, base, base + n.length
            c = base
            for k in n.kids:
                if off < c - base + k.length: return go(k, c, off - (c - base))
                c += k.length
            return None
        r = go(self.root, 0, offset)
        return r

    def control_at(self, offset):
        n, s, e = self.text_node_at(offset) or (None, 0, 0)
        if n is None: return None
        p = n.parent
        while p is not None and not isinstance(p, Control): p = p.parent
        return p

    def line_offsets(self, offset, max_len, screen_layout):
        """VBufStorage_buffer_t::getLineOffsets (nvdaHelper/vbufBase/storage.cpp:1066-1198), line for line: search forward and backward from the text node at
        `offset` through the tree (control nodes included, so an empty block ends a line), collecting the places a line may be cut, then apply maxLineLength."""
        if self.root is None or offset >= self.root.length: return None
        r = self.text_node_at(offset)
        if r is None: return None
        init, init_s, init_e = r
        possible = set()
        limit = init.parent
        while limit is not None and not limit.is_block: limit = limit.parent
        is_break = lambda t, i: t[i] == '\n' or (t[i] == '\r' and (i + 1 >= len(t) or t[i + 1] != '\n'))
        # forward
        node, rel, bs, be = init, offset - init_s, init_s, init_e
        line_end, hard = init_e, False
        while True:
            possible.add(bs); possible.add(be)
            if node.length > 0 and not node.kids:
                text = node.text; line_end = be; last_space = False
                for i in range(rel, node.length):
                    if is_break(text, i): line_end = bs + i + 1; hard = True; break
                    if text[i].isspace(): last_space = True
                    else:
                        if last_space: possible.add(bs + i)
                        last_space = False
                if hard: break
            nxt, trel = next_in_tree(node, FORWARD, limit)
            if nxt is not None and ((not screen_layout and nxt.kids) or nxt.is_block): nxt = None
            if nxt is None: break
            bs += trel; be = bs + nxt.length; rel = 0; node = nxt
        # backward
        node, rel, bs, be = init, offset - init_s, init_s, init_e
        line_start, hard = init_s, False
        while True:
            possible.add(bs); possible.add(be)
            if node.length > 0 and not node.kids:
                text = node.text; line_start = bs; last_space = False
                for i in range(rel - 1, -1, -1):
                    if is_break(text, i): line_start = bs + i + 1; hard = True; break
                    if text[i].isspace():
                        if not last_space: possible.add(bs + i + 1)
                        last_space = True
                    else: last_space = False
                if hard: break
            nxt, trel = next_in_tree(node, SYMBACK, limit if screen_layout else node.parent)
            if nxt is not None and nxt.is_block: nxt = None
            if nxt is None: break
            bs += trel; be = bs + nxt.length; rel = nxt.length; node = nxt
        # finally take maxLineLength into account
        if max_len > 0:
            import bisect
            ordered = sorted(possible); real = {line_start, line_end}
            i, count = line_start, 0
            while i < line_end:
                if count == max_len:
                    if ordered:
                        pos = bisect.bisect_right(ordered, i)      # upper_bound
                        if pos > 0 and ordered[pos - 1] > i - max_len: i = ordered[pos - 1]
                    real.add(i); count = 0
                i += 1; count += 1
            rs = sorted(real); hi = bisect.bisect_right(rs, offset)
            line_end, line_start = rs[hi], rs[hi - 1]
        return line_start, line_end


def _crosses_control(a, b):
    """Not using screen layout, line search stops at a control field boundary (storage.cpp: `node->firstChild`)."""
    return a.parent is not b.parent


# ---------------------------------------------------------------- storage.cpp: nextNodeInTree / matchAttributes / findNodeByAttributes

FORWARD, BACK, UP, SYMBACK = 0, 1, 2, 3          # VBufStorage_findDirection_* (virtualBuffers/__init__.py)


def _prev(n): return n.parent.kids[n.parent.kids.index(n) - 1] if n.parent and n.parent.kids.index(n) > 0 else None
def _next(n): return n.parent.kids[n.parent.kids.index(n) + 1] if n.parent and n.parent.kids.index(n) + 1 < len(n.parent.kids) else None


def next_in_tree(node, direction, limit=None):
    """VBufStorage_fieldNode_t::nextNodeInTree (storage.cpp:57-117) -> (node, relativeStartOffset) or (None, 0)."""
    rel, t = 0, node
    if direction == FORWARD:
        if t.kids: t = t.kids[0]
        else:
            while t is not None and _next(t) is None:
                t = t.parent
                if t is limit: t = None
            if t is None or _next(t) is None: return None, 0
            rel = node.length; t = _next(t)
    elif direction == SYMBACK:      # TREEDIRECTION_SYMMETRICAL_BACK: the pre-order walked backwards, last child first
        if t.kids: t = t.kids[-1]; rel = node.length - t.length
        else:
            while t is not None and _prev(t) is None:
                t = t.parent
                if t is limit: t = None
            if t is None or _prev(t) is None: return None, 0
            t = _prev(t); rel -= t.length
    elif direction == BACK:
        p = _prev(t)
        if p is not None:
            if p is limit: return None, 0
            t = p
            while t.kids and t.kids[-1] is not limit: t = t.kids[-1]
            rel -= t.length
        elif t.parent is not None: t = t.parent
        else: return None, 0
    if t is limit: return None, 0
    return t, rel


def _esc(text, maxlen=0):
    out = []
    for i, c in enumerate(text):
        if c in ':;\\': out.append('\\')
        out.append(c)
        if maxlen and i + 1 == maxlen: break
    return ''.join(out)


def match_attributes(node, attribs, regexp):
    """VBufStorage_fieldNode_t::matchAttributes (storage.cpp:150-195): build 'name:value;' for each requested attribute, full-match."""
    s = []
    for a in attribs:
        s.append(_esc(a) + ':')
        src = node
        if a.startswith('parent::'):
            src, a = node.parent, a[len('parent::'):]
        v = (src.attrs.get(a) if src is not None else None)
        if v is not None: s.append(_esc(v, 100))
        s.append(';')
    try: return re.fullmatch(regexp, ''.join(s)) is not None
    except re.error: return False


def find_by_attributes(buf, offset, direction, attribs, regexp):
    """VBufStorage_buffer_t::findNodeByAttributes (storage.cpp:973-1060) -> (node, start, end) or None."""
    if buf.root is None or offset >= buf.root.length: return None
    if offset == -1: node, bs, be = buf.root, 0, buf.root.length
    else:
        r = buf.text_node_at(offset)
        if r is None: return None
        node, bs, be = r
    attribs = attribs.split()
    if direction == FORWARD:
        while True:
            node, rel = next_in_tree(node, FORWARD)
            if node is None: return None
            bs += rel; be = bs + node.length
            if node.length > 0 and not node.is_hidden and match_attributes(node, attribs, regexp): return node, bs, be
    if direction == BACK:
        skipped = False
        while True:
            node, rel = next_in_tree(node, BACK)
            if node is None: return None
            bs += rel; be = bs + node.length
            if node.length > 0 and not node.is_hidden and match_attributes(node, attribs, regexp):
                if bs == offset or (not skipped and bs < offset < be): skipped = True; continue
                return node, bs, be
    # UP
    while True:
        while _prev(node) is not None:
            node = _prev(node); bs -= node.length
        node = node.parent
        if node is None: return None
        be = bs + node.length
        if not node.is_hidden and match_attributes(node, attribs, regexp): return node, bs, be


# ---------------------------------------------------------------- layer 3: fillVBuf (gecko_ia2.cpp:526-1380)

class Builder:
    def __init__(self, root_pn, doc_handle=1):
        self.buf = Buffer(); self.root_pn = root_pn; self.doc_handle = doc_handle
        self.label_of = {}   # ix of labelled node -> ix of label node, from labelledBy / labelFor
        self.by_ix = {}
        self._index(root_pn)

    def _index(self, pn):
        self.by_ix[pn.ix] = pn
        for k in pn.kids: self._index(k)
        for a in pn.raw.get('labelledByIx', []): self.label_of[pn.ix] = a
        for t in pn.raw.get('labelForIx', []): self.label_of.setdefault(t, pn.ix)

    def build(self):
        node = self.fill(self.root_pn, None, None)
        self.buf.root = node
        return self.buf

    def add_control(self, parent, previous, pn):
        c = Control(self.doc_handle, pn.ix)
        c.parent = parent
        if parent is not None:
            if previous is None: parent.kids.insert(0, c)
            else: parent.kids.insert(parent.kids.index(previous) + 1, c)
        self.buf.by_id[c.id] = c
        return c

    @staticmethod
    def add_text(parent, previous, text):
        if not text: return None
        # VBufStorage_buffer_t::addTextFieldNode (storage.cpp:586-614, #2963): private-use characters (U+E000-U+F8FF, icon fonts) and U+200B are stripped from the
        # start and end of every text node; the count stripped from the start is kept for IA2Text offsets.
        priv = lambda ch: '\ue000' <= ch <= '\uf8ff' or ch == '\u200b'
        i = 0
        while i < len(text) and priv(text[i]): i += 1
        start = i
        j = 0
        while j < len(text) and priv(text[len(text) - 1 - j]): j += 1
        stripped = text[start:max(len(text) - j, start)] if (start or j) else text
        t = TextField(stripped); t.parent = parent
        if start: t.attrs['strippedCharsFromStart'] = str(start)
        if previous is None: parent.kids.insert(0, t)
        else: parent.kids.insert(parent.kids.index(previous) + 1, t)
        return t

    TABLE_ROLES = ('table', 'grid', 'treeGrid', 'layoutTable')
    CELL_ROLES = ('cell', 'gridCell', 'columnHeader', 'rowHeader', 'layoutTableCell')

    def fill(self, pn, parent, previous, table_pn=None, table_id=0, ign=False):
        C = CONST
        ID = pn.ix
        if (self.doc_handle, ID) in self.buf.by_id: return None            # loop guard
        node = self.add_control(parent, previous, pn)
        previous = None
        a = node.attrs
        for k, v in pn.ia2_attrs().items(): a[f'IAccessible2::attribute_{k}'] = v
        role = pn.ia2_role()
        if role == C['ROLE_SYSTEM_OUTLINE'] and 'treegrid' in a.get('IAccessible2::attribute_xml-roles', '').split():
            role = C['ROLE_SYSTEM_TABLE']      # gecko_ia2.cpp:604-610: an ARIA treegrid is forced from outline to table, early, so all the table logic applies
        a['IAccessible::role'] = str(role)
        states, ia2states = pn.msaa_state(), pn.ia2_state()
        for i in range(32):
            if states & (1 << i): a[f'IAccessible::state_{1 << i}'] = '1'
        for i in range(32):
            if ia2states & (1 << i): a[f'IAccessible2::state_{1 << i}'] = '1'
        a['keyboardShortcut'] = ''
        # block element? (gecko_ia2.cpp:660-698)
        disp = a.get('IAccessible2::attribute_display')
        if ia2states & C['IA2_STATE_MULTI_LINE']: block = True
        elif disp is not None: block = disp not in ('inline', 'inline-block', 'inline-flex')
        elif role in (C['ROLE_SYSTEM_TABLE'], C['ROLE_SYSTEM_CELL'], C['IA2_ROLE_SECTION'], C['ROLE_SYSTEM_DOCUMENT'],
                      C['IA2_ROLE_INTERNAL_FRAME'], C['IA2_ROLE_UNKNOWN'], C['ROLE_SYSTEM_SEPARATOR']): block = True
        else: block = False
        node.is_block = block
        name = pn.name()
        desc = pn.description()
        if desc is not None: a['description'] = desc
        is_editable = (role == C['ROLE_SYSTEM_TEXT'] and bool(states & (C['STATE_SYSTEM_FOCUSABLE'] | C['STATE_SYSTEM_UNAVAILABLE']))) or bool(ia2states & C['IA2_STATE_EDITABLE'])
        in_link = bool(states & C['STATE_SYSTEM_LINKED'])
        is_root = ID == self.root_pn.ix
        is_embedded_app = role == C['IA2_ROLE_EMBEDDED_OBJECT'] or (not is_root and role in (C['ROLE_SYSTEM_APPLICATION'], C['ROLE_SYSTEM_DIALOG']))
        never_inter = node.is_hidden or (not is_editable and (is_root or role in (C['ROLE_SYSTEM_DOCUMENT'], C['IA2_ROLE_INTERNAL_FRAME'])))
        # IAccessibleAction (BrowserAccessibilityComWin::get_name, ui/accessibility/platform/browser_accessibility_com_win.cc:850): action 0 is named by the
        # node's default action verb ("click", "press", "clickAncestor"...), and NVDA's `click` / `showlongdesc` make the node interactive and CLICKABLE.
        verb = pn.raw.get('defaultActionVerb')
        action_names = [verb] if verb and verb != 'none' else []
        for i, an in enumerate(action_names): a[f'IAccessibleAction_{an}'] = str(i)
        has_action = (not never_inter) and any(an in ('click', 'showlongdesc') for an in action_names)
        interactive = not never_inter and (is_editable or in_link or bool(states & (C['STATE_SYSTEM_FOCUSABLE'] | C['STATE_SYSTEM_UNAVAILABLE'])) or is_embedded_app or role == C['ROLE_SYSTEM_EQUATION'] or has_action)
        # (IAccessibleAction: Chromium implements no IAccessibleAction, so no `IAccessibleAction_*` attributes and no click-interactive.)
        hidden_aria = False  # aria-hidden: such nodes are not in the platform tree, so never reached here
        name_explicit = a.get('IAccessible2::attribute_explicit-name') == 'true'
        label_visible_cached = self._label_visible(pn)
        name_is_content = (is_embedded_app or role in (C['ROLE_SYSTEM_LINK'], C['ROLE_SYSTEM_PUSHBUTTON'], C['IA2_ROLE_TOGGLE_BUTTON'], C['ROLE_SYSTEM_MENUITEM'])
                           or (role == C['ROLE_SYSTEM_GRAPHIC'] and not pn.pkids) or (role == C['ROLE_SYSTEM_TEXT'] and not is_editable)
                           or role in (C['IA2_ROLE_HEADING'], C['ROLE_SYSTEM_PAGETAB'], C['ROLE_SYSTEM_BUTTONMENU'])
                           or (role in (C['ROLE_SYSTEM_CHECKBUTTON'], C['ROLE_SYSTEM_RADIOBUTTON']) and not label_visible_cached))
        label_visible = bool(name_explicit and name and (not name_is_content or role == C['ROLE_SYSTEM_TABLE']) and label_visible_cached)
        if name_explicit and not name_is_content and role != C['ROLE_SYSTEM_TABLE'] and not label_visible:
            a['alwaysReportName'] = 'true'
        text = pn.hypertext()
        unneeded_space = bool(text) and not is_editable and all(c not in ('\n', EMBED) and c.isspace() for c in text)
        if not text or is_editable: unneeded_space = False
        render_children = True
        if unneeded_space or role == C['ROLE_SYSTEM_COMBOBOX'] or is_embedded_app or role == C['ROLE_SYSTEM_EQUATION'] or (name_is_content and name_explicit):
            render_children = False
        # NOT PORTED: renderSelectedItemOnly for ROLE_SYSTEM_LIST (non-readonly) and ROLE_SYSTEM_OUTLINE
        # NOT PORTED: table information (IAccessibleTable2 / TableCell), presentational row/column attributes
        # presentational table attributes (gecko_ia2.cpp:984-1002): what the page says (aria-rowindex, aria-colindex, aria-rowcount, aria-colcount) where Chromium
        # exposes it, i.e. where it differs from the physical position; NVDA reports these and navigates by the physical table-rownumber and table-columnnumber.
        # (The row-level propagation of table-rownumber-presentational to cells is not ported; the cell carries its own.)
        for ia2, buf_attr in (('rowindex', 'table-rownumber-presentational'), ('colindex', 'table-columnnumber-presentational'),
                              ('rowcount', 'table-rowcount-presentational'), ('colcount', 'table-columncount-presentational')):
            v = a.get(f'IAccessible2::attribute_{ia2}')
            if v is not None: node.attrs[buf_attr] = v
        # --- table cell and table information (gecko_ia2.cpp:906-1005); physical coordinates only
        raw = pn.raw
        if pn.role in self.CELL_ROLES and raw.get('tableCellRowIndex') is not None:
            a['table-rownumber'] = str(raw['tableCellRowIndex'] + 1); a['table-columnnumber'] = str(raw['tableCellColumnIndex'] + 1)
            if (raw.get('tableCellColumnSpan') or 1) > 1: a['table-columnsspanned'] = str(raw['tableCellColumnSpan'])
            if (raw.get('tableCellRowSpan') or 1) > 1: a['table-rowsspanned'] = str(raw['tableCellRowSpan'])
            for key, attr in (('tableCellColumnHeadersIx', 'table-columnheadercells'), ('tableCellRowHeadersIx', 'table-rowheadercells')):
                hs = ''.join(f'{self.doc_handle},{i};' for i in (raw.get(key) or []) if i in self.by_ix)
                if hs: a[attr] = hs
            tid = table_id
            if not tid:
                anc = pn.parent
                while anc is not None and anc.role not in self.TABLE_ROLES: anc = anc.parent
                tid = anc.ix if anc is not None else 0
            a['table-id'] = str(tid)
            table_pn, table_id = None, 0           # inside a cell, descendants do not refer to the table any more
        if table_pn is None and pn.role in self.TABLE_ROLES:
            a['table-id'] = str(ID)
            if 'IAccessible2::attribute_layout-guess' in a: a['table-layout'] = '1'
            rows, cols = raw.get('tableRowCount'), raw.get('tableColumnCount')
            if rows is not None: a['table-rowcount'] = str(rows)
            if cols is not None: a['table-columncount'] = str(cols)
            if (rows or 0) > 0 or (cols or 0) > 0: table_pn, table_id = pn, ID
            summary = desc if desc else (name if name and not label_visible else None)
            if summary:
                t = self.add_text(node, previous, summary)
                if t: previous = t
        value = pn.value()
        if role == C['ROLE_SYSTEM_LINK'] and value is not None: a['IAccessible::value'] = value
        if not value: value = None
        if interactive and not ign: ign = name is not None      # gecko_ia2.cpp:1034: an interactive node with a name makes the unlabelled graphics under it uninteresting
        if text and render_children:
            # The loop of gecko_ia2.cpp:1067-1150: a chunk ends at the end of the text, at the end of an attribute run, or at an embedded
            # object character; each chunk carries its run's text attributes.
            runs = pn.text_attr_runs()
            def run_at(k):
                for (rs, re_, ra) in runs:
                    if rs <= k < re_: return re_, ra
                return len(text), {}
            kids = iter(pn.pkids)
            chunk_start = 0; attribs_end = 0; attribs = {}
            i = 0
            while True:
                if i != chunk_start and (i == len(text) or i == attribs_end or text[i] == EMBED):
                    t = self.add_text(node, previous, text[chunk_start:i])
                    if t:
                        previous = t
                        t.attrs['ia2TextStartOffset'] = str(chunk_start); t.attrs['ia2TextWindowHandle'] = str(self.doc_handle); t.attrs['ia2TextUniqueID'] = str(ID)
                        for ak, av in attribs.items(): t.attrs[ak] = av
                        if 'IAccessible2::attribute_text-align' in a: t.attrs['text-align'] = a['IAccessible2::attribute_text-align']
                if i == len(text): break
                if i == attribs_end:
                    chunk_start = i
                    attribs_end, attribs = run_at(i)
                if text[i] == EMBED:
                    chunk_start = i + 1
                    child = next((k for k in kids if not k.is_text), None)
                    if child is not None:
                        sub = self.fill(child, node, previous, table_pn, table_id, ign)
                        if sub is not None:
                            previous = sub
                            sub.attrs['ia2TextStartOffset'] = str(i); sub.attrs['ia2TextWindowHandle'] = str(self.doc_handle); sub.attrs['ia2TextUniqueID'] = str(ID)
                i += 1
        elif role == C['ROLE_SYSTEM_GRAPHIC']:      # gecko_ia2.cpp:1248
            if name:
                previous = self.add_text(node, previous, name)
            elif name == '' or ign:
                interactive = False
            elif interactive:
                if in_link and value: previous = self.add_text(node, previous, _name_for_url(value))
                elif 'IAccessible2::attribute_src' in a: previous = self.add_text(node, previous, _name_for_url(a['IAccessible2::attribute_src']))
        elif not name_is_content and value is not None:
            previous = self.add_text(node, previous, value)
        if not is_editable and (name_is_content or role in (C['IA2_ROLE_SECTION'], C['IA2_ROLE_TEXT_FRAME'])) and not self._useful_content(node):
            if name is not None: self.add_text(node, None, name)
            elif role == C['ROLE_SYSTEM_LINK'] and value: self.add_text(node, None, _name_for_url(value))
        if role in (C['ROLE_SYSTEM_CELL'], C['ROLE_SYSTEM_ROWHEADER'], C['ROLE_SYSTEM_COLUMNHEADER'], C['IA2_ROLE_UNKNOWN']) and node.length == 0:
            previous = self.add_text(node, previous, EMPTY_TEXT); node.is_block = False
        if (interactive or role == C['ROLE_SYSTEM_SEPARATOR'] or (name and len(name) > 0) or (desc)) and node.length == 0:
            previous = self.add_text(node, previous, EMPTY_TEXT)
        if not name_is_content and name is not None:
            a['name'] = name
            if name_explicit:
                lab = self.label_of.get(ID)
                if lab is not None:
                    lnode = self.buf.by_id.get((self.doc_handle, lab))
                    if lnode is not None and _is_descendant(node, lnode): a['labelledByContent'] = 'true'
        if desc and self._content_matches(node, desc): a['descriptionIsContent'] = 'true'
        self._aria_details(pn, node, a['IAccessible::role'])
        self._aria_error(pn, node)
        return node

    # --- relations, from the automation node's own lists; the reverse list is used when the forward one is absent
    FORWARD = {'details': 'detailsIx', 'error': 'errorMessageIx'}
    REVERSE = {'details': 'detailsForIx', 'error': 'errorMessageForIx', 'detailsFor': 'detailsIx', 'errorFor': 'errorMessageIx'}
    def _relation_ids(self, pn, rtype):
        f = pn.raw.get(self.FORWARD.get(rtype, '')) or []
        if f: return [i for i in f if i >= 0]
        r = self.REVERSE.get(rtype)
        return [n.ix for n in self.by_ix.values() if r and pn.ix in (n.raw.get(r) or [])] if r else []

    def _aria_details(self, pn, node, role_attr):
        """GeckoVBufBackend_t::fillVBufAriaDetails (gecko_ia2.cpp:452-500): detailsRoles / hasDetails, looked for in both directions."""
        def extend(n, role):
            n.attrs['detailsRoles'] = (n.attrs['detailsRoles'] + ',' + role) if 'detailsRoles' in n.attrs else role
        targets = self._relation_ids(pn, 'details')
        if targets:
            node.attrs['hasDetails'] = 'true'
            for t in targets:
                tn = self.buf.by_id.get((self.doc_handle, t))
                if tn is not None: extend(node, tn.attrs.get('role', 'unknown'))
        for o in self._relation_ids(pn, 'detailsFor'):
            on = self.buf.by_id.get((self.doc_handle, o))
            if on is not None: extend(on, role_attr)

    def _aria_error(self, pn, node):
        """GeckoVBufBackend_t::fillVBufAriaError (gecko_ia2.cpp:503-525): the first aria-errormessage target's text."""
        t = self._relation_ids(pn, 'error')
        if t and t[0] in self.by_ix:
            node.attrs['errorMessage'] = self.by_ix[t[0]].text_content() or self.by_ix[t[0]].raw.get('name', '')

    def _label_visible(self, pn):
        """getLabelInfo: the control is labelled by a node that is itself in the rendered tree (not hidden)."""
        lab = self.label_of.get(pn.ix)
        return lab is not None and lab in self.by_ix and not self.by_ix[lab].state.get('invisible')

    @staticmethod
    def _useful_content(node):
        """nodeHasUsefulContent (nvdaHelper/vbufBase/utils.cpp:148): false for an empty node, true for more than three characters, otherwise true if any of
        them is neither white space nor a private-use character."""
        def text(n):
            if isinstance(n, TextField): return n.text
            return ''.join(text(k) for k in n.kids)
        content = text(node)
        if len(content) == 0: return False
        if len(content) > 3: return True
        return any(not c.isspace() and not ('\ue000' <= c <= '\uf8ff' or c == '\u200b') for c in content)

    @staticmethod
    def _content_matches(node, s):
        def collect(n): return n.text if isinstance(n, TextField) else ''.join(collect(k) for k in n.kids)
        return collect(node) == s


def _is_descendant(parent, d):
    while d is not None:
        if d is parent: return True
        d = d.parent
    return False


def _name_for_url(url):
    """getNameForURL, nvdaHelper/vbufBase/utils.cpp:21 (a size_t that steps below zero is npos there, None here)."""
    if not url: return url
    colon = url.find(':')
    if colon != -1 and url[colon:colon + 3] != '://':
        if url[:11].lower() == 'data:image/': return ''
        return url[colon + 1:]
    q, a = url.rfind('?'), url.rfind('#')
    qlen = a - q - 1 if a != -1 and q != -1 else None
    strip = True
    path_end = q if q != -1 else (a if a != -1 else len(url))
    path_end = path_end - 1 if path_end >= 1 else None
    if path_end is not None and url[path_end] == '/':
        path_end = path_end - 1 if path_end >= 1 else None; strip = False
    start = 0
    if path_end is not None:
        start = url.rfind('/', 0, path_end + 1)
        if start == -1: start = 0
        else:
            start += 1
            if strip and start == (colon + 3 if colon != -1 else 2): strip = False
        if strip:
            e = url.rfind('.', 0, path_end + 1)
            if e != -1 and e > start: path_end = e - 1
    name = url[start:path_end + 1] if path_end is not None else ''
    if q != -1: name += ' ' + (url[q + 1:] if qlen is None or qlen < 0 else url[q + 1:q + 1 + qlen])
    if a != -1: name += ' ' + url[a + 1:]
    return name[:30] + '\u2026' if len(name) > 30 else name


# ---------------------------------------------------------------- nvdaHelper/local/textUtils.cpp (word / character offsets)
# The control flow below is a line-by-line port of _calculateUniscribeOffsets. The one thing that is NOT NVDA's is `_log_attr`:
# on Windows it is Uniscribe's ScriptBreak (an OS text service); here it is an approximation of Unicode word/grapheme stops.
# Every word-unit result therefore depends on that approximation, and is reported as Windows-OS-dependent when it differs.
import unicodedata

def _log_attr(text):
    n = len(text); char_stop = [False] * n; word_stop = [False] * n
    for i, c in enumerate(text):
        char_stop[i] = i == 0 or not (unicodedata.combining(c) or '\udc00' <= c <= '\udfff')
    def wc(i): return text[i].isalnum() or text[i] == '_'
    for i in range(n):
        if i == 0: word_stop[i] = True; continue
        if wc(i) and not wc(i - 1):
            # MidLetter / MidNum: an apostrophe or full stop between two word characters does not start a new word
            if i >= 2 and text[i - 1] in "'\u2019.:" and wc(i - 2): continue
            word_stop[i] = True
        elif not wc(i) and not text[i].isspace() and (text[i - 1].isspace()): word_stop[i] = False
    return char_stop, word_stop


def _calc_offsets(unit, text, length, offset):
    if offset < 0 or text is None: return None
    if offset >= length: return offset, offset + 1
    cs, ws = _log_attr(text[:length])
    if unit == 'char':
        start = next(i for i in range(offset, -1, -1) if cs[i]) if any(cs[:offset + 1]) else 0
        end = next((i for i in range(offset + 1, length) if cs[i]), length)
        return start, end
    start = next((i for i in range(offset, -1, -1) if ws[i]), 0)
    skip_ws = True
    for i in range(offset, start - 1, -1):
        if text[i].isspace():
            if skip_ws: continue
            start = i + 1; break
        else: skip_ws = False
    end = next((i for i in range(offset + 1, length) if ws[i]), length)
    i = offset
    while i < end:
        if text[i].isspace():
            while i < end and text[i].isspace(): i += 1
            end = i; break
        i += 1
    return start, end


# ---------------------------------------------------------------- the localLib surface NVDA calls (virtualBuffers/__init__.py)

class _Handle(ctypes.c_ulonglong): pass


class LocalLib:
    """Python stand-in for the 13 VBuf_* natives. Handles are indices into `buffers`."""
    VBufRemote_bufferHandle_t = _Handle

    def __init__(self): self.buffers = {}; self._n = 100; self.trees = {}

    def register_tree(self, key, flat): self.trees[key] = flat

    def VBuf_createBuffer(self, binding, docHandle, ID, backend):
        root = build_platform_tree(self.trees[(docHandle, ID)] if (docHandle, ID) in self.trees else next(iter(self.trees.values())))
        self._n += 1
        self.buffers[self._n] = Builder(root, docHandle).build()
        return self._n

    def _b(self, h): return self.buffers[h.value if hasattr(h, 'value') else h]

    def VBuf_destroyBuffer(self, ref): pass
    def VBuf_getTextLength(self, h): return self._b(h).root.length if self._b(h).root else 0
    def VBuf_getTextInRange(self, h, s, e, markup): return self._b(h).text(s, e, bool(markup))

    def VBuf_getLineOffsets(self, h, offset, maxLen, screen, startRef, endRef):
        r = self._b(h).line_offsets(offset, maxLen, bool(screen))
        if r is None: return False
        _set(startRef, r[0]); _set(endRef, r[1]); return True

    def VBuf_getSelectionOffsets(self, h, sRef, eRef):
        s, e = self._b(h).sel; _set(sRef, s); _set(eRef, e)

    def VBuf_setSelectionOffsets(self, h, s, e): self._b(h).sel = (s, e)

    def VBuf_getFieldNodeOffsets(self, h, node, sRef, eRef):
        n = node.value if hasattr(node, 'value') else node
        c = self._b(h).by_id_ref[n]
        s = c.offset_in_tree(); _set(sRef, s); _set(eRef, s + c.length); return True

    def VBuf_locateControlFieldNodeAtOffset(self, h, offset, sRef, eRef, docRef, idRef, nodeRef):
        b = self._b(h); c = b.control_at(offset)
        if c is None: return False
        s = c.offset_in_tree(); _set(sRef, s); _set(eRef, s + c.length); _set(docRef, c.id[0]); _set(idRef, c.id[1]); _set(nodeRef, _ref(b, c)); return True

    def VBuf_locateTextFieldNodeAtOffset(self, h, offset, sRef, eRef, nodeRef):
        b = self._b(h); r = b.text_node_at(offset)
        if r is None: return False
        n, s, e = r; _set(sRef, s); _set(eRef, e); _set(nodeRef, _ref(b, n)); return True

    def VBuf_getControlFieldNodeWithIdentifier(self, h, doc, ID, nodeRef):
        b = self._b(h); c = b.by_id.get((doc, ID))
        _set(nodeRef, _ref(b, c) if c else 0); return bool(c)

    def VBuf_getIdentifierFromControlFieldNode(self, h, node, docRef, idRef):
        b = self._b(h); n = node.value if hasattr(node, 'value') else node
        c = b.by_id_ref[n]; _set(docRef, c.id[0]); _set(idRef, c.id[1])

    def calculateWordOffsets(self, text, length, offset, sRef, eRef):
        r = _calc_offsets('word', text, length, offset)
        if r is None: return False
        _set(sRef, r[0]); _set(eRef, r[1]); return True

    def calculateCharacterOffsets(self, text, length, offset, sRef, eRef):
        r = _calc_offsets('char', text, length, offset)
        if r is None: return False
        _set(sRef, r[0]); _set(eRef, r[1]); return True

    def nvdaInProcUtils_IA2Text_findContentDescendant(self, binding, hwnd, uid, what, idRef, offRef):
        # Simplification: the object is its own content descendant (right for atomic text fields, wrong for rich contenteditable)
        _set(idRef, uid); _set(offRef, 0)

    def nvdaInProcUtils_getTextFromIAccessible(self, binding, hwnd, uid, ref, recurse, include_top):
        # Approximation of nvdaHelper/remote's getTextFromIAccessible: the text content of the node, else its name
        pn = self.world.by_ix.get(uid) if getattr(self, 'world', None) else None
        if pn is None: return 1
        ref._obj.value = pn.text_content() or pn.raw.get('name', '') or ''
        return 0

    def VBuf_findNodeByAttributes(self, h, offset, direction, attribs, regexp, sRef, eRef, nodeRef):
        b = self._b(h); r = find_by_attributes(b, offset, direction, attribs, regexp)
        if r is None: _set(nodeRef, 0); return False
        n, s, e = r; _set(sRef, s); _set(eRef, e); _set(nodeRef, _ref(b, n)); return True


def _set(ref, v):
    obj = getattr(ref, '_obj', ref)
    obj.value = v


def _ref(b, node):
    if not hasattr(b, 'by_id_ref'): b.by_id_ref = {}
    k = id(node) & 0xffffffff
    b.by_id_ref[k] = node
    return k
