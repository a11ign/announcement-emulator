"""The incremental read of a page's tree (incremental.py, A11-229): a page that only moved its focus or changed a form control's value is brought up to date from the few nodes that changed, and the tree it gives
is the tree a read from scratch gives. The browser here is a recorded page (fixtures/structure/devtools-lists.json.gz) that answers the commands the reader sends and can be changed the way a page changes."""
import gzip, json, os, unittest

import axtree, incremental

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = ('Accessibility.getFullAXTree', 'DOMSnapshot.captureSnapshot')


def load(name='lists', where='structure'):
    with gzip.open(os.path.join(HERE, 'fixtures', where, f'devtools-{name}.json.gz' if where == 'structure' else f'{name}.json.gz'), 'rt') as f: return json.load(f)


def copy_of(value): return json.loads(json.dumps(value))


class Browser:
    """The commands incremental.py sends, answered from a recorded read of a page. `probe` is what the page's listener answers (cdp.py `__aeProbe`) and moves with the page."""
    def __init__(self, raw):
        self.raw = copy_of(raw); self.calls = []; self.lag = False; self.raw.setdefault('listeners', [])
        self.ax = {n['nodeId']: n for n in self.raw['ax']}
        dom = axtree.Dom(self.raw['dom'], self.raw['listeners'])
        self.elements = dom.elements
        self.controls = [b for b in dom.elements if dom.get(b)['tag'] in incremental.FORM_TAGS]
        self.probe = {'doc': 'd1', 'muts': 0, 'soft': [], 'elements': len(dom.elements), 'layout': 0, 'shadows': 0, 'active': -1, 'looks': [], 'forms': [0] * len(self.controls)}
        self.frames = []; self.stale = {}; self.expressions = []
        self.frame_probes = {f: dict(self.probe, forms=[], active=-1, elements=1) for f in self.raw.get('frames', {})}      # the page's frames, each quiet; a frame's probe is asked in the context named for it
        self.labels = self.listening_labels(dom)

    def listening_labels(self, dom):
        """What the page answers to the question of which <label>s carry a click listener: a 0 or a 1 for each label of the document, in order (axtree.py LABELS_JS), the ones the recording found."""
        nodes = self.raw['dom']['documents'][0]['nodes']; strings = self.raw['dom']['strings']
        labels = [nodes['backendNodeId'][i] for i in range(len(nodes['parentIndex'])) if (strings[nodes['nodeName'][i]] or '').lower() == 'label']
        return [1 if b in self.raw['listeners'] else 0 for b in labels]

    def call_many(self, commands):
        out = []
        for method, params in commands:
            self.calls.append(method); self.expressions.append(params.get('expression', ''))
            out.append(copy_of(self.answer(method, params)))      # a browser's answer is a new object each time
        return out

    def answer(self, method, params):
        if method == 'Runtime.evaluate':
            expression = params['expression']
            if '__aeProbe' in expression and 'contextId' in params:
                probe = self.frame_probes.get(params['contextId'].replace('context of ', ''))
                return {'result': {'value': json.dumps(probe)}} if probe is not None else {'result': {}}
            if '__aeProbe' in expression and '__aeCommit' not in expression: return {'result': {'value': json.dumps(self.probe)}}
            if '__aeCommit' in expression: return {'result': {}}
            if 'getEventListeners' in expression: return {'result': {'value': json.dumps(self.labels)}}
            return {'result': {'value': json.dumps(self.raw['page'])}}
        if method == 'Page.getLayoutMetrics': return {'cssVisualViewport': self.raw['viewport']}
        if method == 'Page.getFrameTree': return {'frameTree': {'frame': {'id': 'main'}, 'childFrames': [{'frame': {'id': f}} for f in [*self.raw.get('frames', {}), *self.frames]]}}
        if method == 'Accessibility.getFullAXTree': return {'nodes': list(self.ax.values())} if not params.get('frameId') else {'nodes': self.raw.get('frames', {}).get(params['frameId'], [])}
        if method == 'DOMSnapshot.captureSnapshot': return self.raw['dom']
        if method == 'Accessibility.getPartialAXTree':
            held = [n for n in self.ax.values() if n.get('backendDOMNodeId') == params['backendNodeId']]
            return {'nodes': [self.stale.get(n['nodeId'], n) for n in held[:1]]}
        if method == 'Accessibility.getChildAXNodes': return {'nodes': [self.ax[c] for c in self.ax[params['id']].get('childIds', [])]}
        raise AssertionError(method)

    # ---- what a page does
    def context_of(self, frame): return f'context of {frame}' if frame in self.frame_probes else None

    def ax_of_or_none(self, backend): return next((n for n in self.ax.values() if n.get('backendDOMNodeId') == backend and not n.get('ignored')), None)

    def ax_of(self, backend): return next(n for n in self.ax.values() if n.get('backendDOMNodeId') == backend and not n.get('ignored'))

    def focus(self, backend):
        """The focus moves to the element: the browser's tree has it on that node and the document, and the page's probe names the element."""
        for n in self.ax.values():
            n['properties'] = [p for p in n.get('properties', []) if p['name'] != 'focused' or n.get('role', {}).get('value') == 'RootWebArea']
        target = self.ax_of(backend)
        if self.lag: self.stale[target['nodeId']] = target
        target['properties'] = [*target.get('properties', []), {'name': 'focused', 'value': {'type': 'booleanOrUndefined', 'value': True}}]
        self.probe['active'] = self.elements.index(backend)

    def set_attribute(self, backend, name, value, name_of_node=None):
        """An attribute that changes a name or a look (`title`, `class`, `style`): the snapshot has it, the page's probe names the element and says what attributes it has now, and the node the element has is named as it says."""
        dom = self.raw['dom']; doc = dom['documents'][0]; nodes = doc['nodes']
        i = nodes['backendNodeId'].index(backend); pairs = nodes['attributes'][i]
        held = {dom['strings'][pairs[k]]: k for k in range(0, len(pairs), 2)}
        dom['strings'].append(value); at = len(dom['strings']) - 1
        if name in held: pairs[held[name] + 1] = at
        else: dom['strings'].append(name); pairs.extend([len(dom['strings']) - 1, at])
        attrs = {dom['strings'][pairs[k]]: dom['strings'][pairs[k + 1]] for k in range(0, len(pairs), 2)}
        index = self.elements.index(backend); held = axtree.Dom(dom, self.raw['listeners'])
        texts = [held.get(t).get('bounds') for t in incremental.Reader.texts_below(held, backend)]      # where the text below it is drawn: where it was
        self.probe['soft'] = [*self.probe['soft'], [index, held.get(backend)['tag'], attrs, texts]]
        if name_of_node is not None:
            node = self.ax_of(backend); node['name'] = dict(node.get('name') or {'type': 'computedString'}, value=name_of_node)

    def type_into(self, backend, text):
        """A text typed into a field: its value, the text it holds, and the digest of the control."""
        node = self.ax_of(backend); node['value'] = {'type': 'string', 'value': text}
        inner = self.ax[node['childIds'][0]]; leaf = self.ax[inner['childIds'][0]]; leaf['name'] = dict(leaf['name'], value=text)
        self.probe['forms'][self.controls.index(backend)] += 1


