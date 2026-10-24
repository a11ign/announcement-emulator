"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import hashlib, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import select_pages


class Rule(unittest.TestCase):
    def test_the_candidates_are_the_old60_pages_less_the_seven_the_gate_would_not_compare(self):
        urls, excluded = select_pages.candidates()
        self.assertEqual(len(excluded), 7)
        self.assertEqual(len(urls), 53)
        self.assertTrue(excluded.isdisjoint(urls))

    def test_the_order_is_a_function_of_the_address_alone(self):
        urls, _ = select_pages.candidates()
        keys = [int(hashlib.sha256(u.encode()).hexdigest(), 16) for u in urls]
        self.assertEqual(keys, sorted(keys))

    def test_a_page_is_kept_by_its_dom_only(self):
        self.assertTrue(select_pages.passes({'tabStops': 10, 'textFields': 1}))
        self.assertFalse(select_pages.passes({'tabStops': 9, 'textFields': 1}))
        self.assertFalse(select_pages.passes({'tabStops': 40, 'textFields': 0}))

    def test_the_first_that_pass_are_taken_in_order_and_a_page_that_cannot_be_opened_is_listed(self):
        counts = {'a': {'tabStops': 50, 'textFields': 2}, 'b': {'tabStops': 3, 'textFields': 0}, 'c': {'tabStops': 20, 'textFields': 1}, 'd': {'tabStops': 20, 'textFields': 1}}
        def check(u):
            if u == 'x': raise RuntimeError('timeout')
            return counts[u]
        kept, rejected = select_pages.select(['a', 'x', 'b', 'c', 'd'], check, count=2)
        self.assertEqual([k['url'] for k in kept], ['a', 'c'])
        self.assertEqual([r['url'] for r in rejected], ['x', 'b'])
        self.assertIn('not opened', rejected[0]['why'])


if __name__ == '__main__': unittest.main()
