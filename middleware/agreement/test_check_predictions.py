"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

check_predictions.py (A11-229, step 2): a run of the `large` project in which a page got no prediction is found, and the run committed in results/devtools-source/cost has all five."""
import base64, copy, json, os, subprocess, sys, tempfile, unittest

import check_predictions as check

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, '..', 'sample-suite')
COST = os.path.join(HERE, '..', 'results', 'devtools-source', 'cost')
REPORT = os.path.join(HERE, 'fixtures', 'large-report.json')      # the Playwright report of a run of the `large` project (test-results/report.json), with each attachment cut to the cause of its utterances
PAGES = os.path.join(SUITE, 'tests', 'large', 'pages.json')
CHECK = os.path.join(HERE, 'check_predictions.py')


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


def attachments(report):
    """Every attachment of every test of a report."""
    return [a for suite in report['suites'] for _, result in check.tests(suite) for a in result['attachments']]


class TheReportOfARun(unittest.TestCase):
    """A report as Playwright writes it, of a run of the `large` project in which the runtime predicted all five pages."""
    def setUp(self):
        with open(REPORT) as f: self.report = json.load(f)
        with open(PAGES) as f: self.expected = [page['address'] for page in json.load(f)]

    def write(self, report):
        handle, path = tempfile.mkstemp(suffix='.json')
        with os.fdopen(handle, 'w') as f: json.dump(report, f)
        self.addCleanup(os.remove, path)
        return path

    def run_check(self, report):
        return subprocess.run([sys.executable, CHECK, self.write(report), PAGES], capture_output=True, text=True)

    def test_each_of_the_five_pages_has_its_load_and_its_walked_stops(self):
        rows = check.predictions(self.report)
        self.assertEqual(sorted(row['page'] for row in rows), sorted(self.expected))
        self.assertEqual(check.unpredicted(rows, self.expected), [])
        self.assertTrue(all(row['load'] == 1 and row['focus'] >= check.MIN_FOCUS for row in rows))

    def test_the_command_passes_the_report_of_a_run_that_predicted_every_page(self):
        done = self.run_check(self.report)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_run_whose_predictions_are_gone_fails_the_command_and_names_every_page(self):
        report = copy.deepcopy(self.report)
        for suite in report['suites']:
            for _, result in check.tests(suite): result['attachments'] = []
        done = self.run_check(report)
        self.assertEqual(done.returncode, 1)
        for address in self.expected: self.assertIn(address, done.stderr)

    def test_a_run_in_which_one_page_lost_its_focus_events_fails_the_command_and_names_that_page_only(self):
        report = copy.deepcopy(self.report)
        attachment = attachments(report)[2]
        speech = json.loads(base64.b64decode(attachment['body']))
        speech['predictedSpeech'] = [u for u in speech['predictedSpeech'] if u['cause'] != 'focus']
        attachment['body'] = base64.b64encode(json.dumps(speech).encode()).decode()
        done = self.run_check(report)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stderr.count('https://'), 1); self.assertIn(self.expected[2], done.stderr)

    def test_a_page_that_no_test_walked_fails_the_command(self):
        report = copy.deepcopy(self.report)
        walked = report['suites'][0]['specs']; walked.pop()
        self.assertEqual(len(walked), len(self.expected) - 1)
        done = self.run_check(report)
        self.assertEqual(done.returncode, 1); self.assertIn(self.expected[-1], done.stderr)


class TheRunInTheRepository(unittest.TestCase):
    def test_every_page_of_the_large_project_is_in_it_with_its_prediction(self):
        """results/devtools-source/cost/large-pages.json is the rows of the run measured (check_predictions.predictions, with the speech's length added)."""
        with open(os.path.join(COST, 'large-pages.json')) as f: rows = json.load(f)
        with open(os.path.join(SUITE, 'tests', 'large', 'pages.json')) as f: expected = [page['address'] for page in json.load(f)]
        self.assertEqual(check.unpredicted(rows, expected), [])
        self.assertEqual(sorted(row['page'] for row in rows), sorted(expected))


if __name__ == '__main__': unittest.main()
