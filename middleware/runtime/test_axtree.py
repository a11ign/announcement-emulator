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


if __name__ == '__main__': unittest.main()
