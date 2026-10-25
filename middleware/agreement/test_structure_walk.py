"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

The structure measurement (A11-229, step 2) takes the Q5 rule unchanged: its project walks its pages with the corpus project's test, and its pages are the ones the selection kept."""
import json, os, unittest

SUITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sample-suite')
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'tree-source-structure')


def body(path):
    with open(path) as f: text = f.read()
    return text[text.index('const MAX_STOPS'):]


class SameWalk(unittest.TestCase):
    def test_the_structure_test_is_the_corpus_test_from_its_constants_on(self):
        self.assertEqual(body(os.path.join(SUITE, 'tests', 'structure', 'structure.spec.ts')), body(os.path.join(SUITE, 'tests', 'corpus', 'corpus.spec.ts')))

    def test_the_project_walks_the_pages_the_selection_kept(self):
        with open(os.path.join(SUITE, 'tests', 'structure', 'pages.json')) as f: walked = [p['address'] for p in json.load(f)]
        with open(os.path.join(RESULTS, 'pages.json')) as f: kept = [p['address'] for p in json.load(f)['sample']]
        self.assertEqual(walked, kept)

    def test_the_projects_share_one_viewport_and_timeout(self):
        with open(os.path.join(SUITE, 'base.config.ts')) as f: lines = {n: l.split('{ name:')[1].split(', testDir')[1] for l in f for n in ('corpus', 'structure') if f'{{ name: "{n}"' in l}
        self.assertEqual(lines['corpus'], lines['structure'].replace('structure', 'corpus'))


if __name__ == '__main__': unittest.main()
