"""A tree source for a platform where chrome.automation gives the extension no desktop tree (macOS: A11-208 found `getDesktop` never answers there).

The browser's DevTools port says what the renderer's accessibility tree holds (`Accessibility.getFullAXTree`), and what the page's elements are (`DOMSnapshot.captureSnapshot`): this puts the two
together into the node list that `emu/ext2/tree.js` makes from chrome.automation, so that the rest of the runtime (`predict.py`, and the emulator under it) does not know which it was given.

It is the lower-fidelity source ADR 0047 allows, and it is not the same tree. What the DevTools protocol does not say is worked out here from what it does:
  * the roles are exact (`chromeRole` is Chromium's own number, roles.json names it);
  * a text's line starts are those of its inline text boxes, which Chromium makes one for each line; its word and sentence starts are found with a regular expression and not with ICU's rules;
  * the table indexes, the position in a set and the size of one are counted from the tree, and not read from the AXNode that Chromium holds;
  * `visited`, `default`, `offscreen` beyond the viewport, the document's text selection and the node's `nameFrom` beyond the first source are not known, or are guessed (each is marked below).
The write-up measures what that costs (docs/playwright-middleware-spike.md, Q2).
"""
import json, os, re
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = {int(k): v for k, v in json.load(open(os.path.join(HERE, 'roles.json'))).items()}      # Chromium's Role enum: number -> chrome.automation's name

