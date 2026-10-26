"""The DevTools tree source (axtree.py, A11-208): what it makes of recorded `Accessibility.getFullAXTree` + `DOMSnapshot` answers of three pages (fixtures/devtools, read from Chrome for Testing 155 on Linux).
The assertions are the node list `emu/ext2/tree.js` makes of the same pages (measured on 2026-10-24 by comparing the two, field by field), for the fields the emulator reads."""
import gzip, json, os, unittest

import axtree

HERE = os.path.dirname(os.path.abspath(__file__))


def convert(name):
    with gzip.open(os.path.join(HERE, 'fixtures', 'devtools', f'{name}.json.gz'), 'rt') as f: raw = json.load(f)
    return axtree.Converter().convert(raw)


def find(result, role, name=None):
    return next(n for n in result['nodes'] if n['role'] == role and (name is None or n.get('name') == name))


class SignUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.tree = convert('signup')

    def test_the_roles_and_names_are_those_of_the_extensions_tree(self):
        rows = [(n['depth'], n['role'], n.get('name')) for n in self.tree['nodes'] if n['role'] not in ('inlineTextBox', 'staticText')]
        self.assertEqual(rows[:6], [(0, 'rootWebArea', 'Create an account - Example shop'), (1, 'header', None), (2, 'navigation', 'Main'), (3, 'link', 'Home'), (3, 'link', 'Basket'), (1, 'main', None)])
        self.assertEqual([n.get('name') for n in self.tree['nodes'] if n['role'] == 'textField'], ['Full name', 'Email address'])
        self.assertEqual(len(self.tree['nodes']), 30)

    def test_a_node_names_the_dom_node_the_browser_holds_for_it_and_a_node_with_no_element_names_none(self):
        """The page's focus is matched to a node by this number (predict.py `match_focus`): the AX node's own `backendDOMNodeId`."""
        with gzip.open(os.path.join(HERE, 'fixtures', 'devtools', 'signup.json.gz'), 'rt') as f: raw = json.load(f)
        backend = {n['name']['value']: n['backendDOMNodeId'] for n in raw['ax'] if n.get('role', {}).get('value') == 'link' and 'backendDOMNodeId' in n}
        self.assertEqual(find(self.tree, 'link', 'Home')['backendId'], backend['Home'])
        self.assertNotEqual(backend['Home'], backend['Basket']); self.assertEqual(find(self.tree, 'link', 'Basket')['backendId'], backend['Basket'])
        box = next(n for n in self.tree['nodes'] if n['role'] == 'inlineTextBox')
        self.assertNotIn('backendId', box)

    def test_the_document_has_the_focus_until_something_takes_it(self):
        self.assertEqual(self.tree['focusIx'], 0)
        self.assertTrue(self.tree['nodes'][0]['state']['focused'])

    def test_a_link_and_its_text_are_linked_and_nothing_else_below_it(self):
        self.assertTrue(find(self.tree, 'link', 'Home')['state']['linked'])
        text = next(n for n in self.tree['nodes'] if n['role'] == 'staticText' and n.get('name') == 'Home')
        box = next(n for n in self.tree['nodes'] if n['role'] == 'inlineTextBox' and n.get('name') == 'Home')
        self.assertTrue(text['state']['linked'])
        self.assertNotIn('linked', box['state'])

    def test_a_field_is_editable_and_focusable_with_its_label_as_a_relation(self):
        field = find(self.tree, 'textField', 'Full name')
        self.assertEqual({k: v for k, v in field['state'].items()}, {'editable': True, 'focusable': True})
        self.assertEqual(field['htmlTag'], 'input'); self.assertEqual(field['inputType'], 'text')
        label = self.tree['nodes'][field['labelledByIx'][0]]
        self.assertEqual(label['role'], 'labelText'); self.assertIn(field['ix'], label['labelForIx'])

    def test_the_first_submit_button_of_a_form_is_its_default(self):
        self.assertTrue(find(self.tree, 'button', 'Create account')['state']['default'])

    def test_a_checkbox_says_whether_it_is_checked(self):
        self.assertEqual(find(self.tree, 'checkBox', 'Send me news')['checked'], 'false')

    def test_words_break_at_punctuation_as_the_extensions_do(self):
        self.assertEqual(axtree.word_bounds('Pick a section.'), ([0, 5, 7, 14], [4, 6, 14, 15]))

    def test_every_node_is_listed_by_its_parent_in_order_and_has_a_stable_uid(self):
        nodes = self.tree['nodes']
        for n in nodes:
            for k, c in enumerate(n.get('childrenIx', [])): self.assertEqual(nodes[c]['depth'], n['depth'] + 1); self.assertEqual(nodes[c]['indexInParent'], k)
        self.assertEqual(len({n['uid'] for n in nodes}), len(nodes))
        again = convert('signup')
        self.assertEqual([n['uid'] for n in again['nodes']], [n['uid'] for n in nodes])

    def test_the_uids_of_a_converter_hold_from_one_tree_to_the_next(self):
        with gzip.open(os.path.join(HERE, 'fixtures', 'devtools', 'signup.json.gz'), 'rt') as f: raw = json.load(f)
        converter = axtree.Converter()
        first, second = converter.convert(raw), converter.convert(raw)
        self.assertEqual([n['uid'] for n in first['nodes']], [n['uid'] for n in second['nodes']])


