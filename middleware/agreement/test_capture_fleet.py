"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement -p test_capture_fleet.py   (from the repository root)

capture_fleet.py against a stand-in `fleet` command (q3/fleet_stub.py): what it submits, and what it writes from the job's results."""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.append(os.path.join(HERE, '..', '..', 'q3'))
import capture_fleet
from measure import slug
from fleet_stub import FleetStub, run_main

PAGES = ['https://example.com/a', 'https://example.com/b', 'https://example.com/c']
BOXES = ['a11y-worker-13', 'a11y-worker-14', 'a11y-worker-16']


def run(argv): return run_main(capture_fleet.main, argv)


class CaptureFleet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.dir = self.tmp.name
        self.out = os.path.join(self.dir, 'fleet'); self.pages = os.path.join(self.dir, 'pages.json')
        with open(self.pages, 'w') as f: json.dump({'sample': [{'url': p} for p in PAGES]}, f)
        self.stub = FleetStub(self)

    def submit(self, *extra, boxes='3'): return run([self.pages, self.out, '--boxes', boxes, '--label', 'A11-246', *extra])
    def collect(self, **results):
        self.stub.results(PAGES, BOXES, passes=2, **results)
        return run(['collect', self.out])
    def written(self): return sorted(f for f in os.listdir(self.out) if f.endswith('.json'))
    def put(self, name):
        os.makedirs(self.out, exist_ok=True)
        with open(os.path.join(self.out, name), 'w') as f: json.dump({'earlier': True}, f)

    def test_two_passes_and_the_typing_and_dialog_probes_are_in_the_submit_with_the_label_and_the_boxes(self):
        code, out, _ = self.submit()
        (submit,) = self.stub.submits()
        self.assertEqual((code, out.strip()), (0, FleetStub.JOB)); self.assertEqual(submit['pages'], PAGES)
        self.assertEqual({k: submit['options'][k] for k in ('--passes', '--steps', '--probe', '--boxes', '--label')}, {'--passes': '2', '--steps': '600', '--probe': 'typing,dialog', '--boxes': '3', '--label': 'A11-246'})

    def test_boxes_may_be_names_or_ready_and_a_freeze_is_passed_on(self):
        self.submit('--freeze', 'freeze.json', boxes='a11y-worker-13,a11y-worker-14')
        self.assertEqual({k: v for k, v in self.stub.submits()[0]['options'].items() if k in ('--boxes', '--freeze')}, {'--boxes': 'a11y-worker-13,a11y-worker-14', '--freeze': 'freeze.json'})

    def test_a_page_whose_two_records_exist_is_left_out_and_one_with_a_single_record_is_not(self):
        self.put(f'{slug(PAGES[0])}.f1.json'); self.put(f'{slug(PAGES[0])}.f2.json'); self.put(f'{slug(PAGES[1])}.f1.json')
        self.submit()
        self.assertEqual(self.stub.submits()[0]['pages'], PAGES[1:])

    def test_a_sample_with_nothing_left_to_capture_submits_nothing(self):
        for p in PAGES: self.put(f'{slug(p)}.f1.json'); self.put(f'{slug(p)}.f2.json')
        code, _, err = self.submit()
        self.assertEqual((code, self.stub.calls()), (1, [])); self.assertIn('nothing to capture', err)

    def test_without_wait_nothing_waits_and_nothing_is_written(self):
        self.submit()
        self.assertEqual(self.stub.others(), []); self.assertEqual(self.written(), [])

    def test_with_wait_one_job_wait_runs_and_the_records_are_collected(self):
        self.stub.results(PAGES, BOXES, passes=2)
        code, _, _ = self.submit('--wait', '90m')
        self.assertEqual(self.stub.others()[0], ['job', 'wait', FleetStub.JOB, '--timeout', '90m']); self.assertEqual((code, len(self.written())), (0, 6))

    def test_a_timeout_collects_nothing_and_exits_124(self):
        self.stub.set(wait_exit=124)
        code, _, err = self.submit('--wait', '5m')
        self.assertEqual(code, 124); self.assertEqual(self.written(), []); self.assertIn(f'collect {self.out} {FleetStub.JOB}', err)

    def test_pass_k_of_a_page_is_written_to_the_slug_dot_f_k_file_measure_py_reads_on_two_boxes(self):
        self.submit(); code, out, _ = self.collect()
        self.assertEqual(code, 0); self.assertEqual(self.written(), sorted(f'{slug(p)}.f{k}.json' for p in PAGES for k in (1, 2)))
        for p in PAGES:
            f1, f2 = (json.load(open(os.path.join(self.out, f'{slug(p)}.f{k}.json'))) for k in (1, 2))
            self.assertEqual((f1['capture']['url'], f2['capture']['url']), (p, p)); self.assertNotEqual(f1['worker'], f2['worker'])

    def test_an_existing_record_is_not_written_over(self):
        self.put(f'{slug(PAGES[0])}.f1.json'); self.submit(); self.collect()
        self.assertEqual(json.load(open(os.path.join(self.out, f'{slug(PAGES[0])}.f1.json'))), {'earlier': True})
        self.assertIn('worker', json.load(open(os.path.join(self.out, f'{slug(PAGES[0])}.f2.json'))))

    def test_a_manifest_whose_boxes_disagree_writes_no_record_and_names_the_mismatch(self):
        self.submit(); code, _, err = self.collect(consistent=False, mismatches=['edge: a11y-worker-13 is 141.0.1 and a11y-worker-14 is 142.0.2'])
        self.assertEqual(code, 1); self.assertEqual(self.written(), []); self.assertIn('edge: a11y-worker-13 is 141.0.1', err)

    def test_a_capture_with_no_file_is_a_status_zero_record_and_the_rest_are_written(self):
        self.submit(); self.collect(missing={(PAGES[1], 2)})
        gone = json.load(open(os.path.join(self.out, f'{slug(PAGES[1])}.f2.json')))
        self.assertEqual((gone['status'], gone['worker']), (0, BOXES[(1 + 2 - 1) % 3])); self.assertEqual(len(self.written()), 6)

    def test_the_old_workers_argument_is_refused_with_the_new_form(self):
        code, _, err = run([self.pages, self.out, '--workers', 'a11y-worker-13=http://10.0.0.1:8765', '--label', 'A11-246'])
        self.assertEqual(code, 1); self.assertIn('--boxes', err); self.assertEqual(self.stub.calls(), [])

    def test_plan_is_the_rule_the_service_applies(self):
        self.assertEqual(capture_fleet.plan(['a', 'b', 'c'], ['w1', 'w2', 'w3']), [('a', 1, 'w1'), ('a', 2, 'w2'), ('b', 1, 'w2'), ('b', 2, 'w3'), ('c', 1, 'w3'), ('c', 2, 'w1')])


if __name__ == '__main__': unittest.main()