STYLES = ['display', 'color', 'background-color', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration-line', 'visibility']
# What is asked of the page in the same moment as the two trees: where it is, how loaded, and the caret of the field that has the focus.
PAGE_JS = """JSON.stringify((() => { const a = document.activeElement, text = a && /^(INPUT|TEXTAREA)$/.test(a.tagName); let s = null; try { s = text ? [a.selectionStart, a.selectionEnd] : null; } catch (e) {} \
return {url: location.href, title: document.title, readyState: document.readyState, lang: document.documentElement.lang || '', caret: s}; })())"""


def fetch(call_many):
    """What a conversion needs from one page. `call_many([(method, params), ...])` sends DevTools commands of that page together and answers with their results in order: the AX tree, the DOM, the viewport
    and the page's own state are read in one round trip (the browser answers them in the order sent)."""
    ax, dom, metrics, evaluated, frames = call_many([
        ('Accessibility.getFullAXTree', {}),
        ('DOMSnapshot.captureSnapshot', {'computedStyles': STYLES, 'includeDOMRects': True}),
        ('Page.getLayoutMetrics', {}),
        ('Runtime.evaluate', {'expression': PAGE_JS, 'returnByValue': True}),
        ('Page.getFrameTree', {}),
    ])
    children = []
    def collect(tree):
        for child in tree.get('childFrames', []): children.append(child['frame']['id']); collect(child)
    collect(frames['frameTree'])
    inner = call_many([('Accessibility.getFullAXTree', {'frameId': f}) for f in children]) if children else []
    if 'value' not in evaluated.get('result', {}): raise ValueError('the page has no state to read (it is closing)')
    return {'ax': ax['nodes'], 'dom': dom, 'viewport': metrics.get('cssVisualViewport') or metrics.get('visualViewport'), 'page': json.loads(evaluated['result']['value']), 'frames': {f: r['nodes'] for f, r in zip(children, inner)}}      # a page that is gone has no value: KeyError, which the caller takes as one read lost


# ------------------------------------------------------------------------------------------------ the page's elements

class Dom:
    """The elements of a DOMSnapshot by backendNodeId: tag, attributes, computed style and the box."""
    def __init__(self, snapshot):
        strings = snapshot['strings']; s = lambda i: strings[i] if i >= 0 else None
        self.by_backend = {}; self.frame_of_owner = {}      # frame_of_owner: the backend id of an iframe element -> the id of the frame it holds
        for doc in snapshot['documents']:
            nodes = doc['nodes']
            lang = s(doc.get('contentLanguage', -1))
            layout = {}
            for row, node in enumerate(doc['layout']['nodeIndex']): layout[node] = row
            clickable = set(nodes.get('isClickable', {}).get('index', []))
            contents = dict(zip(nodes.get('contentDocumentIndex', {}).get('index', []), nodes.get('contentDocumentIndex', {}).get('value', [])))
            for i, backend in enumerate(nodes['backendNodeId']):
                attrs = nodes['attributes'][i]
                info = {'tag': (s(nodes['nodeName'][i]) or '').lower(), 'type': nodes['nodeType'][i], 'attrs': {s(attrs[j]): s(attrs[j + 1]) for j in range(0, len(attrs), 2)}, 'parent': nodes['parentIndex'][i],
                        'lang': lang if nodes['parentIndex'][i] == -1 else None, 'base': s(doc.get('baseURL')), 'clickable': i in clickable}
                if i in contents: self.frame_of_owner[backend] = snapshot['documents'][contents[i]].get('frameId') and strings[snapshot['documents'][contents[i]]['frameId']]
                row = layout.get(i)
                if row is not None:
                    values = [s(x) for x in doc['layout']['styles'][row]]
                    info['style'] = dict(zip(STYLES, values)) if values else {}
                    info['bounds'] = doc['layout']['bounds'][row]
                self.by_backend[backend] = info
            # the language a node is in is the nearest lang attribute above it, else the document's
            index_of = {i: backend for i, backend in enumerate(nodes['backendNodeId'])}
            def language(i):
                while i >= 0:
                    a = self.by_backend[index_of[i]]
                    if a['attrs'].get('lang') is not None: return a['attrs']['lang']
                    i = a['parent']
                return lang
            for i, backend in enumerate(nodes['backendNodeId']): self.by_backend[backend]['language'] = language(i)

    def get(self, backend): return self.by_backend.get(backend) or {}


# ------------------------------------------------------------------------------------------------ text

WORD = re.compile(r'\w+|[^\w\s]', re.UNICODE)      # a run of word characters, or one mark of punctuation: each starts a word as ICU breaks them (measured against chrome.automation's wordStarts, 'Pick a section.' -> 0 5 7 14)
SENTENCE_END = re.compile(r'[.!?]+["\')\]]*\s+')


def word_bounds(text):
    """Where the words of a text start and end, by `WORD`: ICU's rules (which Chromium uses) differ at hyphens, apostrophes and numbers with separators. NOT PORTED: ICU's."""
    ms = list(WORD.finditer(text))
    return [m.start() for m in ms], [m.end() for m in ms]


def sentence_starts(text):
    """Where the sentences of a text start: the start, and after each full stop, question mark or exclamation mark followed by a space. NOT PORTED: ICU's rules."""
    if not text.strip(): return []
    return [0] + [m.end() for m in SENTENCE_END.finditer(text) if m.end() < len(text)]


# ------------------------------------------------------------------------------------------------ the conversion

ACTION_VERB = {'button': 'press', 'toggleButton': 'press', 'popUpButton': 'press', 'link': 'jump', 'checkBox': 'check', 'switch': 'check', 'menuItemCheckBox': 'check', 'radioButton': 'select', 'menuItemRadio': 'select',
               'menuItem': 'click', 'tab': 'select', 'listBoxOption': 'select', 'textField': 'activate', 'searchBox': 'activate', 'textFieldWithComboBox': 'activate', 'comboBoxSelect': 'open',
               'comboBoxMenuButton': 'open', 'slider': 'activate', 'spinButton': 'activate'}
SET_ROLES = {'listItem', 'listBoxOption', 'radioButton', 'tab', 'treeItem', 'menuItem', 'menuItemCheckBox', 'menuItemRadio', 'menuListOption', 'article', 'listMarker'}
CELL_ROLES = {'cell', 'gridCell', 'columnHeader', 'rowHeader'}
TABLE_ROLES = {'table', 'grid', 'treeGrid'}
TEXT_FIELDS = ('textField', 'searchBox', 'textFieldWithComboBox', 'spinButton')


def argb(css):
    m = re.match(r'rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?', css or '')
    if not m: return None
    r, g, b = (int(x) for x in m.groups()[:3]); a = 255 if m.group(4) is None else round(float(m.group(4)) * 255)
    return (a << 24) | (r << 16) | (g << 8) | b


def px(css):
    m = re.match(r'([\d.]+)px', css or ''); return float(m.group(1)) if m else None


def name_from(sources):
    """Which of the name's sources gave it: the first that has a value and was not superseded."""
    for src in sources or []:
        if src.get('superseded') or not src.get('value', {}).get('value'): continue
        if src['type'] == 'contents': return 'contents'
        if src['type'] == 'attribute': return 'title' if src.get('attribute') == 'title' else 'attribute'
        if src['type'] == 'relatedElement': return 'relatedElement'
        if src['type'] == 'placeholder': return 'placeholder'
        return 'attribute'
    return 'none'


class Converter:
    """Makes the node list of one page from `fetch`'s answer. It keeps the ids it gave to nodes, so that a node is the same node in the next tree (`uid`)."""
    def __init__(self): self.uids = {}; self.next_uid = 0

    def uid(self, key):
        if key not in self.uids: self.uids[key] = self.next_uid; self.next_uid += 1
        return self.uids[key]

    def convert(self, raw):
        ax = {n['nodeId']: n for n in raw['ax']}
        if not ax: return {'nodes': [], 'focusIx': -1}
        dom, page, viewport = Dom(raw['dom']), raw['page'], raw['viewport'] or {}
        root = next((n for n in raw['ax'] if 'parentId' not in n), raw['ax'][0])
        frame_root = {}      # a frame's id -> the root of its tree, whose node ids are made its own by a prefix
        for frame, frame_nodes in (raw.get('frames') or {}).items():
            for n in frame_nodes:
                renamed = dict(n, nodeId=f'{frame}:{n["nodeId"]}', childIds=[f'{frame}:{c}' for c in n.get('childIds', [])])
                if 'parentId' in n: renamed['parentId'] = f'{frame}:{n["parentId"]}'
                else: frame_root[frame] = renamed
                ax[renamed['nodeId']] = renamed

        def unignored_children(n):
            for child_id in n.get('childIds', []):
                child = ax.get(child_id)
                if child is None: continue
                if child.get('ignored'): yield from unignored_children(child)
                else: yield child
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
        roles = [ROLES.get(n['chromeRole']['value'], 'unknown') for n, _, _ in order]

        nodes = []; keys = []; seen = {}
        for i, (n, depth, p) in enumerate(order):
            if 'backendDOMNodeId' in n: key = ('backend', n['backendDOMNodeId'])
            else: seen[p] = seen.get(p, 0) + 1; key = ('child', keys[p] if p >= 0 else None, seen[p])      # an inline text box has no element: it is its parent's nth child
            keys.append(key)
            nodes.append(self.node(i, n, depth, p, roles[i], dom, page, viewport, key, parent_of, roles, nodes[p]['language'] if p >= 0 and 'backendDOMNodeId' not in n else None, roles[p] if p >= 0 else None))
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
        return {'nodes': nodes, 'focusIx': focus, 'url': page['url'], 'title': page['title'], 'sel': {'anchorIx': -1, 'anchorOffset': 0, 'focusIx': -1, 'focusOffset': 0}}

    def node(self, i, n, depth, parent, role, dom, page, viewport, key, parent_of, roles, parent_lang=None, parent_role=None):
        props = {p['name']: p['value'].get('value') for p in n.get('properties', [])}
        backend = n.get('backendDOMNodeId')
        d = dom.get(backend) if backend is not None else {}
        attrs = d.get('attrs', {}); style = d.get('style', {})
        name = n.get('name', {}).get('value', '') if isinstance(n.get('name'), dict) else ''
        value = n.get('value', {}).get('value') if isinstance(n.get('value'), dict) else None
        out = {'depth': depth, 'ix': i, 'uid': self.uid(key), 'role': role, 'nameFrom': 'contents' if role in ('staticText', 'inlineTextBox') else name_from(n.get('name', {}).get('sources')),
               'value': '' if value is None else str(value), 'indexInParent': 0, 'standardActions': ['doDefault'] if role not in ('inlineTextBox',) else [], 'hasPopup': '' if props.get('hasPopup') in (None, 'false') else props['hasPopup']}
        if name: out['name'] = name
        if n.get('description', {}).get('value'): out['description'] = n['description']['value']; out['descriptionFrom'] = 'relatedElement' if attrs.get('aria-describedby') else 'title' if attrs.get('title') else 'ariaDescription'
        if d.get('tag') and d['tag'] != '#text': out['htmlTag'] = '#document' if d['tag'] == '#document' else d['tag']
        if attrs.get('id'): out['htmlId'] = attrs['id']
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
        verb = ACTION_VERB.get(role) or ('click' if d.get('clickable') and role not in ('rootWebArea', 'staticText', 'inlineTextBox') else None)      # a node that has a click listener: Chromium's verb for it is `click`
        if verb == 'check' and out.get('checked') == 'true': verb = 'uncheck'
        out['defaultActionVerb'] = verb or 'clickAncestor'
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
        if props.get('multiline'): state['multiline'] = True
        if props.get('required'): state['required'] = True
        if props.get('multiselectable'): state['multiselectable'] = True
        if props.get('orientation') in ('vertical', 'horizontal'): state[props['orientation']] = True
        if props.get('expanded') is True: state['expanded'] = True
        elif props.get('expanded') is False: state['collapsed'] = True
        if d.get('tag') == 'input' and out.get('inputType') == 'password': state['protected'] = True
        if props.get('hidden') or style.get('visibility') in ('hidden', 'collapse'): state['invisible'] = True
        if b and viewport and (b[1] + b[3] < 0 or b[1] > viewport.get('pageY', 0) + viewport.get('clientHeight', 1e9) or b[0] + b[2] < 0 or b[0] > viewport.get('pageX', 0) + viewport.get('clientWidth', 1e9)): state['offscreen'] = True
        if role == 'link' or (role == 'staticText' and any(roles[j] == 'link' for j in self.ancestors(i, parent_of))): state['linked'] = True      # the link and its text, and nothing else below it (measured against chrome.automation)
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
        return out

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
        """Position in a set, size of a set, and the table indexes, counted from the tree. NOT the AXNode's own numbers."""
        for parent, children in kids.items():
            for role in SET_ROLES & {roles[c] for c in children}:
                same = [c for c in children if roles[c] == role]
                for k, c in enumerate(same): nodes[c]['posInSet'] = k + 1; nodes[c]['setSize'] = len(same)
        for t, nd in enumerate(nodes):
            if nd['role'] not in TABLE_ROLES: continue
            rows = [] ; stack = list(reversed(kids.get(t, [])))
            while stack:
                c = stack.pop()
                if roles[c] == 'row': rows.append(c)
                elif roles[c] in ('rowGroup', 'genericContainer'): stack.extend(reversed(kids.get(c, [])))
            cols = 0
            for r, row in enumerate(rows):
                col = 0
                for c in kids.get(row, []):
                    if roles[c] not in CELL_ROLES: continue
                    attrs = nodes[c]
                    nodes[c]['tableCellRowIndex'] = r; nodes[c]['tableCellColumnIndex'] = col
                    nodes[c]['tableCellRowSpan'] = nodes[c].get('tableCellRowSpan', 1); nodes[c]['tableCellColumnSpan'] = nodes[c].get('tableCellColumnSpan', 1)
                    col += nodes[c]['tableCellColumnSpan']
                cols = max(cols, col)
            nd['tableRowCount'] = len(rows); nd['tableColumnCount'] = cols

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
        for i, nd in enumerate(nodes):
            for a in [i, *self.ancestors(i, parent_of)]:
                if nodes[a].get('liveStatus'):
                    nd['containerLiveStatus'] = nodes[a]['liveStatus']; nd['containerLiveAtomic'] = bool(nodes[a].get('liveAtomic')); nd['containerLiveBusy'] = bool(nodes[a].get('liveBusy'))
                    if nodes[a].get('liveRelevant'): nd['containerLiveRelevant'] = nodes[a]['liveRelevant']
                    break
