"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summarize_cost as sc


def row(how, total, nodes=1500, reason=None, patched=None, fetch=None, convert=None):
    return {'how': how, 'reason': reason, 'totalMs': total, 'fetchMs': total * 0.6 if fetch is None else fetch, 'convertMs': total * 0.4 if convert is None else convert, 'nodes': nodes, **({'patched': patched} if patched is not None else {})}


def write_run(directory, rows, run):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, 'profile.jsonl'), 'w') as f: f.write('\n'.join(json.dumps(r) for r in rows) + '\n')
    with open(os.path.join(directory, 'run.json'), 'w') as f: json.dump(run, f)


RUN = {'wallMs': 90000, 'drainMs': 60000, 'tests': 8, 'workers': [{'speechMs': 20000, 'snapshots': 9, 'keys': 300, 'focusEvents': 280, 'unresolvedFocus': 3}, {'speechMs': 10000, 'snapshots': 4, 'keys': 100, 'focusEvents': 90, 'unresolvedFocus': 1}]}


class Reads(unittest.TestCase):
    def test_the_reads_of_a_profile_are_counted_by_how_they_were_made_and_summed(self):
        out = sc.reads([row('full', 1000, reason='first'), row('full', 500, reason='mutation'), row('incremental', 100, patched=True), row('incremental', 200, patched=False)])
        self.assertEqual((out['count'], out['full'], out['incremental'], out['patched']), (4, 2, 2, 1))
        self.assertEqual((out['totalMs'], out['fullMs'], out['incrementalMs']), (1800, 1500, 300))
        self.assertEqual((out['meanFullMs'], out['meanIncrementalMs']), (750.0, 150.0))
        self.assertEqual(round(out['fetchMs'] + out['convertMs']), 1800)

    def test_the_cost_of_an_incremental_read_is_set_against_a_full_one_on_the_pages_where_it_matters(self):
        out = sc.reads([row('full', 1000, nodes=2000), row('full', 10, nodes=50), row('incremental', 100, nodes=2000), row('incremental', 5, nodes=50)])['largePages']
        self.assertEqual((out['fullMs'], out['incrementalMs'], out['incrementalOverFull']), (1000.0, 100.0, 0.1))
        self.assertIsNone(sc.reads([row('full', 10, nodes=50)])['largePages']['incrementalOverFull'])

    def test_why_a_read_was_whole_is_counted_without_the_numbers_of_nodes(self):
        out = sc.reads([row('full', 1, reason='layout'), row('full', 1, reason='layout'), row('full', 1, reason='stale: Stale a node the page did not have: 325 (read for a <div>, 1 nodes answered, ignored=True)'),
                        row('full', 1, reason='stale: Stale a node the page did not have: 78'), row('full', 1)])['whyFull']
        self.assertEqual(out, {'layout': 2, 'stale: a node the page did not have: N': 2, 'before the probe existed': 1})

    def test_a_profile_with_no_reads_has_no_means(self):
        out = sc.reads([])
        self.assertEqual((out['count'], out['meanFullMs'], out['meanIncrementalMs']), (0, 0, 0))


class Runs(unittest.TestCase):
    def test_a_run_has_the_time_of_its_workers_added_up_and_its_reads(self):
        with tempfile.TemporaryDirectory() as d:
            write_run(d, [row('full', 100), row('incremental', 10)], RUN)
            out = sc.run(d)
        self.assertEqual((out['wallMs'], out['drainMs'], out['speechMs'], out['snapshots'], out['keys'], out['focusEvents'], out['unresolvedFocus']), (90000, 60000, 30000, 13, 400, 370, 4))
        self.assertEqual(out['reads']['count'], 2)

    def test_a_run_made_before_the_probe_has_reads_that_are_all_full(self):
        with tempfile.TemporaryDirectory() as d:
            write_run(d, [{'totalMs': 100, 'fetchMs': 60, 'convertMs': 40, 'nodes': 3, 'how': 'full'}], RUN)
            self.assertEqual(sc.run(d)['reads']['whyFull'], {'before the probe existed': 1})


class Table(unittest.TestCase):
    def test_two_runs_are_two_columns(self):
        with tempfile.TemporaryDirectory() as d:
            write_run(os.path.join(d, 'a'), [row('full', 1000), row('full', 2000)], RUN); write_run(os.path.join(d, 'b'), [row('full', 1000), row('incremental', 100)], dict(RUN, wallMs=45000))
            summary = {'before': sc.run(os.path.join(d, 'a')), 'after': sc.run(os.path.join(d, 'b'))}
        text = sc.table(summary, ['before', 'after'])
        lines = text.splitlines()
        self.assertEqual(lines[0], '| | before | after |')
        self.assertIn('| wall time (s) | 90.0 | 45.0 |', lines)
        self.assertIn('| reads of a tree | 2 (2 full, 0 incremental) | 2 (1 full, 1 incremental) |', lines)
        self.assertIn('| mean incremental read (ms) | - | 100 |', lines)


if __name__ == '__main__': unittest.main()