class Invalid(unittest.TestCase):
    def test_an_invalid_field_says_so_and_the_error_message_is_not_a_relation_the_extension_gives(self):
        tree = convert('validation-invalid')
        field = find(tree, 'textField', 'Email address')
        self.assertEqual(field['invalidState'], 'true')
        self.assertTrue(field['state']['focused']); self.assertEqual(tree['focusIx'], field['ix'])
        self.assertNotIn('errorMessageIx', field)


class Frames(unittest.TestCase):
    def test_an_iframe_holds_the_document_of_its_frame(self):
        tree = convert('frames')
        rows = [(n['depth'], n['role'], n.get('name')) for n in tree['nodes'] if n['role'] not in ('inlineTextBox', 'staticText')]
        self.assertEqual(rows, [(0, 'rootWebArea', 'Frames'), (1, 'main', None), (2, 'heading', 'Frames'), (2, 'iframe', 'Tabs example'), (3, 'rootWebArea', 'inner'), (4, 'button', 'Inner button'), (4, 'paragraph', None),
                                (2, 'iframe', 'Other'), (3, 'rootWebArea', 'Inner file'), (4, 'genericContainer', None), (5, 'link', 'Inner link')])
        inner = next(n for n in tree['nodes'] if n['role'] == 'rootWebArea' and n.get('name') == 'Inner file')
        self.assertTrue(inner['docUrl'].endswith('/inner.html'))
        self.assertEqual(tree['nodes'][0]['docUrl'].rsplit('/', 1)[1], 'frames.html')


# ------------------------------------------------------------------------------------------------ the fields the extension's tree holds (A11-229, step 1)
# fixtures/structure holds three small pages (middleware/sample-suite/pages/fields) twice: what the companion extension told the runtime while the sample suite's `fields` project walked them (`<page>.jsonl.gz`, AE_RECORD),
# and the answers of the DevTools port for the same page (`devtools-<page>.json.gz`, AE_RAW), both read in Playwright 1.64.1's Chromium (156.0.8078.4) on Linux. The extension's node list is the expected value.

def extension_tree(page):
    last = None
    with gzip.open(os.path.join(HERE, 'fixtures', 'structure', f'{page}.jsonl.gz'), 'rt') as f:
        for line in f:
            row = json.loads(line)
            if row['k'] == 'snap' and len(row['body']['nodes']) > 1: last = row['body']
    return last


def devtools_tree(page):
    with gzip.open(os.path.join(HERE, 'fixtures', 'structure', f'devtools-{page}.json.gz'), 'rt') as f: return axtree.Converter().convert(json.load(f))


def value_of(tree, node, field):
    """A node's field, with the nodes it names (`...Ix`) as what they are called, so that two trees are compared by what they say and not by the numbers they give the nodes."""
    value = node.get(field)
    if field.endswith('Ix') and isinstance(value, list): return [(tree['nodes'][i]['role'], tree['nodes'][i].get('name', '')) for i in value if i >= 0]
    return value


def comparable(field, value):
    """What of a field is compared: Chromium says `none` where there is no description source, and a node under the pointer is `hovered` and one beyond the window `offscreen` (the pointer and the window are the run's, not the page's)."""
    if field == 'descriptionFrom' and value == 'none': return None
    if field == 'state': return {k: v for k, v in value.items() if k not in ('hovered', 'offscreen')}
    return value


