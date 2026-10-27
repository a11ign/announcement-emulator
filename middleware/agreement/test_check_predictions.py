"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

check_predictions.py (A11-229, step 2): a run of the `large` project in which a page got no prediction is found, and the run committed in results/devtools-source/cost has all five."""
import base64, json, os, unittest

import check_predictions as check

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, '..', 'sample-suite')
COST = os.path.join(HERE, '..', 'results', 'devtools-source', 'cost')


def result(causes, status='passed'):
    speech = [{'cause': cause} for cause, n in causes.items() for _ in range(n)]
    body = base64.b64encode(json.dumps({'predictedSpeech': speech}).encode()).decode()
    return {'status': status, 'attachments': [{'name': check.ATTACHMENT, 'body': body}]}


def report(**pages):
    """A report of one spec for each page, with a result as given (None is a test the reporter attached nothing to)."""
    specs = [{'title': f'keyboard walk of {page}', 'tests': [{'results': [res or {'status': 'failed', 'attachments': [{'name': 'error-context'}]}]}]} for page, res in pages.items()]
    return {'suites': [{'suites': [{'specs': specs}]}]}


class Predictions(unittest.TestCase):
    def test_a_page_with_its_load_and_its_walked_stops_is_predicted(self):
        rows = check.predictions(report(a=result({'load': 1, 'focus': 150})))
        self.assertEqual(rows, [{'page': 'a', 'status': 'passed', 'load': 1, 'focus': 150, 'typed': 0}])
        self.assertEqual(check.unpredicted(rows), [])

    def test_a_page_the_reporter_attached_nothing_to_is_not_predicted(self):
        rows = check.predictions(report(a=result({'load': 1, 'focus': 150}), b=None))
        self.assertEqual(check.unpredicted(rows), ['b'])

    def test_a_page_with_no_load_speech_or_most_of_its_stops_missing_is_not_predicted(self):
        rows = check.predictions(report(a=result({'focus': 150}), b=result({'load': 1, 'focus': check.MIN_FOCUS - 1}), c=result({'load': 1, 'focus': check.MIN_FOCUS})))
        self.assertEqual(check.unpredicted(rows), ['a', 'b'])

    def test_a_page_that_no_test_ran_is_not_predicted(self):
        rows = check.predictions(report(a=result({'load': 1, 'focus': 150})))
        self.assertEqual(check.unpredicted(rows, ['a', 'z']), ['z'])

    def test_a_test_that_failed_after_its_walk_still_has_its_prediction(self):
        rows = check.predictions(report(a=result({'load': 1, 'focus': 151}, status='failed')))
        self.assertEqual(check.unpredicted(rows), [])


class TheRunInTheRepository(unittest.TestCase):
    def test_every_page_of_the_large_project_is_in_it_with_its_prediction(self):
        """results/devtools-source/cost/large-pages.json is the rows of the run measured (check_predictions.predictions, with the speech's length added)."""
        with open(os.path.join(COST, 'large-pages.json')) as f: rows = json.load(f)
        with open(os.path.join(SUITE, 'tests', 'large', 'pages.json')) as f: expected = [page['address'] for page in json.load(f)]
        self.assertEqual(check.unpredicted(rows, expected), [])
        self.assertEqual(sorted(row['page'] for row in rows), sorted(expected))


if __name__ == '__main__': unittest.main()
