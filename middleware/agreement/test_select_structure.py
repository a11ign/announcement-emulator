"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import hashlib, json, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import select_structure_pages as rule

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = {'tabStops': 100, 'headerCells': 3, 'largestTable': 40, 'tabStopsInCells': 20, 'tabStopsInItems': 0, 'largestList': 0, 'nestedLists': 0}
LIST = {'tabStops': 100, 'headerCells': 0, 'largestTable': 0, 'tabStopsInCells': 0, 'tabStopsInItems': 20, 'largestList': 20, 'nestedLists': 0}


class Classes(unittest.TestCase):
    def test_a_table_page_has_headers_a_big_table_and_tab_stops_in_its_cells(self):
        self.assertEqual(rule.classify(TABLE), 'table')
        for field in ('headerCells', 'largestTable', 'tabStopsInCells'):
            self.assertIsNone(rule.classify({**TABLE, field: TABLE[field] - 1}), field)

    def test_a_list_page_has_tab_stops_in_its_items_and_a_long_list_or_nested_lists(self):
        self.assertEqual(rule.classify(LIST), 'list')
        self.assertEqual(rule.classify({**LIST, 'largestList': 19, 'nestedLists': 3}), 'list')
        self.assertIsNone(rule.classify({**LIST, 'largestList': 19, 'nestedLists': 2}))
        self.assertIsNone(rule.classify({**LIST, 'tabStopsInItems': 19}))

    def test_a_page_with_more_than_500_tab_stops_is_neither(self):
        self.assertEqual(rule.classify({**TABLE, 'tabStops': 500}), 'table')
        self.assertIsNone(rule.classify({**TABLE, 'tabStops': 501}))
        self.assertIsNone(rule.classify({**LIST, 'tabStops': 501}))

    def test_a_page_that_is_both_is_a_table_page(self):
        self.assertEqual(rule.classify({**TABLE, **{k: v for k, v in LIST.items() if k.startswith('tabStopsInItems') or k in ('largestList',)}}), 'table')


class Selection(unittest.TestCase):
    def test_the_order_is_a_function_of_the_address_alone(self):
        keys = [int(hashlib.sha256(u.encode()).hexdigest(), 16) for u in rule.order(['https://b/', 'https://a/', 'https://c/'])]
        self.assertEqual(keys, sorted(keys))

    def test_the_first_of_each_class_are_kept_in_order_and_what_cannot_be_opened_is_listed(self):
        counts = {'t1': TABLE, 'l1': LIST, 't2': TABLE, 't3': TABLE, 'none': {**LIST, 'tabStopsInItems': 0}, 'l2': LIST, 'l3': LIST}
        def check(u):
            if u == 'gone': raise RuntimeError('timeout')
            return counts[u]
        kept, rejected = rule.select(['t1', 'gone', 'none', 'l1', 't2', 't3', 'l2', 'l3'], check, count=2)
        self.assertEqual([(k['url'], k['class']) for k in kept], [('t1', 'table'), ('l1', 'list'), ('t2', 'table'), ('l2', 'list')])
        self.assertEqual([r['url'] for r in rejected], ['gone', 'none', 't3'])
        self.assertIn('already kept', rejected[-1]['why'])

    def test_the_selection_stops_when_every_class_has_its_count(self):
        seen = []
        def check(u): seen.append(u); return TABLE if u.startswith('t') else LIST
        rule.select(['t1', 'l1', 't2', 'l2', 'never'], check, count=2)
        self.assertNotIn('never', seen)


class Candidates(unittest.TestCase):
    def test_the_candidates_are_fixed_addresses_without_duplicates(self):
        with open(os.path.join(HERE, '..', 'results', 'tree-source-structure', 'candidates.json')) as f: urls = [c['url'] for c in json.load(f)['candidates']]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertGreaterEqual(len(urls), 20)


if __name__ == '__main__': unittest.main()