def parent_of(tree, node):
    i = node['ix']
    while i > 0:
        i -= 1
        if tree['nodes'][i]['depth'] == node['depth'] - 1: return tree['nodes'][i]


def differences(page, fields, only=lambda node: True):
    """[(role, name, field, extension's value, DevTools's value)] for each field of each node in which the two trees differ."""
    ext, dev = extension_tree(page), devtools_tree(page)
    out = []
    for e, d in zip(ext['nodes'], dev['nodes']):
        if not only(e): continue
        for field in fields:
            a, b = comparable(field, value_of(ext, e, field)), comparable(field, value_of(dev, d, field))
            if (a or None) != (b or None): out.append((e['role'], e.get('name', '')[:30], field, a, b))
    return out


PAGES = ('tables', 'lists', 'clickable')
IS_CELL = lambda node: node['role'] in axtree.CELL_ROLES
IS_TABLE = lambda node: node['role'] in axtree.TABLE_ROLES


class StructureTrees(unittest.TestCase):
    def test_the_two_trees_of_a_page_have_the_same_nodes_in_the_same_order(self):
        for page in PAGES:
            ext, dev = extension_tree(page), devtools_tree(page)
            self.assertEqual([(n['depth'], n['role'], n.get('name', '')) for n in dev['nodes']], [(n['depth'], n['role'], n.get('name', '')) for n in ext['nodes']], page)

    def test_a_native_select_and_a_grid_cell_are_the_roles_chromium_156_numbers_them(self):
        """roles.json is Chromium 155's enum: 209 and 212 are in neither, and a node with a role of no name made the emulator speak a select as a list and read a grid cell as unknown."""
        for page in PAGES: self.assertEqual([n['role'] for n in devtools_tree(page)['nodes'] if n['role'] == 'unknown'], [], page)
        self.assertEqual(find(devtools_tree('tables'), 'gridCell', 'Ada')['role'], 'gridCell')
        self.assertEqual(find(devtools_tree('lists'), 'comboBoxSelect', 'Fruit')['role'], 'comboBoxSelect')

    def test_a_row_group_is_not_a_node_of_the_extensions_tree_and_its_rows_belong_to_the_table(self):
        tree = devtools_tree('tables')
        self.assertNotIn('rowGroup', [n['role'] for n in tree['nodes']])
        table = find(tree, 'table', 'Prices by size')
        self.assertEqual([tree['nodes'][c]['role'] for c in table['childrenIx']], ['caption', 'row', 'row', 'row'])


