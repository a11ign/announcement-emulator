"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common_units


def unit(i, ok): return (('https://x.test/p', 'links', i), {'ok': ok})


class Common(unittest.TestCase):
    def test_each_reading_is_counted_over_the_units_every_reading_has(self):
        a = dict([unit(0, True), unit(1, False), unit(2, True)])
        b = dict([unit(1, True), unit(2, True)])
        counts, pages = common_units.common({'a': a, 'b': b})
        self.assertEqual(counts, {'a': [1, 2], 'b': [2, 2]})
        self.assertEqual(pages, {'https://x.test/p': 2})

    def test_no_unit_in_common_and_no_reading_are_errors_not_a_division(self):
        with self.assertRaisesRegex(ValueError, 'no unit in common'): common_units.common({'a': dict([unit(0, True)]), 'b': dict([unit(1, True)])})
        with self.assertRaisesRegex(ValueError, 'at least one'): common_units.common({})


if __name__ == '__main__': unittest.main()