def converted(raw, uids):
    twin = axtree.Converter(); twin.uids = dict(uids); twin.next_uid = len(uids)
    return twin.convert(copy_of(raw))


def tree_of(browser): return dict(browser.raw, ax=list(browser.ax.values()))


class Reading(unittest.TestCase):
    def setUp(self):
        self.browser = Browser(load()); self.reader = incremental.Reader()
        self.first = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.reader.read(self.browser.call_many, self.browser.context_of)      # a document just come is read whole once more, to see that its tree has settled
        self.link = next(b for b in self.browser.elements if b in {n.get('backendDOMNodeId') for n in self.browser.ax.values() if n.get('role', {}).get('value') == 'link'})
        self.field = 275      # the text field of the page, with "Ada" in it
        self.browser.calls.clear()

    def assertSameAsFromScratch(self, tree):
        self.assertEqual(tree, converted(tree_of(self.browser), self.reader.converter.uids))

    def test_the_first_read_is_a_full_read_and_is_the_tree_a_converter_makes(self):
        browser = Browser(load()); reader = incremental.Reader(); tree = reader.read(browser.call_many, browser.context_of)
        self.assertEqual((reader.cost['how'], reader.cost['reason']), ('full', 'first'))
        self.assertEqual(tree, axtree.Converter().convert(copy_of(browser.raw)))

    def test_a_document_just_come_is_read_whole_again_and_trusted_when_two_reads_give_the_same_shape_of_tree(self):
        browser = Browser(load()); reader = incremental.Reader(); reader.read(browser.call_many, browser.context_of)
        reader.read(browser.call_many, browser.context_of)
        self.assertEqual((reader.cost['how'], reader.cost['reason']), ('full', 'settling'))
        reader.read(browser.call_many, browser.context_of)
        self.assertEqual(reader.cost['how'], 'incremental')

    def test_a_tree_the_browser_is_still_making_is_read_whole_until_it_stops_changing_and_not_for_ever(self):
        """The browser makes some of its tree after the load and says nothing (an anonymous box under a <details>): the read that began it and the one after differ, and the incremental read would have kept the first."""
        browser = Browser(load()); reader = incremental.Reader(); reader.read(browser.call_many, browser.context_of)
        victim = next(n for n in browser.ax.values() if n.get('childIds') and n.get('role', {}).get('value') == 'list')
        dropped = victim['childIds'].pop()      # the second read has one node fewer, the third the same as the second
        reader.read(browser.call_many, browser.context_of); self.assertEqual(reader.cost['reason'], 'settling')
        reader.read(browser.call_many, browser.context_of); self.assertEqual(reader.cost['reason'], 'settling')      # the shape changed between the first and the second: not yet trusted
        reader.read(browser.call_many, browser.context_of); self.assertEqual(reader.cost['how'], 'incremental')

    def test_a_tree_that_never_stops_changing_is_trusted_after_so_many_reads(self):
        browser = Browser(load()); reader = incremental.Reader(); reader.read(browser.call_many, browser.context_of)
        victim = next(n for n in browser.ax.values() if len(n.get('childIds', [])) > incremental.MAX_SETTLE + 2)
        for _ in range(incremental.MAX_SETTLE + 1):
            victim['childIds'].pop(); reader.read(browser.call_many, browser.context_of)
        self.assertEqual(reader.unsettled, 0)

    def test_a_document_that_loaded_again_is_young_again(self):
        self.browser.probe['doc'] = 'd2'; self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'document')
        self.reader.read(self.browser.call_many, self.browser.context_of); self.assertEqual(self.reader.cost['reason'], 'settling')

    def test_a_page_that_only_moved_its_focus_is_read_again_without_the_whole_tree_or_the_snapshot_and_is_the_same_tree(self):
        self.browser.focus(self.link)
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental')
        self.assertFalse([m for m in self.browser.calls if m in FULL], self.browser.calls)
        self.assertEqual(tree['focusIx'], next(n['ix'] for n in tree['nodes'] if n.get('backendId') == self.link))
        self.assertSameAsFromScratch(tree)

    def test_the_nodes_keep_their_numbers_from_one_read_to_the_next(self):
        self.browser.focus(self.link)
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual([n['uid'] for n in tree['nodes']], [n['uid'] for n in self.first['nodes']])

    def test_a_value_typed_into_a_field_is_read_again_below_the_field(self):
        self.browser.type_into(self.field, 'Adam')
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental'); self.assertEqual(self.reader.cost['controls'], 1)
        field = next(n for n in tree['nodes'] if n.get('backendId') == self.field)
        self.assertEqual(field['value'], 'Adam')
        self.assertIn('Accessibility.getChildAXNodes', self.browser.calls)
        self.assertSameAsFromScratch(tree)

    def test_an_attribute_that_only_names_or_styles_an_element_is_read_again_alone_and_is_the_same_tree(self):
        """A link's `title` (the page-preview script of an encyclopaedia takes it away from the link that has the focus), a class: the element, the nodes above it and the page's attributes, and no snapshot."""
        link = next(n for n in self.browser.ax.values() if n.get('backendDOMNodeId') == self.link)
        self.browser.set_attribute(self.link, 'title', 'a tip', name_of_node=link.get('name', {}).get('value', '') + ' now')
        self.browser.focus(self.link)
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['how'], self.reader.cost['patched']), ('incremental', True), self.reader.cost)
        self.assertFalse([m for m in self.browser.calls if m in FULL])
        self.assertTrue(next(n for n in tree['nodes'] if n.get('backendId') == self.link)['name'].endswith(' now'))
        self.assertSameAsFromScratch(tree)

    def test_an_element_the_focus_passed_between_two_reads_is_read_again_with_the_ones_above_it(self):
        """The focus went through a link and on: the tree the browser keeps leaves the link's parent out now, and the page's layout is what it was. Only the links' `focusin` says where the focus has been."""
        wrapper = next(n for n in self.browser.ax.values() if self.link in [self.browser.ax[c].get('backendDOMNodeId') for c in n.get('childIds', [])] and n.get('backendDOMNodeId') in self.browser.elements)
        wrapper['ignored'] = True; wrapper['role'] = {'type': 'role', 'value': 'none'}
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental')      # nothing says the focus has been there: the reader cannot know (this is what `verify` is for)
        self.reader.visited({self.link})
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'full'); self.assertTrue(self.reader.cost['reason'].startswith('stale'), self.reader.cost)

    def test_the_nodes_the_focus_passed_are_read_again_once(self):
        self.reader.visited({self.link}); self.reader.read(self.browser.call_many, self.browser.context_of)
        self.browser.calls.clear(); self.reader.read(self.browser.call_many, self.browser.context_of)
        asked = [m for m in self.browser.calls if m == 'Accessibility.getPartialAXTree']
        self.assertLessEqual(len(asked), 2)

    def test_the_look_of_the_elements_the_focus_has_been_on_is_asked_of_the_page(self):
        """A :focus rule styled them while they had it and does not now: the probe is told which elements to describe, the one that had the focus at the last read and the ones named since."""
        asked = []
        original = self.browser.answer
        def answer(method, params):
            if method == 'Runtime.evaluate' and '__aeProbe' in params['expression'] and 'contextId' not in params: asked.append(params['expression'])
            return original(method, params)
        self.browser.answer = answer
        self.reader.visited({self.link}); self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertIn(f'window.__aeProbe(false, [-1, {self.browser.elements.index(self.link)}])', asked[0])

    def test_the_focus_having_been_on_a_great_many_elements_is_a_full_read(self):
        self.reader.visited(range(incremental.MAX_VISITS + 1)); self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'full')

    def test_a_class_that_shows_text_that_was_not_drawn_is_a_full_read(self):
        """The snapshot has no box and no style for text that was not drawn: what the page draws now cannot be told from what it has."""
        element = next(b for b in self.browser.elements if self.browser.ax_of_or_none(b) and incremental.Reader.texts_below(axtree.Dom(self.browser.raw['dom'], self.browser.raw['listeners']), b))
        self.browser.set_attribute(element, 'class', 'shown')
        self.browser.probe['soft'][-1][3][0] = None if self.browser.probe['soft'][-1][3][0] is not None else [0, 0, 5, 5]
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'full'); self.assertIn('text is drawn where it was not', self.reader.cost['reason'])

    def test_an_element_whose_class_changed_is_read_again_below_and_the_tree_made_again_when_its_shape_changed(self):
        parent = next(n for n in self.browser.ax.values() if n.get('role', {}).get('value') == 'list' and n.get('backendDOMNodeId') in self.browser.elements and len(n.get('childIds', [])) > 1)
        self.browser.set_attribute(parent['backendDOMNodeId'], 'class', 'hidden-items')
        self.browser.ax[parent['childIds'][0]]['ignored'] = True      # one of its items is left out of the tree now
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['how'], self.reader.cost['patched']), ('incremental', False), self.reader.cost)
        self.assertIn('Accessibility.getChildAXNodes', self.browser.calls)
        self.assertSameAsFromScratch(tree)

    def test_an_element_whose_class_changed_and_whose_subtree_did_not_is_patched(self):
        parent = next(n for n in self.browser.ax.values() if n.get('role', {}).get('value') == 'list' and n.get('backendDOMNodeId') in self.browser.elements and len(n.get('childIds', [])) > 1)
        self.browser.set_attribute(parent['backendDOMNodeId'], 'class', 'compact')
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['how'], self.reader.cost['patched']), ('incremental', True), self.reader.cost)
        self.assertSameAsFromScratch(tree)

    def test_an_element_that_is_gone_is_a_full_read(self):
        self.browser.probe['soft'] = None
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'an element that is gone')

    def test_a_node_named_by_a_field_whose_value_changed_is_read_again(self):
        """A list of suggestions named by the field it completes (aria-labelledby) says the words typed: it is read again with the field."""
        raw = load(); ax = {n['nodeId']: n for n in raw['ax']}
        suggestions = next(n for n in raw['ax'] if n.get('role', {}).get('value') in ('list', 'listbox') and n.get('backendDOMNodeId') in {x['backendDOMNodeId'] for x in raw['ax'] if 'backendDOMNodeId' in x} and 'name' in n)
        suggestions['properties'] = [*suggestions.get('properties', []), {'name': 'labelledby', 'value': {'type': 'nodeList', 'relatedNodes': [{'backendDOMNodeId': self.field}]}}]
        browser = Browser(raw); reader = incremental.Reader(); reader.read(browser.call_many, browser.context_of); reader.read(browser.call_many, browser.context_of)
        browser.type_into(self.field, 'Adam'); named = browser.ax[suggestions['nodeId']]; named['name'] = dict(named['name'], value='Adam')
        tree = reader.read(browser.call_many, browser.context_of)
        self.assertEqual(reader.cost['how'], 'incremental')
        self.assertEqual(next(n for n in tree['nodes'] if n.get('backendId') == suggestions['backendDOMNodeId'])['name'], 'Adam')
        self.assertEqual(tree, converted(tree_of(browser), reader.converter.uids))

    def test_a_page_read_whole_is_given_the_probe_it_had_and_not_a_second_walk_of_its_elements(self):
        self.browser.probe['muts'] += 1; self.browser.expressions.clear()
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'mutation')
        self.assertEqual(sum('window.__aeProbe(' in e for e in self.browser.expressions), 1)
        self.assertEqual(sum('window.__aeCommit' in e and '__aeProbe(' not in e for e in self.browser.expressions), 1)      # what it saw is taken as what was read
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental')      # the probe it was given is the baseline of the next

    def test_a_page_that_asks_for_a_full_read_every_time_is_read_without_the_probe_for_a_while_and_then_looked_at_again(self):
        for _ in range(incremental.FUTILE):
            self.browser.probe['layout'] = 5; self.reader.read(self.browser.call_many, self.browser.context_of)
            self.assertEqual(self.reader.cost['reason'], 'layout')
        self.browser.probe['layout'] = 0; self.browser.expressions.clear()
        self.reader.read(self.browser.call_many, self.browser.context_of)      # the probe is left out for one read
        self.assertEqual((self.reader.cost['how'], self.reader.cost['reason']), ('full', 'a page that keeps changing'))
        self.assertFalse([e for e in self.browser.expressions if '__aeProbe' in e])
        self.reader.read(self.browser.call_many, self.browser.context_of)      # the probe again: nothing to compare with, so whole
        self.assertEqual(self.reader.cost['reason'], incremental.AFTER_BACK_OFF)
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental')      # and a quiet page is read incrementally again

    def test_the_longer_a_page_keeps_changing_the_longer_the_probe_is_left_out(self):
        skips = []
        for _ in range(incremental.FUTILE + 3):
            self.reader.back_off('layout'); skips.append(self.reader.skip); self.reader.skip = 0
        self.assertEqual(skips[incremental.FUTILE - 1:], [1, 2, 4, 8])
        for _ in range(10): self.reader.back_off('layout')
        self.assertEqual(self.reader.skip, incremental.MAX_BACKOFF)

    def test_a_read_that_is_whole_because_of_what_the_page_is_and_not_what_it_does_does_not_count(self):
        for reason in ('first', 'document', 'loadComplete', 'keyframe'):
            self.reader.futile = 3; self.reader.back_off(reason); self.assertEqual(self.reader.futile, 0, reason)
        self.reader.futile = 3; self.reader.back_off(incremental.AFTER_BACK_OFF); self.assertEqual(self.reader.futile, 3)

    def test_a_node_described_by_an_element_whose_title_changed_is_read_again(self):
        """`<span id=tip title="">` described to a button by aria-describedby: the title is the description, and the button's AX node changes with it."""
        raw = load(); button = next(n for n in raw['ax'] if n.get('role', {}).get('value') == 'button')
        target = next(b for b in axtree.Dom(raw['dom'], raw['listeners']).elements if b != button['backendDOMNodeId'] and axtree.Dom(raw['dom'], raw['listeners']).get(b)['tag'] in ('li', 'p', 'span', 'h2'))
        button['properties'] = [*button.get('properties', []), {'name': 'describedby', 'value': {'type': 'nodeList', 'relatedNodes': [{'backendDOMNodeId': target}]}}]
        browser = Browser(raw); reader = incremental.Reader(); reader.read(browser.call_many, browser.context_of); reader.read(browser.call_many, browser.context_of)
        browser.set_attribute(target, 'title', 'Tooltip'); browser.ax[button['nodeId']]['description'] = {'type': 'computedString', 'value': 'Tooltip'}
        tree = reader.read(browser.call_many, browser.context_of)
        self.assertEqual(reader.cost['how'], 'incremental')
        self.assertEqual(next(n for n in tree['nodes'] if n.get('backendId') == button['backendDOMNodeId']).get('description'), 'Tooltip')
        self.assertEqual(tree, converted(tree_of(browser), reader.converter.uids))

    def test_a_frame_whose_script_context_went_while_the_read_was_made_is_a_full_read_and_not_a_lost_one(self):
        browser = Browser(load('frames', 'devtools')); reader = incremental.Reader(); read = lambda: reader.read(browser.call_many, browser.context_of)
        read(); read()
        original = browser.answer
        def answer(method, params):
            if method == 'Runtime.evaluate' and 'contextId' in params: raise RuntimeError('Cannot find context with specified id')
            return original(method, params)
        browser.answer = answer
        tree = read()
        self.assertEqual((reader.cost['how'], reader.cost['reason']), ('full', 'a frame changed')); self.assertTrue(tree['nodes'])

    def test_a_page_is_urgent_while_its_first_tree_is_read_and_not_after(self):
        browser = Browser(load()); reader = incremental.Reader(); seen = []
        original = browser.answer
        def answer(method, params):
            seen.append(reader.urgent_since is not None)
            return original(method, params)
        browser.answer = answer
        reader.read(browser.call_many, browser.context_of)
        self.assertTrue(any(seen)); self.assertIsNone(reader.urgent_since)
        seen.clear(); reader.read(browser.call_many, browser.context_of)      # the read that settles it is not urgent: the page has its tree
        self.assertFalse(any(seen))

    def test_a_heavy_page_that_is_still_loading_is_waited_for_before_it_is_read_whole(self):
        raw = load(); raw['page'] = dict(raw['page'], readyState='loading')
        browser = Browser(raw); reader = incremental.Reader(); real = incremental.HEAVY, incremental.LOAD_WAIT
        incremental.HEAVY = 10
        looks = []
        original = browser.answer
        def answer(method, params):
            if method == 'Runtime.evaluate' and 'readyState' in params['expression']:
                looks.append(1)
                if len(looks) == 3: browser.raw['page']['readyState'] = 'complete'
            return original(method, params)
        browser.answer = answer
        try: tree = reader.read(browser.call_many, browser.context_of)
        finally: incremental.HEAVY, incremental.LOAD_WAIT = real
        self.assertGreaterEqual(len(looks), 4)      # the page was looked at until it said it had loaded, and then read
        self.assertTrue(tree['nodes'][0]['docLoaded'])

    def test_a_light_page_that_is_still_loading_is_read_at_once_and_a_heavy_page_that_never_loads_is_read_after_the_wait(self):
        raw = load(); raw['page'] = dict(raw['page'], readyState='loading')
        browser = Browser(raw); reader = incremental.Reader(); looks = []
        original = browser.answer
        def answer(method, params):
            if method == 'Runtime.evaluate' and 'readyState' in params['expression']: looks.append(1)
            return original(method, params)
        browser.answer = answer
        reader.read(browser.call_many, browser.context_of)
        self.assertEqual(len(looks), 2)      # the first look, and the read's own
        real = incremental.HEAVY, incremental.LOAD_WAIT; incremental.HEAVY, incremental.LOAD_WAIT = 10, 0.3; looks.clear()
        try: incremental.Reader().read(browser.call_many, browser.context_of)
        finally: incremental.HEAVY, incremental.LOAD_WAIT = real
        self.assertGreater(len(looks), 3); self.assertLess(len(looks), 12)

    def test_a_change_to_the_document_is_a_full_read(self):
        self.browser.probe['muts'] += 1
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['how'], self.reader.cost['reason']), ('full', 'mutation'))
        self.assertIn('Accessibility.getFullAXTree', self.browser.calls)

    def test_a_new_document_is_a_full_read(self):
        self.browser.probe['doc'] = 'd2'
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'document')

    def test_a_box_that_moved_or_a_display_that_changed_is_a_full_read(self):
        self.browser.probe['layout'] = 3
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'layout')

    def test_a_page_without_a_probe_is_always_read_in_full(self):
        self.browser.probe = None
        self.browser.answer = (lambda original: lambda m, p: {'result': {}} if m == 'Runtime.evaluate' and '__aeProbe' in p['expression'] else original(m, p))(self.browser.answer)
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'no probe')

    def test_a_page_with_a_frame_is_read_in_full(self):
        self.browser.frames = ['child']
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'frames')

    def test_a_page_with_a_shadow_tree_is_read_in_full(self):
        self.browser.probe['shadows'] = 1
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'shadow tree')

    def test_the_browser_loading_a_document_is_a_full_read_once(self):
        self.reader.loaded()
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['reason'], 'loadComplete')
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental')

    def test_every_so_many_incremental_reads_the_page_is_read_in_full(self):
        for _ in range(incremental.MAX_RUN): self.reader.read(self.browser.call_many, self.browser.context_of); self.assertEqual(self.reader.cost['how'], 'incremental')
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['how'], self.reader.cost['reason']), ('full', 'keyframe'))
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'incremental')

    def test_an_ax_node_that_changed_its_children_is_a_full_read(self):
        """A node other than a control whose children are not the ones held: the tree changed shape, and what was held cannot be brought up to date from the node alone."""
        list_ = next(n for n in self.browser.ax.values() if n.get('role', {}).get('value') == 'list' and n.get('childIds'))
        self.browser.focus(self.link)
        self.browser.stale[list_['nodeId']] = dict(list_, childIds=list_['childIds'][:-1]); self.browser.probe['active'] = -1
        holder = self.browser.elements.index(list_['backendDOMNodeId']); self.browser.probe['active'] = holder
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'full'); self.assertTrue(self.reader.cost['reason'].startswith('stale'), self.reader.cost)

    def test_an_ax_node_the_page_did_not_have_is_a_full_read(self):
        node = next(n for n in self.browser.ax.values() if n.get('backendDOMNodeId') == self.link)
        self.browser.focus(self.link)
        self.browser.stale[node['nodeId']] = dict(node, nodeId='no-such-node')
        self.browser.answer = (lambda original: lambda m, p: {'nodes': [dict(node, nodeId='no-such-node')]} if m == 'Accessibility.getPartialAXTree' and p['backendNodeId'] == self.link else original(m, p))(self.browser.answer)
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['how'], 'full'); self.assertIn('did not have', self.reader.cost['reason'])