class Tables(unittest.TestCase):
    def test_each_cell_says_where_it_is_and_how_far_it_spans_as_the_extension_does(self):
        for fields in (('tableCellRowIndex', 'tableCellColumnIndex'), ('tableCellRowSpan', 'tableCellColumnSpan')):
            self.assertEqual(differences('tables', fields, IS_CELL), [], fields)

    def test_a_cell_beside_a_cell_that_spans_rows_takes_the_next_free_column(self):
        """'Choir' is the second cell of its row and sits in column 1: column 0 holds 'Room 1', whose rowspan is 2."""
        tree = devtools_tree('tables')
        room = find(tree, 'rowHeader', 'Room 1'); choir = find(tree, 'cell', 'Choir'); rehearsal = find(tree, 'cell', 'Rehearsal')
        self.assertEqual((room['tableCellRowSpan'], choir['tableCellRowIndex'], choir['tableCellColumnIndex']), (2, 3, 1))
        self.assertEqual((rehearsal['tableCellColumnIndex'], rehearsal['tableCellColumnSpan']), (2, 2))

    def test_the_rows_and_columns_of_a_table_are_counted_without_those_of_a_table_in_one_of_its_cells(self):
        self.assertEqual(differences('tables', ('tableRowCount', 'tableColumnCount'), IS_TABLE), [])
        tree = devtools_tree('tables')
        prices = find(tree, 'table', 'Prices by size'); grouped = next(n for n in tree['nodes'] if n['role'] == 'table' and n.get('htmlId') == 'grouped'); inner = next(n for n in tree['nodes'] if n['role'] == 'table' and n.get('htmlId') == 'inner')
        self.assertEqual([(t['tableRowCount'], t['tableColumnCount']) for t in (prices, grouped, inner)], [(3, 3), (4, 2), (3, 2)])

    def test_the_index_the_page_gives_a_row_or_a_cell_is_kept_and_the_next_cell_follows_it(self):
        self.assertEqual(differences('tables', ('tableCellAriaRowIndex', 'tableCellAriaColumnIndex'), IS_CELL), [])
        tree = devtools_tree('tables')
        amount = find(tree, 'cell', '$20')
        self.assertEqual((amount['tableCellRowIndex'], amount['tableCellAriaRowIndex'], amount['tableCellColumnIndex'], amount['tableCellAriaColumnIndex']), (1, 41, 1, 5))
        compiler = find(tree, 'gridCell', 'Compiler')      # no aria-colindex of its own: it follows 'Grace', which has 1
        self.assertEqual(compiler['tableCellAriaColumnIndex'], 2)

    def test_a_cell_lists_the_header_words_of_its_column_and_of_its_row(self):
        """What NVDA speaks after `row N` and `column N`: every column header that covers the cell's first column and every row header that covers its first row, in the order they come, a header cell among its own."""
        self.assertEqual(differences('tables', ('tableCellColumnHeadersIx', 'tableCellRowHeadersIx'), IS_CELL), [])
        tree = devtools_tree('tables')
        names = lambda cell, field: [tree['nodes'][i]['name'] for i in cell.get(field, [])]
        yoga = find(tree, 'cell', 'Yoga')
        self.assertEqual((names(yoga, 'tableCellColumnHeadersIx'), names(yoga, 'tableCellRowHeadersIx')), (['Monday', 'AM'], ['Room 1']))
        self.assertEqual(names(find(tree, 'cell', 'Choir'), 'tableCellRowHeadersIx'), ['Room 1'])      # the row header spans two rows
        self.assertEqual(names(find(tree, 'cell', '$4'), 'tableCellColumnHeadersIx'), ['Price'])
        self.assertEqual(names(find(tree, 'columnHeader', 'Size'), 'tableCellColumnHeadersIx'), ['Size'])

    def test_a_span_is_clamped_to_the_table_so_that_a_page_cannot_make_the_grid_huge(self):
        """HTML allows rowspan 65534 and colspan 1000: one cell of both would have filled 65 million slots."""
        cell = {'role': 'cell', '_dom': {'attrs': {'rowspan': '65534', 'colspan': '5000'}}}
        nodes = [{'role': 'table', '_dom': {'attrs': {}}}, {'role': 'row', '_dom': {'attrs': {}}}, cell]
        axtree.Converter().table(0, nodes, {0: [1], 1: [2]}, ['table', 'row', 'cell'])
        self.assertEqual((cell['tableCellRowSpan'], cell['tableCellColumnSpan'], nodes[0]['tableRowCount'], nodes[0]['tableColumnCount']), (1, 1000, 1, 1000))

    def test_a_row_span_ends_at_its_row_group_and_rowspan_0_reaches_it(self):
        """HTML clamps a span to the row group (<thead>, <tbody>) its row is in: a header cell with rowspan 2 over a one-row <thead> does not take a slot in the <tbody>, and rowspan 0 means "to the end of the group"."""
        def cell(**attrs): return {'role': 'cell', '_dom': {'attrs': attrs}}
        def row(group=None): return {'role': 'row', '_dom': {'attrs': {}, **({'group': group} if group else {})}}
        a, b, c = cell(rowspan='2', colspan='2px'), cell(), cell(rowspan='0')
        nodes = [{'role': 'table', '_dom': {'attrs': {}}}, row('head'), a, row('body'), b, row('body'), c]
        axtree.Converter().table(0, nodes, {0: [1, 3, 5], 1: [2], 3: [4], 5: [6]}, ['table', 'row', 'cell', 'row', 'cell', 'row', 'cell'])
        self.assertEqual((a['tableCellRowSpan'], a['tableCellColumnSpan'], b['tableCellColumnIndex'], c['tableCellRowSpan']), (1, 2, 0, 1))
        d = cell(rowspan='0')
        nodes = [{'role': 'table', '_dom': {'attrs': {}}}, row('body'), d, row('body'), cell(), row('body'), cell()]
        axtree.Converter().table(0, nodes, {0: [1, 3, 5], 1: [2], 3: [4], 5: [6]}, ['table', 'row', 'cell', 'row', 'cell', 'row', 'cell'])
        self.assertEqual(d['tableCellRowSpan'], 3)
        self.assertEqual(nodes[4]['tableCellColumnIndex'], 1)

    def test_a_table_is_named_from_its_caption(self):
        self.assertEqual(find(devtools_tree('tables'), 'table', 'Prices by size')['nameFrom'], 'caption')


