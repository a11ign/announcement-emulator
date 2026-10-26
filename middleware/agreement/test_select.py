"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import collections, hashlib, json, os, sys, unittest

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


class Skip(unittest.TestCase):
    """A11-234: the next pages by the same rule, with the earlier round's pages left out."""

    def earlier(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'agreement', 'pages.json')) as f: return json.load(f)

    def test_every_page_an_earlier_round_listed_is_left_out_whether_it_was_kept_or_rejected(self):
        urls, _ = select_pages.candidates()
        earlier = self.earlier()
        left = select_pages.without(urls, [earlier])
        used = {p['url'] for p in earlier['sample'] + earlier['rejected']}
        self.assertEqual(len(used), 7)
        self.assertTrue(used.isdisjoint(left))
        self.assertEqual(len(left), len(urls) - 7)

    def test_the_order_of_the_rest_is_the_rules_order_so_the_next_pages_are_the_next_in_it(self):
        urls, _ = select_pages.candidates()
        left = select_pages.without(urls, [self.earlier()])
        self.assertEqual(left, [u for u in urls if u in set(left)])

    def test_with_nothing_to_skip_the_order_is_unchanged(self):
        self.assertEqual(select_pages.without(['a', 'b', 'c'], []), ['a', 'b', 'c'])
        self.assertEqual(select_pages.without(['a', 'b', 'c'], [{'sample': [{'url': 'b'}]}]), ['a', 'c'])
        self.assertEqual(select_pages.without(['a', 'b', 'c'], [{'rejected': [{'url': 'c'}]}, {'sample': [{'url': 'a'}]}]), ['b'])


class Plan(unittest.TestCase):
    def test_the_two_captures_of_a_page_go_to_two_boxes(self):
        import capture_fleet
        plan = capture_fleet.plan(['a', 'b', 'c'], ['w1', 'w2', 'w3'])
        for address in 'abc': self.assertEqual(len({w for a, k, w in plan if a == address}), 2)
        self.assertEqual(sorted(collections.Counter(w for _, _, w in plan).values()), [2, 2, 2])


if __name__ == '__main__': unittest.main()