class Frames(unittest.TestCase):
    """A page with frames (fixtures/devtools/frames.json.gz: two iframes with a document each) is read again without them while each frame's probe says it has not changed."""
    def setUp(self):
        self.browser = Browser(load('frames', 'devtools')); self.reader = incremental.Reader(); self.read = lambda: self.reader.read(self.browser.call_many, self.browser.context_of)
        self.first = self.read(); self.read(); self.browser.calls.clear()
        self.frames = list(self.browser.raw['frames']); self.iframe = next(b for b in self.browser.elements if b == 30)

    def test_a_page_whose_frames_did_not_change_is_read_again_without_the_whole_tree(self):
        tree = self.read()
        self.assertEqual((self.reader.cost['how'], self.reader.cost['patched']), ('incremental', True), self.reader.cost)
        self.assertFalse([m for m in self.browser.calls if m in FULL])
        self.assertEqual(tree, converted(dict(self.browser.raw, ax=list(self.browser.ax.values())), self.reader.converter.uids))
        self.assertEqual([n['role'] for n in tree['nodes']], [n['role'] for n in self.first['nodes']])      # the frames' documents are in it

    def test_the_probe_of_each_frame_is_asked_in_the_context_of_that_frame(self):
        asked = []
        original = self.browser.answer
        def answer(method, params):
            if method == 'Runtime.evaluate' and 'contextId' in params: asked.append(params['contextId'])
            return original(method, params)
        self.browser.answer = answer; self.read()
        self.assertEqual(sorted(asked), sorted(f'context of {f}' for f in self.frames))

    def test_a_frame_whose_document_changed_is_a_full_read(self):
        self.browser.frame_probes[self.frames[0]]['muts'] += 1
        self.read()
        self.assertEqual((self.reader.cost['how'], self.reader.cost['reason']), ('full', 'a frame changed'))

    def test_a_frame_that_moved_its_focus_or_changed_its_layout_is_a_full_read(self):
        for key, value in (('active', 3), ('layout', 2), ('soft', [[0, 'a', {}]])):
            self.setUp(); self.browser.frame_probes[self.frames[1]][key] = value
            self.read()
            self.assertEqual((self.reader.cost['how'], self.reader.cost['reason']), ('full', 'a frame changed'), key)

    def test_a_frame_with_no_script_context_or_no_probe_is_always_a_full_read(self):
        del self.browser.frame_probes[self.frames[0]]      # the browser has no context for the frame
        for _ in range(2):
            self.read()
            self.assertEqual((self.reader.cost['how'], self.reader.cost['reason']), ('full', 'a frame changed'))

    def test_a_frame_that_came_or_went_is_a_full_read(self):
        self.browser.frames = ['new']; self.browser.frame_probes['new'] = dict(self.browser.probe)
        self.read()
        self.assertEqual(self.reader.cost['reason'], 'frames')

    def test_the_focus_on_a_frame_is_a_full_read(self):
        self.browser.probe['active'] = self.browser.elements.index(self.iframe)
        self.read()
        self.assertEqual(self.reader.cost['how'], 'full'); self.assertIn('the focus is on a frame', self.reader.cost['reason'])