class Sets(unittest.TestCase):
    def test_the_position_in_a_set_and_its_size_are_the_extensions_for_every_node(self):
        for page in PAGES: self.assertEqual(differences(page, ('posInSet', 'setSize')), [], page)

    def test_the_numbers_the_page_gives_are_used_and_a_marker_is_not_an_item(self):
        tree = devtools_tree('lists')
        first, second = [n for n in tree['nodes'] if n['role'] == 'listItem' and n.get('posInSet') in (31, 32)]
        self.assertEqual((first['posInSet'], first['setSize'], second['posInSet'], second['setSize']), (31, 90, 32, 90))
        self.assertTrue(all('posInSet' not in n for n in tree['nodes'] if n['role'] == 'listMarker'))
        self.assertEqual(find(tree, 'tree', 'Files')['setSize'], 2)

    def test_a_list_nested_in_an_item_is_a_set_of_its_own(self):
        tree = devtools_tree('lists')
        pear = parent_of(tree, next(n for n in tree['nodes'] if n['role'] == 'staticText' and n.get('name') == 'Pear'))
        self.assertEqual((pear['role'], pear['posInSet'], pear['setSize']), ('listItem', 2, 3))

    def test_native_radio_buttons_are_a_group_by_their_name_within_their_form(self):
        tree = devtools_tree('lists')
        radios = [(n['posInSet'], n['setSize']) for n in tree['nodes'] if n['role'] == 'radioButton' and n['htmlTag'] == 'input']
        self.assertIn((1, 2), radios); self.assertIn((2, 2), radios)      # 'Card' and 'Cash' in the form
        self.assertIn((1, 1), radios)      # the radio of that name outside the form is a group of its own

    def test_a_select_gives_the_position_of_its_selected_option_in_its_options(self):
        tree = devtools_tree('lists')
        large = find(tree, 'comboBoxSelect', 'Size of drink')
        self.assertEqual((large['posInSet'], large['setSize']), (3, 3))


class Edges(unittest.TestCase):
    """Cases the recorded pages do not hold, found by reading the diff."""
    def test_a_role_number_is_taken_for_a_role_only_where_the_protocol_names_the_node_as_it_did(self):
        self.assertEqual(axtree.role_of({'chromeRole': {'value': 212}, 'role': {'value': 'gridcell'}}), 'gridCell')
        self.assertEqual(axtree.role_of({'chromeRole': {'value': 212}, 'role': {'value': 'something else'}}), 'unknown')
        self.assertEqual(axtree.role_of({'chromeRole': {'value': 13}, 'role': {'value': 'cell'}}), 'cell')

    def test_radio_buttons_of_one_name_in_two_documents_are_two_groups(self):
        roles = ['rootWebArea', 'radioButton', 'rootWebArea', 'radioButton']
        nodes = [{'_dom': {'tag': 'input', 'form': None, 'attrs': {'name': 'q'}}} for _ in roles]
        axtree.Converter.radio_groups(nodes, roles, {1: 0, 3: 2})
        self.assertEqual([(nodes[i]['posInSet'], nodes[i]['setSize']) for i in (1, 3)], [(1, 1), (1, 1)])

    def test_a_contenteditable_link_is_still_a_link_and_an_editing_host_activates(self):
        d = {'tag': 'a'}
        self.assertEqual(axtree.Converter.action_verb('link', d, {'contenteditable': 'true', 'href': '#'}, None, {}), 'jump')
        self.assertEqual(axtree.Converter.action_verb('genericContainer', {'tag': 'div'}, {'contenteditable': 'true'}, None, {}), 'activate')


