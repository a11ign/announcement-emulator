"""A tree source for a platform where chrome.automation gives the extension no desktop tree (macOS: A11-208 found `getDesktop` never answers there).

The browser's DevTools port says what the renderer's accessibility tree holds (`Accessibility.getFullAXTree`), and what the page's elements are (`DOMSnapshot.captureSnapshot`): this puts the two
together into the node list that `emu/ext2/tree.js` makes from chrome.automation, so that the rest of the runtime (`predict.py`, and the emulator under it) does not know which it was given.

It is the lower-fidelity source ADR 0047 allows, and it is not the same tree. What the DevTools protocol does not say is worked out here from what it does:
  * the roles are exact (`chromeRole` is Chromium's own number, roles.json names it; the two numbers Chromium 156 adds that matter are named in ADDED_ROLES);
  * a text's line starts are those of its inline text boxes, which Chromium makes one for each line; its word and sentence starts are found with a regular expression and not with ICU's rules;
  * the table model (where a cell is, what it spans, `aria-rowindex` / `aria-colindex`, its header cells), the position in a set and the size of one are worked out from the tree and the page's attributes by Chromium's own rules
    (AXTableInfo; AXTree::ComputeSetSizePosInSet, AXNode::GetOrderedSet), and not read from the AXNode that Chromium holds. A11-229 held each to the companion extension's tree for the same pages (fixtures/structure);
  * the default action verb is Chromium's `AXObject::Action`: a page's own click listener (DOMSnapshot's `isClickable` less what the browser does itself, and, for a <label>, the console's `getEventListeners`) makes a node `click`;
  * `visited`, `default`, `offscreen` beyond the viewport, the document's text selection and the node's `nameFrom` beyond the first source are not known, or are guessed (each is marked below).
Not forced, because the protocol does not give it (A11-229, listed with the units it costs in the write-up): ICU's word and sentence starts; the names of the parts inside a date or time field (the protocol computes "Day Day" where the extension has
"Day When"); the value of a colour field and the file field's "No file chosen"; ARIA radio buttons outside a radio group (Chromium groups them); the `relevant` a live region has by default; a label's listener in a frame; and, for a node with no
action at all, the extension's `none` where this says `clickAncestor` (a listener on the document is not one DOMSnapshot sees, and neither is spoken).
The write-up measures what that costs (docs/playwright-middleware-spike.md, Q2).
"""
import json, os, re
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = {int(k): v for k, v in json.load(open(os.path.join(HERE, 'roles.json'))).items()}      # Chromium's Role enum: number -> chrome.automation's name
# Roles that Chromium 156 numbers beyond roles.json (made from 155's ax_enums.mojom), as the companion extension names them for the same elements in Playwright 1.64.1's Chromium (156.0.8078.4): a native <select> and a grid cell.
# A number is taken for the role only where the protocol's own name for the node is the one it had there, so that a build that numbers something else 209 or 212 is not misread.
ADDED_ROLES = {(209, 'combobox'): 'comboBoxSelect', (212, 'gridcell'): 'gridCell'}


def is_offscreen(bounds, viewport):
    """Whether a box (DOMSnapshot's, in page coordinates) lies wholly outside the viewport the page is scrolled to."""
    return bool(bounds and viewport and (bounds[1] + bounds[3] < 0 or bounds[1] > viewport.get('pageY', 0) + viewport.get('clientHeight', 1e9) or bounds[0] + bounds[2] < 0 or bounds[0] > viewport.get('pageX', 0) + viewport.get('clientWidth', 1e9)))


def role_of(ax):
    """chrome.automation's name for the role of a DevTools AX node: its `chromeRole` number in roles.json, else one of ADDED_ROLES, else `unknown`."""
    number = (ax.get('chromeRole') or {}).get('value')
    return ROLES.get(number) or ADDED_ROLES.get((number, (ax.get('role') or {}).get('value')), 'unknown')