class Style(unittest.TestCase):
    """A :focus rule changes the look of the focused element, of what is above it and below it, and of the text each holds: the held elements follow."""
    def setUp(self):
        self.raw = load('clickable'); self.dom = axtree.Dom(self.raw['dom'], self.raw['listeners'])
        self.reader = incremental.Reader(); self.reader.page = incremental.Page(self.raw['ax'], self.dom, {'forms': []}, None)
        self.link = next(b for b in self.dom.elements if self.dom.get(b)['tag'] == 'a' and any(self.dom.get(c).get('type') == 3 for c in self.dom.get(b)['children']))

    def look(self, **changed):
        values = [{'display': 'inline', 'color': 'rgb(1, 2, 3)', 'background-color': 'rgb(255, 221, 0)', 'font-family': 'x', 'font-size': '19px', 'font-weight': '700', 'font-style': 'italic', 'text-decoration-line': 'none', 'visibility': 'visible'}.get(k) for k in axtree.STYLES]
        return values

    def test_the_element_and_the_text_in_it_take_the_new_look(self):
        held = self.dom.get(self.link); text = next(self.dom.get(c) for c in held['children'] if self.dom.get(c).get('type') == 3)
        before = dict(held['style'])
        self.reader.restyle(self.reader.page, {'looks': [[self.dom.elements.index(self.link), 'a', self.look(), {}]]})
        for node in (held, text):
            self.assertEqual((node['style']['color'], node['style']['background-color'], node['style']['font-size'], node['style']['font-weight']), ('rgb(1, 2, 3)', 'rgb(255, 221, 0)', '19px', '700'))
        self.assertEqual((held['style']['display'], held['style']['visibility']), (before['display'], before['visibility']))      # what the probe's `layout` covers is not touched

    def test_an_element_that_is_not_the_one_the_page_numbers_is_a_full_read(self):
        with self.assertRaises(incremental.Stale): self.reader.restyle(self.reader.page, {'looks': [[self.dom.elements.index(self.link), 'section', self.look(), {}]]})

    def test_a_focus_chain_of_a_great_deal_is_a_full_read(self):
        with self.assertRaises(incremental.Stale): self.reader.restyle(self.reader.page, {'looks': None})

    def test_a_pseudo_element_the_page_does_not_describe_is_a_full_read(self):
        pseudo = next(b for b, v in self.dom.by_backend.items() if v.get('pseudo') and 'style' in v)
        parent = next(b for b, v in self.dom.by_backend.items() if pseudo in v['children'])
        with self.assertRaises(incremental.Stale): self.reader.restyle(self.reader.page, {'looks': [[self.dom.elements.index(parent), self.dom.get(parent)['tag'], self.look(), {}]]})

    def test_a_pseudo_element_takes_the_look_the_page_gives_it_and_the_element_does_not_give_it(self):
        pseudo = next(b for b, v in self.dom.by_backend.items() if v.get('pseudo') and 'style' in v)
        parent = next(b for b, v in self.dom.by_backend.items() if pseudo in v['children'])
        other = self.look(); other[1] = 'rgb(9, 9, 9)'
        self.reader.restyle(self.reader.page, {'looks': [[self.dom.elements.index(parent), self.dom.get(parent)['tag'], self.look(), {self.dom.get(pseudo)['pseudo']: other}]]})
        self.assertEqual(self.dom.get(pseudo)['style']['color'], 'rgb(9, 9, 9)'); self.assertEqual(self.dom.get(parent)['style']['color'], 'rgb(1, 2, 3)')