class Clickable(unittest.TestCase):
    def test_a_node_is_clickable_when_the_extensions_is_and_not_otherwise(self):
        """NVDA says "clickable" for the verb `click` and for no other: the 'clickable' units of step 2's measurement were a <label> with no listener of the page's own, flagged by DOMSnapshot because the browser acts on a click there."""
        for page in PAGES:
            ext, dev = extension_tree(page), devtools_tree(page)
            wrong = [(e['role'], e.get('name', '')[:30], e.get('defaultActionVerb'), d.get('defaultActionVerb')) for e, d in zip(ext['nodes'], dev['nodes']) if (e.get('defaultActionVerb') == 'click') != (d.get('defaultActionVerb') == 'click')]
            self.assertEqual(wrong, [], page)

    def test_a_label_is_clickable_only_when_the_page_listens_for_a_click_on_it(self):
        tree = devtools_tree('lists')
        verbs = {n.get('htmlId'): n['defaultActionVerb'] for n in tree['nodes'] if n['role'] == 'labelText' and n.get('htmlId')}
        self.assertEqual((verbs['clicklabel'], verbs['plainlabel']), ('click', 'clickAncestor'))

    def test_the_labels_of_a_form_are_not_clickable(self):
        """The label of a field has no listener of the page's own: it was `click` (and "clickable" with the field's name in front of it) for every label of every form (fixtures/devtools/signup)."""
        self.assertEqual({n['defaultActionVerb'] for n in convert('signup')['nodes'] if n['role'] == 'labelText'}, {'clickAncestor'})

    def test_the_verb_of_a_role_is_the_one_chromium_gives_it(self):
        """A radio button checks (it was `select`), a tab on a button is clicked and a menu item selected, a disclosure triangle presses, a native select opens."""
        tree = devtools_tree('clickable')
        verbs = {n.get('htmlId'): n['defaultActionVerb'] for n in tree['nodes'] if n.get('htmlId')}
        ext = {n.get('htmlId'): n.get('defaultActionVerb') for n in extension_tree('clickable')['nodes'] if n.get('htmlId')}
        for ident in ('in-radio-own', 'r-mi-radio', 'r-toggle', 'sum-plain', 'sel-plain', 'opt', 'r-slider', 'r-spin', 'd-role-tab-own', 'in-chk-own', 'btn-own', 'a-href', 'ta-plain', 'in-num'):
            self.assertIn(ident, verbs, ident)
            if ext[ident]: self.assertEqual(verbs[ident], ext[ident], ident)      # where the extension names a verb (it names none for a node nothing acts on)
        self.assertEqual(verbs['in-radio-own'], 'check'); self.assertEqual(verbs['r-slider'], 'click'); self.assertEqual(verbs['sum-plain'], 'press')

    def test_the_labels_the_page_listens_to_are_matched_to_the_snapshots_by_their_order(self):
        strings = ['label', 'div', 'LABEL']
        snapshot = {'strings': strings, 'documents': [{'nodes': {'nodeName': [0, 1, 2, 1], 'backendNodeId': [10, 11, 12, 13], 'parentIndex': [-1, 0, 0, 1], 'isClickable': {'index': [0, 2]}}}]}
        answer = lambda flags: {'result': {'value': json.dumps(flags)}}
        self.assertEqual(axtree.label_listeners(answer([0, 1]), snapshot), [12])
        self.assertEqual(axtree.label_listeners(answer([1, 0]), snapshot), [10])
        self.assertEqual(axtree.label_listeners(answer([1]), snapshot), [], 'a page that changed between the two questions: no label is taken for another')
        self.assertEqual(axtree.label_listeners({'exceptionDetails': {}}, snapshot), [])

    def test_a_label_in_a_shadow_root_is_not_one_the_page_script_counted(self):
        strings = ['label', 'div']
        nodes = {'nodeName': [1, 1, 0, 0], 'backendNodeId': [10, 11, 12, 13], 'parentIndex': [-1, 0, 1, 0], 'shadowRootType': {'index': [1], 'value': [0]}}
        self.assertEqual(axtree.label_listeners({'result': {'value': '[1]'}}, {'strings': strings, 'documents': [{'nodes': nodes}]}), [13])


