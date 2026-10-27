"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import collections, json, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_devtools_pages as mp

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', 'devtools-source')


class Pages(unittest.TestCase):
    def test_nineteen_pages_in_three_groups(self):
        sample = mp.pages()
        self.assertEqual(len(sample), 19)
        self.assertEqual(collections.Counter(p['group'] for p in sample), {'step 1': 6, 'step 2': 8, 'large': 5})

    def test_the_classes_are_the_structure_measurements_for_its_pages(self):
        sample = mp.pages()
        self.assertEqual(collections.Counter(p['class'] for p in sample if p['group'] == 'step 2'), {'table': 4, 'list': 4})
        self.assertEqual({p['class'] for p in sample if p['group'] == 'large'}, {'large'})

    def test_the_large_pages_are_the_ones_the_structure_measurement_left_out_for_their_size(self):
        for p in mp.pages():
            if p['group'] == 'large': self.assertGreaterEqual(p['tabStops'], 700, p['url'])

    def test_the_committed_page_list_is_what_the_script_writes(self):
        with open(os.path.join(RESULTS, 'pages.json')) as f: committed = json.load(f)
        self.assertEqual(committed['sample'], mp.pages())

    def test_each_page_is_walked_by_one_project_of_the_sample_suite(self):
        suite = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sample-suite', 'tests')
        walked = {}
        for project in ('corpus', 'structure', 'large'):
            with open(os.path.join(suite, project, 'pages.json')) as f: data = json.load(f)
            for p in (data if isinstance(data, list) else data['sample']): walked.setdefault(p.get('address') or p['url'], []).append(project)
        for p in mp.pages(): self.assertEqual(len(walked.get(p['url'], [])), 1, p['url'])


if __name__ == '__main__': unittest.main()