class Checking(unittest.TestCase):
    """`verify`: the page is read from scratch after an incremental read, and a difference is reported."""
    def setUp(self):
        self.browser = Browser(load()); self.reader = incremental.Reader(verify=True)
        self.reader.read(self.browser.call_many, self.browser.context_of); self.reader.read(self.browser.call_many, self.browser.context_of)      # and once more, for the tree to settle
        self.link = next(b for b in self.browser.elements if b in {n.get('backendDOMNodeId') for n in self.browser.ax.values() if n.get('role', {}).get('value') == 'link'})

    def test_a_read_that_is_the_same_as_one_from_scratch_is_verified(self):
        self.browser.focus(self.link)
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['how'], self.reader.cost['verified'], self.reader.mismatches), ('incremental', 'same', []))

    def test_a_node_the_reader_did_not_read_again_that_changed_is_reported_and_the_tree_from_scratch_is_used(self):
        """The page changed a checkbox's state with nothing to say so (no mutation, no digest): the held tree is wrong, and verify says so."""
        box = next(n for n in self.browser.ax.values() if n.get('role', {}).get('value') == 'checkbox')
        for p in box['properties']:
            if p['name'] == 'checked': p['value'] = {'type': 'tristate', 'value': 'true' if p['value']['value'] != 'true' else 'false'}
        self.browser.focus(self.link)
        tree = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['verified'], 'differs'); self.assertTrue(self.reader.mismatches)
        again = self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual(self.reader.cost['verified'], 'same')      # the page is held as the read from scratch says

    def test_a_tree_that_follows_the_focus_a_moment_late_is_not_a_difference(self):
        """The browser's tree is updated after the page's focus is: the first answer is the old one, and the reader reads once more."""
        self.browser.lag = True; self.browser.focus(self.link)
        first = self.browser.stale[self.browser.ax_of(self.link)['nodeId']]
        self.browser.stale = {first['nodeId']: dict(first, properties=[p for p in first['properties'] if p['name'] != 'focused'])}
        calls = {'n': 0}
        original = self.browser.answer
        def answer(method, params):
            if method == 'Accessibility.getPartialAXTree':
                calls['n'] += 1
                if calls['n'] > 1: self.browser.stale = {}
            return original(method, params)
        self.browser.answer = answer
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['verified'], self.reader.mismatches), ('same', []))

    def test_a_page_that_changed_while_it_was_checked_is_not_compared(self):
        original = self.browser.answer
        def answer(method, params):
            if method == 'Accessibility.getFullAXTree': self.browser.probe['muts'] += 1
            return original(method, params)
        self.browser.answer = answer; self.browser.focus(self.link)
        self.reader.read(self.browser.call_many, self.browser.context_of)
        self.assertEqual((self.reader.cost['verified'], self.reader.mismatches), ('the page changed', []))


