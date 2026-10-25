"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summarize_readings as sr


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: json.dump(data, f)


class Summaries(unittest.TestCase):
    def test_a_capture_is_summarised_by_its_own_dates_and_counts_and_nothing_of_the_page_is_copied(self):
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, 'a.f1.json'), {'capturedAt': '2026-10-25T09:40:00.000Z', 'worker': 'a11y-worker-14', 'status': 200,
                                                  'capture': {'transcript': ['spoken-words-x', 'y'], 'interaction': {'focusOrder': ['a', 'b', 'c']}, 'environment': {'browserVersion': '156', 'windowsBuild': '26300.9711', 'secret': 'no'}}})
            [row] = sr.fleet(d)
        self.assertEqual((row['worker'], row['status'], row['transcriptLines'], row['focusStops']), ('a11y-worker-14', 200, 2, 3))
        self.assertEqual(row['environment'], {'browserVersion': '156', 'windowsVersion': None, 'windowsBuild': '26300.9711', 'nvdaVersion': None})
        self.assertNotIn('spoken-words-x', json.dumps(row))

    def test_a_run_is_summarised_with_its_dates_and_the_runtimes_counts(self):
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, 'extension-1', 'times.json'), {'reading': 'ext-linux', 'run': 1, 'startedAt': 's', 'finishedAt': 'f'})
            write(os.path.join(d, 'extension-1', 'run.json'), {'tests': 8, 'flags': 0, 'wallMs': 5, 'drainMs': 4, 'workers': [{'snapshots': 3, 'keys': 9, 'focusEvents': 7, 'speechMs': 11, 'startup': {'treeSource': 'extension'}}]})
            out = sr.passive(d)
        self.assertEqual(out['ext-linux-run1']['workers'], [{'snapshots': 3, 'keys': 9, 'focusEvents': 7, 'speechMs': 11}])
        self.assertEqual((out['ext-linux-run1']['startedAt'], out['ext-linux-run1']['drainMs']), ('s', 4))


if __name__ == '__main__': unittest.main()