STYLES = ['display', 'color', 'background-color', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration-line', 'visibility']
# What is asked of the page in the same moment as the two trees: where it is, how loaded, and the caret of the field that has the focus.
PAGE_JS = """JSON.stringify((() => { const a = document.activeElement, text = a && /^(INPUT|TEXTAREA)$/.test(a.tagName); let s = null; try { s = text ? [a.selectionStart, a.selectionEnd] : null; } catch (e) {} \
return {url: location.href, title: document.title, readyState: document.readyState, lang: document.documentElement.lang || '', caret: s}; })())"""


def frame_ids(tree):
    """The ids of the frames below the main one in a `Page.getFrameTree` answer, each before the ones it holds."""
    out = []
    def collect(t):
        for child in t.get('childFrames', []): out.append(child['frame']['id']); collect(child)
    collect(tree['frameTree'])
    return out


def prefix_frames(frames):
    """The nodes of each frame's tree with their ids made their own by a prefix (a frame's node ids are numbered from the start, as the main tree's are): {id: node}, and the root of each frame's tree."""
    nodes, roots = {}, {}
    for frame, frame_nodes in (frames or {}).items():
        for n in frame_nodes:
            renamed = dict(n, nodeId=f'{frame}:{n["nodeId"]}', childIds=[f'{frame}:{c}' for c in n.get('childIds', [])])
            if 'parentId' in n: renamed['parentId'] = f'{frame}:{n["parentId"]}'
            else: roots[frame] = renamed
            nodes[renamed['nodeId']] = renamed
    return nodes, roots


def fetch(call_many):
    """What a conversion needs from one page. `call_many([(method, params), ...])` sends DevTools commands of that page together and answers with their results in order: the AX tree, the DOM, the viewport
    and the page's own state are read in one round trip (the browser answers them in the order sent)."""
    ax, dom, metrics, evaluated, frames, labels = call_many([
        ('Accessibility.getFullAXTree', {}),
        ('DOMSnapshot.captureSnapshot', {'computedStyles': STYLES}),      # without includeDOMRects: the rects it adds (offset, client, scroll) are read by nothing here, and cost a third of the call
        ('Page.getLayoutMetrics', {}),
        ('Runtime.evaluate', {'expression': PAGE_JS, 'returnByValue': True}),
        ('Page.getFrameTree', {}),
        ('Runtime.evaluate', {'expression': LABELS_JS, 'returnByValue': True, 'includeCommandLineAPI': True}),
    ])
    children = frame_ids(frames)
    inner = call_many([('Accessibility.getFullAXTree', {'frameId': f}) for f in children]) if children else []
    if 'value' not in evaluated.get('result', {}): raise ValueError('the page has no state to read (it is closing)')
    return {'ax': ax['nodes'], 'dom': dom, 'viewport': metrics.get('cssVisualViewport') or metrics.get('visualViewport'), 'page': json.loads(evaluated['result']['value']), 'frames': {f: r['nodes'] for f, r in zip(children, inner)},
            'listeners': label_listeners(labels, dom)}      # a page that is gone has no value: KeyError, which the caller takes as one read lost


# DOMSnapshot says an element is clickable when a script listens for a click on it and also when the browser itself acts on a click there: a link, a form control, a <label>. Chromium's accessibility tree
# counts only the first as a click handler (`AXObject::Action` gives a plain <label> no verb), so for the tags below the flag says nothing about the page's own listeners.
NATIVE_CLICK_TAGS = {'a', 'area', 'label', 'input', 'button', 'summary', 'select', 'textarea', 'option'}
# Asked of the page in the same round trip as the trees, with the console's own `getEventListeners`: for each <label> of the document, in document order, whether the page listens for a click on it.
LABELS_JS = """JSON.stringify([...document.querySelectorAll('label')].map(label => { const on = getEventListeners(label); return ['click', 'mousedown', 'mouseup', 'DOMActivate'].some(type => (on[type] || []).length) ? 1 : 0; }))"""


def label_listeners(answer, snapshot):
    """The backend ids of the <label> elements of the page's main document that carry a click listener of the page's own. A label is the one native element whose "clickable" is spoken (it has no role verb to hide it),
    and DOMSnapshot cannot tell the page's listener from the label's own behaviour. `answer` is the result of LABELS_JS, which sees the main document's labels outside any shadow root: they are matched to the snapshot's by
    their order, and by nothing if the two do not count the same (a page that changed between the two questions)."""
    try: asked = json.loads(answer['result']['value'])
    except (KeyError, TypeError, ValueError): return []
    if not asked or not snapshot['documents']: return []
    strings = snapshot['strings']; nodes = snapshot['documents'][0]['nodes']; parents = nodes['parentIndex']
    in_shadow = {i for i, kind in zip(nodes.get('shadowRootType', {}).get('index', []), nodes.get('shadowRootType', {}).get('value', [])) if kind >= 0}
    def shadowed(i):
        while i >= 0:
            if i in in_shadow: return True
            i = parents[i]
        return False
    labels = [nodes['backendNodeId'][i] for i in range(len(parents)) if (strings[nodes['nodeName'][i]] or '').lower() == 'label' and not shadowed(i)]
    return [backend for backend, listens in zip(labels, asked) if listens] if len(labels) == len(asked) else []


# ------------------------------------------------------------------------------------------------ the page's elements

class Dom:
    """The elements of a DOMSnapshot by backendNodeId: tag, attributes, computed style and the box."""
    def __init__(self, snapshot, listeners=()):
        strings = snapshot['strings']; table = strings + [None]; s = table.__getitem__      # a string by its number; -1, which the snapshot gives for none, is the last of the table
        listeners = set(listeners)
        self.by_backend = {}; self.frame_of_owner = {}      # frame_of_owner: the backend id of an iframe element -> the id of the frame it holds
        self.elements = []      # the backend ids of the main document's elements in document order, as the page's `querySelectorAll('*')` lists them: not the pseudo-elements, and none in a shadow tree (the numbers cdp.py's probe gives)
        self.shadowed = False      # whether the page has a shadow tree (the numbers above do not hold for it)
        for number, doc in enumerate(snapshot['documents']):
            nodes = doc['nodes']
            lang = s(doc.get('contentLanguage', -1))
            layout = {}
            for row, node in enumerate(doc['layout']['nodeIndex']): layout[node] = row
            clickable = set(nodes.get('isClickable', {}).get('index', []))
            contents = dict(zip(nodes.get('contentDocumentIndex', {}).get('index', []), nodes.get('contentDocumentIndex', {}).get('value', [])))
            backends, parents, names, kinds, attributes = nodes['backendNodeId'], nodes['parentIndex'], nodes['nodeName'], nodes['nodeType'], nodes['attributes']; base = s(doc.get('baseURL'))
            for i, backend in enumerate(backends):
                attrs = attributes[i]; parent = parents[i]
                tag = (s(names[i]) or '').lower()
                info = {'backend': backend, 'tag': tag, 'type': kinds[i], 'attrs': dict(zip(map(s, attrs[0::2]), map(s, attrs[1::2]))) if attrs else {}, 'parent': parent,
                        'up': backends[parent] if parent >= 0 else None,      # the backend id of the parent node
                        'lang': lang if parent == -1 else None, 'base': base,
                        'clickable': i in clickable and (tag not in NATIVE_CLICK_TAGS or backend in listeners)}      # the page's own click listener, which is what makes a node `click`
                if i in contents: self.frame_of_owner[backend] = snapshot['documents'][contents[i]].get('frameId') and strings[snapshot['documents'][contents[i]]['frameId']]
                row = layout.get(i)
                if row is not None:
                    values = [s(x) for x in doc['layout']['styles'][row]]
                    info['style'] = dict(zip(STYLES, values)) if values else {}
                    info['bounds'] = doc['layout']['bounds'][row]
                self.by_backend[backend] = info
            # the language a node is in is the nearest lang attribute above it, else the document's
            index_of = {i: backend for i, backend in enumerate(nodes['backendNodeId'])}
            known = {}
            def language(i):
                path = []
                while i >= 0 and i not in known:
                    a = self.by_backend[index_of[i]]
                    if a['attrs'].get('lang') is not None: known[i] = a['attrs']['lang']; break
                    path.append(i); i = a['parent']
                value = known[i] if i >= 0 else lang
                for j in path: known[j] = value
                return value
            for i, backend in enumerate(nodes['backendNodeId']): self.by_backend[backend]['language'] = language(i)
            pseudo = dict(zip(nodes.get('pseudoType', {}).get('index', []), (strings[v] for v in nodes.get('pseudoType', {}).get('value', []))))
            for i, backend in enumerate(nodes['backendNodeId']):      # what is below each node, and which nodes the page does not number (incremental.py)
                self.by_backend[backend]['children'] = []
                if i in pseudo: self.by_backend[backend]['pseudo'] = pseudo[i]      # 'before', 'after', 'marker': the pseudo-element this node is
            for i, backend in enumerate(nodes['backendNodeId']):
                if nodes['parentIndex'][i] >= 0: self.by_backend[nodes['backendNodeId'][nodes['parentIndex'][i]]]['children'].append(backend)
            if number == 0: self.list_elements(nodes)
            def form_owner(i):      # the nearest <form> above an element: the scope of a radio button's group
                i = nodes['parentIndex'][i]
                while i >= 0:
                    if self.by_backend[index_of[i]]['tag'] == 'form': return index_of[i]
                    i = nodes['parentIndex'][i]
                return None
            for i, backend in enumerate(nodes['backendNodeId']):
                if self.by_backend[backend]['tag'] == 'input': self.by_backend[backend]['form'] = form_owner(i)

    def list_elements(self, nodes):
        roots = {i for i, kind in zip(nodes.get('shadowRootType', {}).get('index', []), nodes.get('shadowRootType', {}).get('value', [])) if kind >= 0}
        pseudo = set(nodes.get('pseudoType', {}).get('index', [])); parents = nodes['parentIndex']; inside = {}
        def in_shadow_tree(i):
            if i < 0: return False
            if i not in inside: inside[i] = i in roots or in_shadow_tree(parents[i])
            return inside[i]
        self.shadowed = bool(roots)
        for i, backend in enumerate(nodes['backendNodeId']):
            if nodes['nodeType'][i] == 1 and i not in pseudo and not in_shadow_tree(i): self.elements.append(backend)

    def get(self, backend): return self.by_backend.get(backend) or {}


# ------------------------------------------------------------------------------------------------ text

WORD = re.compile(r'\w+|[^\w\s]', re.UNICODE)      # a run of word characters, or one mark of punctuation: each starts a word as ICU breaks them (measured against chrome.automation's wordStarts, 'Pick a section.' -> 0 5 7 14)
SENTENCE_END = re.compile(r'[.!?]+["\')\]]*\s+')


MARKS = {}      # a container holds the text of what is in it, so that text is marked once for each distinct string and not once for each level of the tree
MARKED = [0]      # the characters of the strings in MARKS: the table is emptied when they are more than MARKED_LIMIT, and a long text (a whole page's) is not kept
MARKED_LIMIT = 2_000_000
MARKED_LONGEST = 2000


def remember(key, text, found):
    if len(text) > MARKED_LONGEST: return
    if MARKED[0] + len(text) > MARKED_LIMIT: MARKS.clear(); MARKED[0] = 0
    MARKS[key] = found; MARKED[0] += len(text)


def word_bounds(text):
    """Where the words of a text start and end, by `WORD`: ICU's rules (which Chromium uses) differ at hyphens, apostrophes and numbers with separators. NOT PORTED: ICU's."""
    found = MARKS.get(('words', text))
    if found is None:
        ms = list(WORD.finditer(text)); found = ([m.start() for m in ms], [m.end() for m in ms]); remember(('words', text), text, found)
    return list(found[0]), list(found[1])


def sentence_starts(text):
    """Where the sentences of a text start: the start, and after each full stop, question mark or exclamation mark followed by a space. NOT PORTED: ICU's rules."""
    if not text.strip(): return []
    found = MARKS.get(('sentences', text))
    if found is None:
        found = [0] + [m.end() for m in SENTENCE_END.finditer(text) if m.end() < len(text)]; remember(('sentences', text), text, found)
    return list(found)


# ------------------------------------------------------------------------------------------------ the conversion

# The default action verb Chromium gives a node (AXObject::Action, ax_object.cc): a text field activates, a checkable control checks (or unchecks), and the roles below have their own verb. Anything else is `click` when
# the node itself is what a click acts on (a listener the page put on it, or a native control of the kinds in CLICK_INPUTS), and `clickAncestor` when it is something above it. NVDA says "clickable" for `click` only.
ACTION_VERB = {'button': 'press', 'disclosureTriangle': 'press', 'disclosureTriangleGrouped': 'press', 'link': 'jump', 'listBoxOption': 'select', 'menuItem': 'select', 'menuListOption': 'select',
               'comboBoxMenuButton': 'open', 'comboBoxSelect': 'open', 'popUpButton': 'open', 'textField': 'activate', 'searchBox': 'activate', 'textFieldWithComboBox': 'activate'}
RANGE_ROLES = {'slider', 'spinButton', 'progressIndicator', 'meter', 'scrollBar', 'splitter'}
CHECKABLE = {'checkBox', 'menuItemCheckBox', 'menuItemRadio', 'radioButton', 'switch', 'toggleButton'}
CLICK_INPUTS = {'color', 'date', 'datetime-local', 'month', 'week', 'time'}      # <input> types that Chromium gives a verb of their own kind: the default, `click`
# Which roles are ordered sets and which are their items, and which a set looks through to find them (ui/accessibility/ax_role_properties.cc IsSetLike, IsItemLike; AXNode::IsIgnoredContainerForOrderedSet, SetRoleMatchesItemRole in ax_node.cc).
SET_LIKE = {'comboBoxSelect', 'descriptionList', 'docBibliography', 'feed', 'group', 'list', 'listBox', 'listGrid', 'menu', 'menuBar', 'menuListPopup', 'popUpButton', 'radioGroup', 'tabList', 'tree', 'treeGrid'}
ITEM_LIKE = {'article', 'comment', 'disclosureTriangle', 'disclosureTriangleGrouped', 'listItem', 'menuItem', 'menuItemRadio', 'tab', 'menuItemCheckBox', 'treeItem', 'listBoxOption', 'menuListOption', 'radioButton', 'term'}
SET_TRANSPARENT = {'cell', 'details', 'labelText', 'layoutTableCell', 'layoutTableRow', 'listItem', 'genericContainer', 'gridCell', 'row', 'scrollView', 'unknown'}
ITEMS_OF = {'feed': {'article'}, 'list': {'listItem'}, 'group': {'comment', 'listItem', 'menuItem', 'menuItemRadio', 'menuItemCheckBox', 'listBoxOption', 'treeItem'}, 'menu': {'menuItem', 'menuItemRadio', 'menuItemCheckBox'},
            'menuBar': {'menuItem', 'menuItemRadio', 'menuItemCheckBox'}, 'tabList': {'tab'}, 'tree': {'treeItem'}, 'treeItem': {'treeItem'}, 'listBox': {'listBoxOption'},
            'menuListPopup': {'menuListOption', 'menuItem', 'menuItemRadio', 'menuItemCheckBox'}, 'radioGroup': {'radioButton'}, 'descriptionList': {'term'}, 'comboBoxSelect': {'menuListPopup'}}


def item_matches(set_role, item_role):
    return item_role in ('disclosureTriangle', 'disclosureTriangleGrouped') or item_role in ITEMS_OF.get(set_role, ())


CELL_ROLES = {'cell', 'gridCell', 'columnHeader', 'rowHeader'}
ROW_GROUP_TAGS = {'thead', 'tbody', 'tfoot'}
MAX_COLSPAN = 1000
TABLE_ROLES = {'table', 'grid', 'treeGrid'}
TEXT_FIELDS = ('textField', 'searchBox', 'textFieldWithComboBox', 'spinButton')


COLOURS = {}      # the colours and sizes a page uses are few and each is asked about for every node


def argb(css):
    if css not in COLOURS:
        m = re.match(r'rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?', css or '')
        if not m: COLOURS[css] = None
        else:
            r, g, b = (int(x) for x in m.groups()[:3]); a = 255 if m.group(4) is None else round(float(m.group(4)) * 255)
            COLOURS[css] = (a << 24) | (r << 16) | (g << 8) | b
    return COLOURS[css]


SIZES = {}


def px(css):
    if css not in SIZES:
        m = re.match(r'([\d.]+)px', css or ''); SIZES[css] = float(m.group(1)) if m else None
    return SIZES[css]


def name_from(sources):
    """Which of the name's sources gave it: the first that has a value and was not superseded."""
    for src in sources or []:
        if src.get('superseded') or not src.get('value', {}).get('value'): continue
        if src['type'] == 'contents': return 'contents'
        if src['type'] == 'attribute': return {'title': 'title', 'value': 'value'}.get(src.get('attribute'), 'attribute')
        if src['type'] == 'relatedElement': return 'caption' if src.get('nativeSource') == 'tablecaption' else 'relatedElement'
        if src['type'] == 'placeholder': return 'placeholder'
        return 'attribute'
    return 'none'


class Unpatchable(Exception):
    """A list of nodes cannot be brought up to date from the nodes that changed: the page is converted whole."""


MISSING = object()
INTERNAL = ('_props', '_dom', '_submit')      # what `node` leaves for the passes after it, and they take away
PATCHABLE = {'state', 'color', 'backgroundColor', 'fontFamily', 'fontSize', 'bold', 'italic', 'underline', 'lineThrough', 'textSelStart', 'textSelEnd', 'docLoaded', 'docLoadingProgress', 'docUrl', 'url',
             'name', 'nameFrom', 'description', 'descriptionFrom'}      # what `patch` takes from a node made again
TEXTUAL = ('staticText', 'inlineTextBox', 'lineBreak')      # the name of these is the text of the page, and the text marks of every node above are made of it: a node of another role has a name that is no one's text


class Retained:
    """What a conversion leaves for `patch`: the order of the nodes, where each is in the tree, the list made, what `node` made of each, and the links seen."""
    def __init__(self, order, parent_of, roles, keys, ix_of, ix_of_backend, nodes, base, linked, viewport, focus, dom):
        self.order, self.parent_of, self.roles, self.keys, self.ix_of, self.ix_of_backend = order, parent_of, roles, keys, ix_of, ix_of_backend
        self.nodes, self.base, self.linked, self.viewport, self.focus, self.dom = nodes, base, set(linked), viewport, focus, dom


class Converter:
    """Makes the node list of one page from `fetch`'s answer. It keeps the ids it gave to nodes, so that a node is the same node in the next tree (`uid`)."""
    def __init__(self): self.uids = {}; self.next_uid = 0; self.context = None

    def uid(self, key):
        if key not in self.uids: self.uids[key] = self.next_uid; self.next_uid += 1
        return self.uids[key]

    def convert(self, raw, retain=False):
        """The node list of a page. With `retain` it keeps what `patch` needs to bring that list up to date from the few AX nodes that changed."""
        self.context = None
        ax = {n['nodeId']: n for n in raw['ax']}
        if not ax: return {'nodes': [], 'focusIx': -1}
        self.linked = set()
        dom, page, viewport = raw.get('_dom') or Dom(raw['dom'], raw.get('listeners', ())), raw['page'], raw['viewport'] or {}      # `_dom`: the elements of a page that has not changed (incremental.py)
        root = next((n for n in raw['ax'] if 'parentId' not in n), raw['ax'][0])
        frame_nodes, frame_root = prefix_frames(raw.get('frames'))      # a frame's id -> the root of its tree, whose node ids are made its own by a prefix
        ax.update(frame_nodes)

        row_group = {}      # a row's node id -> the node id of the row group (<thead>, <tbody>, <tfoot>) it was in: a row span ends there
        def unignored_children(n, group=None):
            for child_id in n.get('childIds', []):
                child = ax.get(child_id)
                if child is None: continue
                is_group = role_of(child) == 'rowGroup' or (child.get('ignored') and dom.get(child.get('backendDOMNodeId')).get('tag') in ROW_GROUP_TAGS)
                if child.get('ignored') or is_group: yield from unignored_children(child, child['nodeId'] if is_group else group)      # a row group is not in the tree chrome.automation gives: its rows are the table's
                else:
                    if group is not None: row_group[child['nodeId']] = group
                    yield child
            held = frame_root.get(dom.frame_of_owner.get(n.get('backendDOMNodeId')))      # an iframe holds the document of its frame, which the browser's tree reads as its child
            if held is not None: yield held

        order = []      # [(ax node, depth, parent index)] depth first, as emu/ext2/tree.js `walk` makes it
        def visit(n, depth, parent):
            order.append((n, depth, parent)); here = len(order) - 1
            for child in unignored_children(n): visit(child, depth + 1, here)
        visit(root, 0, -1)

        kids = {}; parent_of = {}
        for i, (n, depth, p) in enumerate(order):
            parent_of[i] = p
            if p >= 0: kids.setdefault(p, []).append(i)
        ix_of = {n['nodeId']: i for i, (n, _, _) in enumerate(order)}
        ix_of_backend = {n['backendDOMNodeId']: i for i, (n, _, _) in enumerate(order) if 'backendDOMNodeId' in n}
        roles = [role_of(n) for n, _, _ in order]

        nodes = []; keys = []; seen = {}; base = []
        for i, (n, depth, p) in enumerate(order):
            if 'backendDOMNodeId' in n: key = ('backend', n['backendDOMNodeId'])
            else: seen[p] = seen.get(p, 0) + 1; key = ('child', keys[p] if p >= 0 else None, seen[p])      # an inline text box has no element: it is its parent's nth child
            keys.append(key)
            nodes.append(self.node(i, n, depth, p, roles[i], dom, page, viewport, key, parent_of, roles, nodes[p]['language'] if p >= 0 and 'backendDOMNodeId' not in n else None, roles[p] if p >= 0 else None))
            if retain: base.append({**nodes[-1], 'state': dict(nodes[-1]['state'])})      # what `node` made, before the passes below add to it
        for i, (n, _, _) in enumerate(order):
            if n['nodeId'] in row_group: nodes[i]['_dom']['group'] = row_group[n['nodeId']]
        self.relations(nodes, order, ix_of, ix_of_backend)
        self.counts(nodes, kids, roles)
        self.defaults(nodes, parent_of)
        for i, nd in enumerate(nodes):      # a node with no box of its own (a line of text, a pseudo-element) is where its parent is
            if 'location' not in nd and parent_of[i] >= 0 and nodes[parent_of[i]]['state'].get('offscreen'): nd['state']['offscreen'] = True
        self.text_marks(nodes, kids, roles)
        self.containers(nodes, parent_of)
        flagged = [i for i, nd in enumerate(nodes) if nd['state'].get('focused')]      # the document says it is focused while a field in it is: the node that has the focus is the last of them, the deepest
        focus = flagged[-1] if flagged else -1
        for i in flagged[:-1]: del nodes[i]['state']['focused']
        if retain: self.context = Retained(order, parent_of, roles, keys, ix_of, ix_of_backend, nodes, base, self.linked, viewport, focus, dom)
        return {'nodes': nodes, 'focusIx': focus, 'url': page['url'], 'title': page['title'], 'sel': {'anchorIx': -1, 'anchorOffset': 0, 'focusIx': -1, 'focusOffset': 0}}

    def patch(self, ax, ids, backends, dom, page, viewport):
        """The node list of the last conversion (`retain`) brought up to date when only the nodes in `ids` (AX node ids) and `backends` (DOM nodes whose style changed) can have changed, and the viewport and the page's state: the nodes
        are made again as `convert` makes them, and one that differs from what was made before in more than the focus, the look and the page's address is not something this knows the effect of (a name is in the text marks of the
        nodes above it): `Unpatchable`, and the page is converted whole. The result is the list `convert` makes of the same page."""
        c = self.context
        if c is None or c.dom is not dom: raise Unpatchable('there is no conversion to bring up to date')
        dirty = {0, *(c.ix_of[i] for i in ids if i in c.ix_of), *(c.ix_of_backend[b] for b in backends if b in c.ix_of_backend)}
        if c.focus >= 0: dirty.add(c.focus)
        self.linked = set(c.linked)
        nodes = list(c.nodes); base = list(c.base)
        for i in sorted(dirty):
            n = ax[c.order[i][0]['nodeId']]; depth, p = c.order[i][1], c.parent_of[i]
            fresh = self.node(i, n, depth, p, c.roles[i], dom, page, viewport, c.keys[i], c.parent_of, c.roles, nodes[p]['language'] if p >= 0 and 'backendDOMNodeId' not in n else None, c.roles[p] if p >= 0 else None)
            kept = base[i]; changed = [k for k in fresh.keys() | kept.keys() if k not in INTERNAL and fresh.get(k, MISSING) != kept.get(k, MISSING)]
            for k in changed:
                if k == 'state':
                    now, was = fresh['state'], kept['state']
                    if any(now.get(x) != was.get(x) for x in now.keys() | was.keys() if x not in ('focused', 'offscreen')): raise Unpatchable('the state of a node changed')
                elif k not in PATCHABLE: raise Unpatchable(f'{k} of a node changed')
                elif k in ('name', 'nameFrom') and c.roles[i] in TEXTUAL: raise Unpatchable('the text of a node changed')
            new = dict(nodes[i])
            for k in changed:
                if k == 'state': continue
                if k in fresh: new[k] = fresh[k]
                else: new.pop(k, None)
            new['state'] = {**nodes[i]['state'], **({'focused': True} if fresh['state'].get('focused') else {})}
            if not fresh['state'].get('focused'): new['state'].pop('focused', None)
            nodes[i] = new; base[i] = {**fresh, 'state': dict(fresh['state'])}
        flagged = [i for i in sorted(dirty) if nodes[i]['state'].get('focused')]      # the one that has the focus is the last, the deepest, as `convert` has it
        focus = flagged[-1] if flagged else -1
        for i in flagged[:-1]: nodes[i]['state'].pop('focused')
        if viewport != c.viewport: self.scroll(c, nodes, ax, dom, viewport)
        c.nodes, c.base, c.linked, c.viewport, c.focus = nodes, base, self.linked, viewport, focus
        return {'nodes': nodes, 'focusIx': focus, 'url': page['url'], 'title': page['title'], 'sel': {'anchorIx': -1, 'anchorOffset': 0, 'focusIx': -1, 'focusOffset': 0}}

    @staticmethod
    def scroll(c, nodes, ax, dom, viewport):
        """The page was scrolled: which nodes are off the screen again. A node is when its own box is, and a node with no box of its own (a line of text, a pseudo-element) when its parent is."""
        for i, node in enumerate(nodes):
            backend = c.order[i][0].get('backendDOMNodeId')
            off = is_offscreen(dom.get(backend).get('bounds'), viewport) if backend is not None else False
            if 'location' not in node and c.parent_of[i] >= 0 and nodes[c.parent_of[i]]['state'].get('offscreen'): off = True
            if bool(node['state'].get('offscreen')) != off:
                nodes[i] = node = dict(node, state={k: v for k, v in node['state'].items() if k != 'offscreen'} | ({'offscreen': True} if off else {}))

    def node(self, i, n, depth, parent, role, dom, page, viewport, key, parent_of, roles, parent_lang=None, parent_role=None):
        props = {p['name']: p['value'].get('value') for p in n.get('properties', [])}
        backend = n.get('backendDOMNodeId')
        d = dom.get(backend) if backend is not None else {}
        attrs = d.get('attrs', {}); style = d.get('style', {})
        name = n.get('name', {}).get('value', '') if isinstance(n.get('name'), dict) else ''
        value = n.get('value', {}).get('value') if isinstance(n.get('value'), dict) else None
        if attrs.get('aria-valuetext') and role in RANGE_ROLES: value = attrs['aria-valuetext']      # a range's words (aria-valuetext) are what it holds, as chrome.automation's `value`: the protocol's own `valuetext` property is empty
        out = {'depth': depth, 'ix': i, 'uid': self.uid(key), 'role': role, 'nameFrom': 'contents' if role in ('staticText', 'inlineTextBox') else name_from(n.get('name', {}).get('sources')),
               'value': '' if value is None else str(value), 'indexInParent': 0, 'standardActions': ['doDefault'] if role not in ('inlineTextBox',) else [], 'hasPopup': '' if props.get('hasPopup') in (None, 'false') else props['hasPopup']}
        if name: out['name'] = name
        if n.get('description', {}).get('value'): out['description'] = n['description']['value']; out['descriptionFrom'] = 'relatedElement' if attrs.get('aria-describedby') else 'title' if attrs.get('title') else 'ariaDescription'
        if d.get('tag') and d['tag'] != '#text': out['htmlTag'] = '#document' if d['tag'] == '#document' else d['tag']
        if attrs.get('id'): out['htmlId'] = attrs['id']
        if backend is not None: out['backendId'] = backend      # the DOM node the browser holds for this one: what the page's focus is matched to (predict.py `match_focus`)
        if d.get('tag') == 'input': out['inputType'] = (attrs.get('type') or 'text').lower()
        if style.get('display') and d.get('type') == 1: out['display'] = style['display']
        out['language'] = (d['language'] if d.get('language') is not None else None) or (parent_lang if parent_lang is not None else page.get('lang') or '')
        if props.get('level') is not None: out['hierarchicalLevel'] = props['level']
        if props.get('invalid') is not None: out['invalidState'] = str(props['invalid'])
        if props.get('checked') is not None: out['checked'] = str(props['checked']).lower()
        elif props.get('pressed') is not None: out['checked'] = str(props['pressed']).lower()
        if props.get('selected') is not None: out['selected'] = bool(props['selected'])
        if props.get('disabled'): out['restriction'] = 'disabled'
        elif props.get('readonly'): out['restriction'] = 'readOnly'
        if props.get('roledescription'): out['roleDescription'] = props['roledescription']
        if props.get('autocomplete') and props['autocomplete'] != 'none': out['autoComplete'] = props['autocomplete']
        if attrs.get('placeholder'): out['placeholder'] = attrs['placeholder']
        if attrs.get('accesskey'): out['accessKey'] = attrs['accesskey']
        if attrs.get('aria-current') not in (None, ''): out['ariaCurrentState'] = attrs['aria-current']
        if attrs.get('aria-sort'): out['sortDirection'] = {'none': 'unsorted'}.get(attrs['aria-sort'], attrs['aria-sort'])
        if props.get('url'): out['url'] = props['url']
        elif role == 'image' and attrs.get('src'): out['url'] = urljoin(d.get('base') or page['url'], attrs['src'])
        out['defaultActionVerb'] = self.action_verb(role, d, attrs, out.get('checked'), props)
        if role == 'rootWebArea':
            top = parent < 0      # a frame's document is not the page: it has its own address and title
            loaded = page['readyState'] == 'complete' if top else True
            out.update(docTitle=page['title'] if top else name, docUrl=page['url'] if top else props.get('url', ''), docLoaded=loaded, docLoadingProgress=1 if loaded else 0.5, htmlTag='#document', url=page['url'] if top else props.get('url', ''),
                       scrollable=False, scrollX=0, scrollXMax=0, scrollXMin=0, scrollY=0, scrollYMax=0, scrollYMin=0)
            if top and not name: out['name'] = page['title']
        # the box and the look
        b = d.get('bounds')
        if b: out['location'] = out['unclippedLocation'] = {'left': round(b[0]), 'top': round(b[1]), 'width': round(b[2]), 'height': round(b[3])}      # whole pixels, as chrome.automation gives them
        if style:
            out['fontFamily'] = style.get('font-family', '').strip('"'); out['fontSize'] = px(style.get('font-size')) or 16.0
            out['color'] = argb(style.get('color')); out['backgroundColor'] = argb(style.get('background-color'))
            out['bold'] = int((style.get('font-weight') or '400') if (style.get('font-weight') or '400').isdigit() else 400) >= 600
            out['italic'] = style.get('font-style') == 'italic'
            out['underline'] = 'underline' in (style.get('text-decoration-line') or ''); out['lineThrough'] = 'line-through' in (style.get('text-decoration-line') or '')
            out = {k: v for k, v in out.items() if v is not None}
        # state
        state = {}
        if props.get('focusable'): state['focusable'] = True
        if props.get('focused'): state['focused'] = True
        editable = props.get('editable')
        if editable in ('plaintext', 'richtext'): state['editable'] = True
        if editable == 'richtext': state['richlyEditable'] = True
        if props.get('multiline') or (editable == 'richtext' and attrs.get('contenteditable') in ('', 'true') and attrs.get('aria-multiline') != 'false' and role in ('genericContainer', 'textField')): state['multiline'] = True      # an editing host of the page's own is a block of lines
        if props.get('required'): state['required'] = True
        if props.get('multiselectable'): state['multiselectable'] = True
        if props.get('orientation') in ('vertical', 'horizontal'): state[props['orientation']] = True
        if props.get('expanded') is True: state['expanded'] = True
        elif props.get('expanded') is False: state['collapsed'] = True
        if d.get('tag') == 'input' and out.get('inputType') == 'password': state['protected'] = True
        if props.get('hidden') or style.get('visibility') in ('hidden', 'collapse'): state['invisible'] = True
        if role == 'menuListPopup': state['invisible'] = True; out['htmlTag'] = 'div'; out['display'] = 'none'      # a select's popup is in a closed shadow root, not in the snapshot: Chromium holds it hidden, with its options not selected
        if role == 'menuListOption':
            out['display'] = 'block'
            if not out.get('selected'): state['invisible'] = True
        if is_offscreen(b, viewport): state['offscreen'] = True
        if role == 'link' and (props.get('url') or 'href' in attrs): self.linked.add(i); state['linked'] = True      # a link that goes somewhere (an anchor with no href, or a role=link, does not), and its text, and nothing else below it (measured against chrome.automation)
        elif role == 'staticText' and any(j in self.linked for j in self.ancestors(i, parent_of)): state['linked'] = True
        if role == 'genericContainer' and not d and parent_role in TEXT_FIELDS: out['htmlTag'] = 'div'; out['display'] = 'flow-root'      # the editor Chromium puts inside a text field is in a closed shadow root: not in the snapshot
        if (d.get('tag') == 'button' and attrs.get('type', 'submit') == 'submit') or (d.get('tag') == 'input' and out.get('inputType') in ('submit', 'image')): out['_submit'] = True
        out['state'] = state
        if state.get('focused') and page.get('caret') and role in TEXT_FIELDS: out['textSelStart'], out['textSelEnd'] = page['caret']
        elif role in TEXT_FIELDS: out['textSelStart'] = out['textSelEnd'] = 0
        # live regions: the node's own, and the nearest above it
        if props.get('live') not in (None, 'off'): out['liveStatus'] = props['live']
        if props.get('atomic'): out['liveAtomic'] = True
        if props.get('relevant'): out['liveRelevant'] = props['relevant']
        if props.get('busy'): out['liveBusy'] = True
        out['_props'] = props
        out['_dom'] = {'attrs': attrs, 'tag': d.get('tag'), 'form': d.get('form')}
        return out

    @staticmethod
    def native_action(tag, attrs):
        """A native control a click acts on: what Chromium takes for the element a node's action is, with no script."""
        if tag in ('a', 'area'): return 'href' in attrs
        if tag == 'input': return (attrs.get('type') or 'text').lower() not in ('hidden', 'range')
        return tag in ('button', 'select', 'textarea', 'summary', 'option')

    @staticmethod
    def action_verb(role, d, attrs, checked, props):
        """Chromium's `AXObject::Action` for a node, from its role and its element."""
        tag = d.get('tag')
        editable_root = attrs.get('contenteditable') in ('', 'true', 'plaintext-only') and role not in ('staticText', 'inlineTextBox')
        if role in ('textField', 'searchBox', 'textFieldWithComboBox') or (role == 'spinButton' and tag == 'input'): return 'activate'
        if role in CHECKABLE: return 'uncheck' if checked == 'true' else 'check'
        if role in ACTION_VERB: return ACTION_VERB[role]
        if editable_root: return 'activate'
        if d.get('clickable') or (tag == 'input' and (attrs.get('type') or '').lower() in CLICK_INPUTS) or (Converter.native_action(tag, attrs) and not props.get('disabled')):
            return 'click' if role not in ('rootWebArea', 'staticText', 'inlineTextBox') else 'clickAncestor'
        return 'clickAncestor'

    @staticmethod
    def ancestors(i, parent_of):
        while parent_of[i] >= 0:
            i = parent_of[i]; yield i

    def relations(self, nodes, order, ix_of, ix_of_backend):
        for i, (n, _, _) in enumerate(order):
            for prop, key in (('labelledby', 'labelledByIx'), ('details', 'detailsIx')):      # the two relations chrome.automation gives as nodes; the others (error message, controls, described by) it does not, and the emulator does not read them
                related = [p['value'].get('relatedNodes') or [] for p in n.get('properties', []) if p['name'] == prop]
                targets = [ix_of_backend.get(r.get('backendDOMNodeId'), -1) for r in (related[0] if related else [])]
                if any(t >= 0 for t in targets): nodes[i][key] = targets
        for i, nd in enumerate(nodes):
            for target in nd.get('labelledByIx', []):
                if target >= 0: nodes[target].setdefault('labelForIx', []).append(i)
        for nd in nodes: nd.pop('_props', None)
        for i, nd in enumerate(nodes):
            nd['childrenIx'] = []
        for i, (n, depth, p) in enumerate(order):
            if p >= 0: nodes[p]['childrenIx'].append(i); nodes[i]['indexInParent'] = len(nodes[p]['childrenIx']) - 1
        for nd in nodes:
            if not nd['childrenIx']: del nd['childrenIx']; nd['children'] = []

    def defaults(self, nodes, parent_of):
        """A form's default button is its first submit button: Chromium marks it `default`. (A form-associated button outside the form, by the `form` attribute, is not found.)"""
        seen = set()
        for i, nd in enumerate(nodes):
            if not nd.pop('_submit', False): continue
            form = next((a for a in self.ancestors(i, parent_of) if nodes[a].get('htmlTag') == 'form'), None)
            if form is not None and form not in seen: seen.add(form); nd['state']['default'] = True

    def counts(self, nodes, kids, roles):
        """Position in a set, size of a set, and the table model: where each cell is, what it spans, and its header cells. Worked out from the tree and the page's attributes as Chromium does, and not read from the AXNode."""
        self.sets(nodes, kids, roles)
        for t, nd in enumerate(nodes):
            if nd['role'] in TABLE_ROLES: self.table(t, nodes, kids, roles)
        for nd in nodes: nd.pop('_dom', None)

    @staticmethod
    def number(attrs, name, minimum=1):
        """An integer attribute of the page, or None when it is absent, not a number or less than `minimum`."""
        try: v = int(str(attrs.get(name)).strip())
        except ValueError: return None
        return v if v >= minimum else None

    @staticmethod
    def span(attrs, name, zero):
        """HTML's number of rows or columns a cell spans: the digits the attribute starts with (so `2px` is 2), `zero` where it is 0, None where there are none."""
        found = re.match(r'\s*\+?(\d+)', attrs.get(name) or '')
        return None if not found else int(found.group(1)) or zero

    def table(self, t, nodes, kids, roles):
        """AXTableInfo: where each cell of a table is and which header cells go with it."""
        cells = self.table_grid(t, nodes, kids, roles)
        by_column, by_row = {}, {}
        for c in cells:
            nd = nodes[c]
            for dc in range(nd['tableCellColumnSpan']):
                if roles[c] == 'columnHeader': by_column.setdefault(nd['tableCellColumnIndex'] + dc, []).append(c)
            for dr in range(nd['tableCellRowSpan']):
                if roles[c] == 'rowHeader': by_row.setdefault(nd['tableCellRowIndex'] + dr, []).append(c)
        for c in cells:      # the column headers of the first column a cell covers and the row headers of its first row, in the order they appear (a header cell lists itself)
            nd = nodes[c]
            if by_column.get(nd['tableCellColumnIndex']): nd['tableCellColumnHeadersIx'] = list(by_column[nd['tableCellColumnIndex']])
            if by_row.get(nd['tableCellRowIndex']): nd['tableCellRowHeadersIx'] = list(by_row[nd['tableCellRowIndex']])

    def table_grid(self, t, nodes, kids, roles):
        """The rows of a table (through generic containers) and the grid its cells fill: a cell spanning rows or columns keeps the slots below and beside it. Sets each cell's row, column, spans and `aria-rowindex` /
        `aria-colindex` (a cell without one follows the one before it), and the table's counts. Returns the cells."""
        rows = []; stack = list(reversed(kids.get(t, [])))
        while stack:
            c = stack.pop()
            if roles[c] == 'row': rows.append(c)
            elif roles[c] == 'genericContainer': stack.extend(reversed(kids.get(c, [])))
        last_row = {}      # the last row of each row group; of a row in none, of the table
        for r, row in enumerate(rows): last_row[nodes[row]['_dom'].get('group')] = r
        if None in last_row: last_row[None] = len(rows) - 1
        taken = set(); cells = []; columns = 0; aria_row = 0
        for r, row in enumerate(rows):
            aria_row = self.number(nodes[row]['_dom']['attrs'], 'aria-rowindex') or aria_row + 1
            col = 0; aria_col = 1
            for c in kids.get(row, []):
                if roles[c] not in CELL_ROLES: continue
                attrs = nodes[c]['_dom']['attrs']
                end = last_row[nodes[row]['_dom'].get('group')]
                rs = self.span(attrs, 'rowspan', end - r + 1) or self.number(attrs, 'aria-rowspan') or 1; cs = self.span(attrs, 'colspan', 1) or self.number(attrs, 'aria-colspan') or 1
                rs = min(rs, end - r + 1); cs = min(cs, MAX_COLSPAN)      # a span ends at the row group's last row (HTML clamps it there; rowspan 0 means "to there"), and a column span is at most 1000
                while (r, col) in taken: col += 1
                aria_col = self.number(attrs, 'aria-colindex') or aria_col
                nodes[c].update(tableCellRowIndex=r, tableCellColumnIndex=col, tableCellRowSpan=rs, tableCellColumnSpan=cs, tableCellAriaRowIndex=aria_row, tableCellAriaColumnIndex=aria_col)
                for dr in range(rs):
                    for dc in range(cs): taken.add((r + dr, col + dc))
                cells.append(c); col += cs; aria_col += cs
            columns = max(columns, col)
        nodes[t]['tableRowCount'] = len(rows); nodes[t]['tableColumnCount'] = columns
        return cells

    def sets(self, nodes, kids, roles):
        """AXTree::ComputeSetSizePosInSet: an item's position in the ordered set that holds it, and a set's size. The set is the nearest ancestor that is not an ignored container (`AXNode::GetOrderedSet`), its items are the
        descendants of the role it takes (`SetRoleMatchesItemRole`) seen through ignored containers, and `aria-posinset` / `aria-setsize` on an item or on the set say what the page means: the size is the largest of
        the items counted, the numbers the page gave and the last position."""
        parent = {c: p for p, cs in kids.items() for c in cs}
        def ordered_set(i):
            p = parent.get(i)
            while p is not None and roles[p] in SET_TRANSPARENT: p = parent.get(p)
            return p
        def items_of(s):
            out = []; stack = list(reversed(kids.get(s, [])))
            while stack:
                c = stack.pop()
                if item_matches(roles[s], roles[c]): out.append(c)
                if roles[c] in SET_TRANSPARENT: stack.extend(reversed(kids.get(c, [])))
            return out
        measured = {}
        def measure(s):
            if s not in measured:
                items = items_of(s); size = self.number(nodes[s]['_dom']['attrs'], 'aria-setsize', 0) or 0; last = 0; positions = {}
                for c in items:
                    attrs = nodes[c]['_dom']['attrs']
                    last = self.number(attrs, 'aria-posinset') or last + 1; positions[c] = last
                    size = max(size, self.number(attrs, 'aria-setsize', 0) or 0, last)
                measured[s] = (max(size, len(items)), positions)
            return measured[s]
        for i, nd in enumerate(nodes):
            if roles[i] in SET_LIKE and roles[i] != 'comboBoxSelect':
                size, positions = measure(i)
                if size: nd['setSize'] = size
            if roles[i] == 'comboBoxSelect': self.select_position(i, nodes, kids, roles)
            if roles[i] in ITEM_LIKE:
                s = ordered_set(i)
                if s is None or not item_matches(roles[s], roles[i]): continue
                size, positions = measure(s)
                if i in positions: nd['posInSet'] = positions[i]; nd['setSize'] = size
        self.radio_groups(nodes, roles, parent)

    @staticmethod
    def radio_groups(nodes, roles, parent):
        """A native radio button's group is the radios of its document and form (or of no form) with its name, in the order of the tree; it gives the numbers whatever set holds the button."""
        def document(i):
            while i is not None and roles[i] != 'rootWebArea': i = parent.get(i)
            return i
        groups = {}
        for i, nd in enumerate(nodes):
            dom = nd['_dom']
            if roles[i] == 'radioButton' and dom['tag'] == 'input' and dom['attrs'].get('name'): groups.setdefault((document(i), dom['form'], dom['attrs']['name']), []).append(i)
        for group in groups.values():
            for k, i in enumerate(group): nodes[i]['posInSet'] = k + 1; nodes[i]['setSize'] = len(group)

    @staticmethod
    def select_position(i, nodes, kids, roles):
        """A native select holds its options below a popup node, and gives the size of the set they make and, for itself, the position of the selected option (measured against the extension's tree)."""
        options = []; stack = list(reversed(kids.get(i, [])))
        while stack:
            c = stack.pop()
            if roles[c] == 'menuListOption': options.append(c)
            else: stack.extend(reversed(kids.get(c, [])))
        if options: nodes[i]['setSize'] = len(options); nodes[i]['posInSet'] = next((k + 1 for k, c in enumerate(options) if nodes[c].get('selected')), 1)

    def text_marks(self, nodes, kids, roles):
        """Word, sentence and line starts of the nodes that hold text. A text field's are its value's, a static text's lines are those of its inline text boxes (Chromium makes one for each line it laid out),
        and any other node's are those of the text it holds (the static texts below it, joined)."""
        inner = {}
        def text_of(i):
            if i in inner: return inner[i]
            role = nodes[i]['role']
            if role in ('inlineTextBox', 'staticText', 'lineBreak'): t = nodes[i]['name']
            elif role in TEXT_FIELDS: t = nodes[i]['value']
            else: t = ''.join(text_of(c) for c in kids.get(i, []) if roles[c] != 'inlineTextBox')
            inner[i] = t; return t
        for i, nd in enumerate(nodes):
            text = text_of(i)
            starts, ends = word_bounds(text)
            nd['wordStarts'], nd['wordEnds'] = starts, ends
            nd['sentenceStarts'] = sentence_starts(text); nd['sentenceEnds'] = []
            lines = [0] if text else []
            if nd['role'] == 'staticText':
                pos = 0
                for c in [c for c in kids.get(i, []) if roles[c] == 'inlineTextBox'][:-1]: pos += len(nodes[c]['name']); lines.append(pos)
            nd['lineStartOffsets'] = lines

    def containers(self, nodes, parent_of):
        """The live region a node is in: the nearest ancestor-or-self that sets one."""
        region = []      # the node that is the live region each node is in: itself if it sets one, else the one its parent is in (a parent comes before its children)
        for i, nd in enumerate(nodes):
            a = i if nd.get('liveStatus') else (region[parent_of[i]] if parent_of[i] >= 0 else None)
            region.append(a)
            if a is not None:
                nd['containerLiveStatus'] = nodes[a]['liveStatus']; nd['containerLiveAtomic'] = bool(nodes[a].get('liveAtomic')); nd['containerLiveBusy'] = bool(nodes[a].get('liveBusy'))
                if nodes[a].get('liveRelevant'): nd['containerLiveRelevant'] = nodes[a]['liveRelevant']