class Values(unittest.TestCase):
    def test_a_field_holds_the_value_the_page_gave_it_and_a_range_the_words_the_page_gave_it(self):
        self.assertEqual(differences('lists', ('value',)), [])
        tree = devtools_tree('lists')
        self.assertEqual(find(tree, 'textField', 'Preset')['value'], 'preset')
        self.assertEqual(find(tree, 'slider', 'Volume')['value'], 'three of ten')

    def test_the_description_of_a_node_and_where_it_comes_from_are_the_extensions(self):
        """A button's title, an aria-description, two aria-describedby (one of them hidden), an image's title, a title the same as the name and a description that holds a link: all as the extension has them."""
        norm = lambda d: [(a, b, f, None if v == 'none' else v, None if w == 'none' else w) for a, b, f, v, w in d]
        self.assertEqual(norm(differences('lists', ('description', 'descriptionFrom'))), [])
        tree = devtools_tree('lists')
        self.assertEqual((find(tree, 'button', 'Save')['description'], find(tree, 'button', 'Save')['descriptionFrom']), ('Saves your work', 'title'))
        self.assertEqual(find(tree, 'button', 'Share')['descriptionFrom'], 'ariaDescription')

    def test_a_link_goes_somewhere_only_when_it_has_an_address(self):
        """An anchor with no href and a role=link are not linked: only the ones that go somewhere (and their text) are."""
        self.assertEqual(differences('clickable', ('state',)), [])
        tree = devtools_tree('clickable')
        self.assertNotIn('linked', find(tree, 'link', 'Own anchor without href')['state'])
        self.assertTrue(find(tree, 'link', 'Plain link')['state']['linked'])


if __name__ == '__main__': unittest.main()


# ------------------------------------------------------------------------------------------------ a list of nodes brought up to date (A11-229, step 2)
# `Converter.patch` makes again the nodes that can have changed and takes the rest of the list as it was; the list it gives is the one `convert` gives of the page as it is now.

class Patching(unittest.TestCase):
    def setUp(self):
        with gzip.open(os.path.join(HERE, 'fixtures', 'structure', 'devtools-lists.json.gz'), 'rt') as f: self.raw = json.load(f)
        self.converter = axtree.Converter(); self.dom = axtree.Dom(self.raw['dom'], self.raw['listeners']); self.raw['_dom'] = self.dom
        self.first = self.converter.convert(self.raw, retain=True)
        self.ax = {n['nodeId']: n for n in self.raw['ax']}

    def now(self, changed=(), page=None, viewport=None):
        """The list `patch` makes after the AX nodes in `changed` were replaced, and the list `convert` makes of the same page."""
        page = page or self.raw['page']; viewport = viewport or self.raw['viewport']
        ax = dict(self.ax); ax.update({n['nodeId']: n for n in changed})
        patched = self.converter.patch(ax, {n['nodeId'] for n in changed}, set(), self.dom, page, viewport)
        twin = axtree.Converter(); twin.uids = dict(self.converter.uids); twin.next_uid = self.converter.next_uid
        whole = twin.convert(dict(self.raw, ax=list(ax.values()), page=page, viewport=viewport))
        return patched, whole

    def node(self, role, name=None):
        return next(n for n in self.ax.values() if n.get('role', {}).get('value') == role and (name is None or n.get('name', {}).get('value') == name))

    def focused(self, node, on=True):
        props = [p for p in node.get('properties', []) if p['name'] != 'focused']
        return dict(node, properties=[*props, {'name': 'focused', 'value': {'type': 'booleanOrUndefined', 'value': True}}] if on else props)

    def test_nothing_changed_is_the_list_that_was_made(self):
        patched, whole = self.now()
        self.assertEqual(patched, whole); self.assertEqual(patched['nodes'], self.first['nodes'])

    def test_the_focus_moved_from_one_node_to_another(self):
        old = next(n for n in self.ax.values() if any(p['name'] == 'focused' for p in n.get('properties', [])) and n['role']['value'] != 'RootWebArea')
        new = self.node('link')
        patched, whole = self.now([self.focused(old, on=False), self.focused(new)])
        self.assertEqual(patched, whole)
        self.assertEqual(patched['focusIx'], next(n['ix'] for n in patched['nodes'] if n.get('backendId') == new['backendDOMNodeId']))
        self.assertEqual(sum(1 for n in patched['nodes'] if n['state'].get('focused')), 1)

    def test_the_nodes_that_did_not_change_are_the_ones_that_were_made(self):
        patched, whole = self.now([self.focused(self.node('link'))])
        same = sum(1 for a, b in zip(patched['nodes'], self.first['nodes']) if a is b)
        self.assertGreater(same, len(self.first['nodes']) - 12)

    def test_the_name_of_a_node_that_is_no_ones_text_can_change(self):
        link = self.node('link'); renamed = dict(link, name=dict(link['name'], value='a new name'))
        patched, whole = self.now([renamed])
        self.assertEqual(patched, whole)
        self.assertEqual(next(n for n in patched['nodes'] if n.get('backendId') == link['backendDOMNodeId'])['name'], 'a new name')

    def test_the_text_of_a_text_is_the_marks_of_every_node_above_it_and_is_not_patched(self):
        text = self.node('StaticText', next(n['name']['value'] for n in self.ax.values() if n.get('role', {}).get('value') == 'StaticText' and n['name']['value'].strip()))
        with self.assertRaises(axtree.Unpatchable): self.now([dict(text, name=dict(text['name'], value='other words'))])

    def test_a_field_whose_text_changed_is_not_patched(self):
        field = self.node('textbox'); 
        with self.assertRaises(axtree.Unpatchable): self.now([dict(field, value={'type': 'string', 'value': 'changed'})])

    def test_a_state_other_than_the_focus_is_not_patched(self):
        box = self.node('checkbox'); flipped = dict(box, properties=[dict(p, value=dict(p['value'], value='true' if p['value']['value'] != 'true' else 'false')) if p['name'] == 'checked' else p for p in box['properties']])
        with self.assertRaises(axtree.Unpatchable): self.now([flipped])

    def test_the_page_scrolled(self):
        viewport = dict(self.raw['viewport'], pageY=self.raw['viewport'].get('pageY', 0) + 2000)
        patched, whole = self.now(viewport=viewport)
        self.assertEqual(patched, whole)
        self.assertNotEqual([n['state'].get('offscreen') for n in patched['nodes']], [n['state'].get('offscreen') for n in self.first['nodes']])

    def test_the_address_of_the_page_changed_without_a_load(self):
        patched, whole = self.now(page=dict(self.raw['page'], url=self.raw['page']['url'] + '#route'))
        self.assertEqual(patched, whole); self.assertTrue(patched['nodes'][0]['docUrl'].endswith('#route'))

    def test_the_caret_moved_in_the_field_that_has_the_focus(self):
        patched, whole = self.now(page=dict(self.raw['page'], caret=[1, 2]))
        self.assertEqual(patched, whole)

    def test_a_look_that_changed_is_patched_where_the_style_was_set(self):
        link = self.node('link'); backend = link['backendDOMNodeId']
        self.dom.get(backend)['style']['color'] = 'rgb(1, 2, 3)'
        patched = self.converter.patch(self.ax, set(), {backend}, self.dom, self.raw['page'], self.raw['viewport'])
        twin = axtree.Converter(); twin.uids = dict(self.converter.uids); twin.next_uid = self.converter.next_uid
        self.assertEqual(patched, twin.convert(self.raw))
        self.assertEqual(next(n for n in patched['nodes'] if n.get('backendId') == backend)['color'], 0xff010203)

    def test_a_page_that_was_not_converted_with_retain_cannot_be_patched(self):
        converter = axtree.Converter(); converter.convert(self.raw)
        with self.assertRaises(axtree.Unpatchable): converter.patch(self.ax, set(), set(), self.dom, self.raw['page'], self.raw['viewport'])


