"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

The `large` project (A11-229, step 2) walks the five pages that the structure measurement left out for their size, with the corpus project's test: the same steps, so that what is read of them is read the way the others are."""
import json, os, unittest

SUITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sample-suite')
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'tree-source-structure')


def body(path):
    with open(path) as f: text = f.read()
    return text[text.index('const MAX_STOPS'):]


class SameWalk(unittest.TestCase):
    def test_the_large_test_is_the_corpus_test_from_its_constants_on(self):
        self.assertEqual(body(os.path.join(SUITE, 'tests', 'large', 'large.spec.ts')), body(os.path.join(SUITE, 'tests', 'corpus', 'corpus.spec.ts')))

    def test_the_project_walks_the_five_pages_the_structure_measurement_left_out_for_their_size(self):
        with open(os.path.join(SUITE, 'tests', 'large', 'pages.json')) as f: walked = [p['address'] for p in json.load(f)]
        with open(os.path.join(RESULTS, 'pages.json')) as f: rejected = {p['url']: p['tabStops'] for p in json.load(f)['rejected']}
        self.assertEqual(len(walked), 5)
        for address in walked: self.assertGreaterEqual(rejected[address], 700, address)      # from 705 tab stops (the Equality Act 2010's contents) to 1,770

    def test_the_project_has_the_corpus_viewport(self):
        with open(os.path.join(SUITE, 'base.config.ts')) as f: lines = {n: l.split('{ name:')[1].split(', testDir')[1] for l in f for n in ('corpus', 'large') if f'{{ name: "{n}"' in l}
        self.assertIn('use: { viewport: { width: 1008, height: 729 } }', lines['large']); self.assertIn('use: { viewport: { width: 1008, height: 729 } }', lines['corpus'])


if __name__ == '__main__': unittest.main()
