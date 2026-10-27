"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge_reports as mr
import measure


def report(*addresses): return {'suites': [{'title': 'x.spec.ts', 'specs': [{'title': f'keyboard walk of {a}', 'tests': []} for a in addresses]}]}


def write(directory, project, data):
    os.makedirs(os.path.join(directory, project)); path = os.path.join(directory, project, 'report.json')
    with open(path, 'w') as f: json.dump(data, f)
    return path


class Merge(unittest.TestCase):
    def test_the_suites_of_every_project_are_in_one_report_in_the_order_of_the_paths(self):
        with tempfile.TemporaryDirectory() as d:
            paths = [write(d, 'corpus', report('https://a.example/')), write(d, 'large', report('https://b.example/', 'https://c.example/'))]
            merged = mr.merge(paths)
        found = sorted(a for s in merged['suites'] for a in mr.specs(s))
        self.assertEqual(found, ['https://a.example/', 'https://b.example/', 'https://c.example/'])

    def test_a_page_walked_by_two_projects_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            paths = [write(d, 'corpus', report('https://a.example/')), write(d, 'structure', report('https://a.example/'))]
            with self.assertRaisesRegex(ValueError, 'is walked by'): mr.merge(paths)

    def test_measure_reads_a_prediction_out_of_the_merged_report(self):
        body = json.dumps({'treeSource': 'devtools', 'predictedSpeech': [], 'sweeps': []}).encode()
        import base64
        spec = {'title': 'keyboard walk of https://a.example/', 'tests': [{'results': [{'attachments': [{'name': 'predicted-nvda-speech.json', 'body': base64.b64encode(body).decode()}]}]}]}
        with tempfile.TemporaryDirectory() as d:
            paths = [write(d, 'corpus', {'suites': [{'specs': [spec]}]}), write(d, 'large', report('https://b.example/'))]
            found = measure.passive_predictions(mr.merge(paths))
        self.assertEqual(list(found), ['https://a.example/'])
        self.assertEqual(found['https://a.example/']['treeSource'], 'devtools')


if __name__ == '__main__': unittest.main()