class MarkingText(unittest.TestCase):
    """Where the words and sentences of a text start are found once for each distinct text (a container holds the text of what is in it, so the same string comes up at each level of the tree) and the table of them is bounded."""
    def setUp(self): axtree.MARKS.clear(); axtree.MARKED[0] = 0

    def test_the_marks_of_a_text_are_the_same_the_second_time_and_a_caller_may_change_what_it_is_given(self):
        first = axtree.word_bounds('Pick a section. Then go.')
        first[0].append(99)
        self.assertEqual(axtree.word_bounds('Pick a section. Then go.'), ([0, 5, 7, 14, 16, 21, 23], [4, 6, 14, 15, 20, 23, 24]))
        sentences = axtree.sentence_starts('Pick a section. Then go.'); sentences.append(99)
        self.assertEqual(axtree.sentence_starts('Pick a section. Then go.'), [0, 16])

    def test_a_long_text_is_not_kept(self):
        axtree.word_bounds('word ' * (axtree.MARKED_LONGEST // 4)); self.assertEqual(len(axtree.MARKS), 0)

    def test_the_table_is_emptied_before_it_holds_more_than_its_limit(self):
        for i in range(axtree.MARKED_LIMIT // 1000 + 5): axtree.word_bounds(f'{i} ' + 'x' * 998)
        self.assertLessEqual(axtree.MARKED[0], axtree.MARKED_LIMIT)
        self.assertEqual(axtree.MARKED[0], sum(len(key[1]) for key in axtree.MARKS))
