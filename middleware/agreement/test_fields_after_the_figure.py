"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fields_after_the_figure as ff
from test_compare_sources import A, reading


class Words(unittest.TestCase):
    def test_a_cell_spoken_without_its_header_words_is_words_missing(self):
        self.assertTrue(ff.words_missing('Made by, column 6, 2013 c. 22, link', 'column 6, 2013 c. 22, link'))
        self.assertTrue(ff.words_missing('row 25, Changes that affect, column 2, x, link', 'row 25, column 2, x, link'))

    def test_other_differences_are_not(self):
        self.assertFalse(ff.words_missing('column 6, x, link', 'column 6, y, link'))          # a word the fleet did not speak
        self.assertFalse(ff.words_missing('Made by, x, link', 'x, link'))                      # no row or column index
        self.assertFalse(ff.words_missing('Made by, column 6, x', None))
        self.assertFalse(ff.words_missing('column 6, x', 'column 6, x'))                       # nothing missing


class Discordant(unittest.TestCase):
    def test_each_side_is_counted_by_the_field_the_loser_differs_in(self):
        ext = reading('ext-linux', [('links', 0, 'a, link', 'a, link'), ('links', 1, 'b, link', None), ('links', 2, 'c, link', 'c, link')])
        dev = reading('devtools-linux', [('links', 0, 'a, link', 'a, clickable, link'), ('links', 1, 'b, link', 'b, link'), ('links', 2, 'c, link', 'c, link')])
        out = ff.discordant(ext, dev, {A: 'table'})
        self.assertEqual(dict(out['table']['extension only']), {'clickable': 1})
        self.assertEqual(dict(out['table']['devtools only']), {'no prediction': 1})
        self.assertEqual(out['all'], out['table'])

    def test_pages_the_extension_has_no_unit_of_are_counted_for_devtools_only(self):
        ext = reading('ext-linux', [('links', 0, 'a', 'a')])
        dev = reading('devtools-linux', [('links', 0, 'a', 'a')])
        other = 'https://z.test/'
        from test_compare_sources import row
        dev.main[(other, 'links', 0)] = row(0, 'Made by, column 2, x', 'column 2, x', 'links', address=other)
        dev.main[(other, 'links', 1)] = row(1, 'y', 'y', 'links', address=other)
        self.assertEqual(dict(ff.unread(ext, dev, {})), {other: [2, 1, 1]})
        [note] = ff.notes(ext, dev)
        self.assertEqual((note['reading'], note['address'], note['cause'], note['contains']), ('devtools-linux', other, 'conversion: name', 'Made by, column 2, x'))
        import compare_sources as cs
        self.assertTrue(cs.is_cause(note['cause']) and note['reason'])


if __name__ == '__main__': unittest.main()