def recording(name):
    with gzip.open(os.path.join(HERE, 'fixtures', 'incremental', f'{name}.jsonl.gz'), 'rt') as f: return [json.loads(line) for line in f]


class Recorded(unittest.TestCase):
    """Reads as they were had in Playwright 1.64.1's Chromium (156.0.8078.4) on Linux (fixtures/incremental, made with AE_CONVERSATION and `verify` on, so that each incremental read in them is one a read from scratch agreed with): the
    commands the reader sent, what the browser answered, what the browser had said since the last read, and the tree it made. The reader is given the same and must send the same commands and make the same tree."""
    def play(self, name):
        reader = incremental.Reader(); hows = []
        for row in recording(name):
            script = list(row['conversation'])
            def call_many(commands, script=script):
                expected, answers = script.pop(0)
                self.assertEqual(json.loads(json.dumps(commands)), expected)
                return copy_of(answers)
            for nodes in row['told']['hints']: reader.updated(nodes)
            reader.visited(row['told']['visits'])
            if row['told']['loaded']: reader.loaded()
            tree = reader.read(call_many, {frame: context for frame, context in row['contexts'].items()}.get)
            self.assertEqual(script, [], 'the reader asked for less than it did when the read was made')
            self.assertEqual(json.loads(json.dumps(tree)), row['tree'])
            hows.append(reader.cost['how'])
        return hows

    def test_a_form_filled_in_key_by_key_is_read_as_it_was(self):
        hows = self.play('form')
        self.assertEqual(hows[:2], ['full', 'full']); self.assertEqual(hows.count('incremental'), 16)
        self.assertEqual([row['verified'] for row in recording('form')[2:]].count('same'), 15)      # `verify` found each of these the same as a read from scratch

    def test_a_basket_that_counts_while_the_focus_is_on_its_button_is_read_as_it_was(self):
        hows = self.play('basket')
        self.assertEqual(hows.count('incremental'), 7); self.assertEqual([row['reason'] for row in recording('basket') if row['how'] == 'full'][2:], ['mutation'] * 3)      # the live region's text is a change of the document: a full read

    def test_the_recordings_have_what_the_reader_is_told_by_the_browser(self):
        rows = recording('form')
        self.assertTrue(any(row['told']['visits'] for row in rows)); self.assertTrue(any(row['told']['hints'] for row in rows))


class Differences(unittest.TestCase):
    def test_two_trees_that_are_the_same_have_none(self):
        tree = axtree.Converter().convert(load())
        self.assertEqual(incremental.differences(tree, tree), [])

    def test_a_field_that_differs_is_named_with_both_values(self):
        a = axtree.Converter().convert(load()); b = axtree.Converter().convert(load())
        b['nodes'][3]['name'] = 'other'
        found = incremental.differences(a, b)
        self.assertEqual(found[0][0], 3); self.assertEqual(found[0][2][0][0], 'name'); self.assertEqual(found[0][2][0][2], 'other')

    def test_a_different_number_of_nodes_is_a_difference(self):
        a = axtree.Converter().convert(load()); b = axtree.Converter().convert(load()); b['nodes'].pop()
        self.assertEqual(incremental.differences(a, b)[0][0], 'count')


if __name__ == '__main__': unittest.main()
