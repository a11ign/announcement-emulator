"""python3 -m unittest discover -s q3 -t q3 -p test_fleet_capture.py   (from the repository root; standard library only)

fleet_capture.py is the one client of the fleet job service: every test here runs it against a stand-in `fleet` command (fleet_stub.py) that logs what it is asked and answers as the service does. Nothing reaches a fleet."""
import contextlib, io, json, os, re, tempfile, unittest, unittest.mock

import fleet_capture as fc, control_capture as ctl
from fleet_stub import FleetStub, ok_record

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PAGE = 'https://example.com/'


def run(main, argv):
    """(exit code, stdout, stderr) of an entry point's `main(argv)`."""
    out, err, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try: main(argv)
        except SystemExit as e: code = e.code if isinstance(e.code, int) else (1 if e.code else 0); err.write(e.code if isinstance(e.code, str) else '')
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.dir = self.tmp.name
        self.stub = FleetStub(self)
    def read(self, *path):
        with open(os.path.join(self.dir, *path)) as f: return json.load(f)


class Submit(Base):
    def capture(self, *extra, label=('--label', 'A11-246')):
        return run(fc.main, ['capture', 'a11y-worker-2', PAGE, os.path.join(self.dir, 'out.json'), *extra, *label])

    def test_a_capture_submits_one_job_for_the_page_on_the_named_box_and_prints_its_id(self):
        code, out, _ = self.capture()
        (submit,) = self.stub.submits()
        self.assertEqual((code, out.strip()), (0, FleetStub.JOB))
        self.assertEqual(submit['pages'], [PAGE])
        self.assertEqual(submit['options'], {**submit['options'], '--boxes': 'a11y-worker-2', '--passes': '1', '--steps': '600', '--label': 'A11-246'})
        self.assertNotIn('--probe', submit['options'])

    def test_the_steps_and_tables_arguments_still_mean_what_they_did(self):
        self.capture('300', '--tables')
        self.assertEqual({k: v for k, v in self.stub.submits()[0]['options'].items() if k in ('--steps', '--probe')}, {'--steps': '300', '--probe': 'tables'})

    def test_the_typing_dialog_flag_asks_for_the_typing_and_escape_probes_and_may_follow_the_step_count(self):
        self.capture('450', '--typing-dialog')
        self.assertEqual({k: v for k, v in self.stub.submits()[0]['options'].items() if k in ('--steps', '--probe')}, {'--steps': '450', '--probe': 'typing,dialog'})

    def test_both_probe_flags_together_ask_for_all_three(self):
        self.capture('--tables', '--typing-dialog')
        self.assertEqual(self.stub.submits()[0]['options']['--probe'], 'tables,typing,dialog')

    def test_a_submit_without_a_label_is_refused_before_fleet_runs(self):
        code, _, _ = self.capture(label=())
        self.assertNotEqual(code, 0); self.assertEqual(self.stub.calls(), [])
        with self.assertRaises(SystemExit): fc.submit([PAGE], 'a11y-worker-2', '')
        self.assertEqual(self.stub.calls(), [])

    def test_without_wait_the_job_id_is_the_result_and_nothing_waits_or_collects(self):
        code, out, err = self.capture()
        self.assertEqual(self.stub.others(), [])
        self.assertIn(FleetStub.JOB, err); self.assertFalse(os.path.exists(os.path.join(self.dir, 'out.json')))
        self.assertTrue(os.path.exists(os.path.join(self.dir, fc.PENDING_DIR, FleetStub.JOB + '.json')))

    def test_a_submit_the_service_refuses_exits_with_the_reason_and_writes_no_pending_file(self):
        stub = self.stub; stub.set(submit_exit=2)
        code, _, err = self.capture()
        self.assertEqual(code, 1); self.assertIn('the control plane could not be reached', err)
        self.assertFalse(os.path.exists(os.path.join(self.dir, fc.PENDING_DIR)))

    def test_an_old_name_equals_url_argument_is_refused_with_the_reason(self):
        code, _, err = run(fc.main, ['capture', 'a11y-worker-2=http://10.0.0.5:8765', PAGE, os.path.join(self.dir, 'out.json'), '--label', 'A11-246'])
        self.assertEqual(code, 1); self.assertIn('finds the box\'s address itself', err); self.assertEqual(self.stub.calls(), [])

    def test_a_host_with_no_fleet_command_says_so_and_runs_nothing_else(self):
        with unittest.mock.patch.dict(os.environ, {'FLEET': os.path.join(self.dir, 'no-such-fleet')}):
            code, _, err = self.capture()
        self.assertEqual(code, 1); self.assertIn('no capture is run here instead', err)


class Wait(Base):
    def go(self, **kw):
        self.stub.results([PAGE], ['a11y-worker-2'])
        return run(fc.main, ['capture', 'a11y-worker-2', PAGE, os.path.join(self.dir, 'out.json'), '--label', 'A11-246', '--wait', '30m'])

    def test_wait_is_one_job_wait_with_the_timeout_and_a_done_job_is_collected(self):
        code, out, _ = self.go()
        self.assertEqual(self.stub.others()[0], ['job', 'wait', FleetStub.JOB, '--timeout', '30m'])
        self.assertEqual(sum(1 for c in self.stub.others() if c[1] == 'wait'), 1)
        self.assertEqual(code, 0); self.assertEqual(self.read('out.json')['capture']['url'], PAGE); self.assertIn('200 2 lines', out)

    def test_a_timeout_prints_the_job_id_and_the_collect_command_and_collects_nothing(self):
        self.stub.set(wait_exit=124)
        code, out, err = self.go()
        self.assertEqual(code, 124); self.assertIn(FleetStub.JOB, out + err); self.assertIn(f'collect {os.path.join(self.dir, "out.json")} {FleetStub.JOB}', err)
        self.assertEqual([c[:2] for c in self.stub.others()], [['job', 'wait']]); self.assertFalse(os.path.exists(os.path.join(self.dir, 'out.json')))

    def test_a_failed_or_cancelled_job_exits_with_the_codes_of_job_wait_and_collects_nothing(self):
        for exit_code in (1, 3, 2):
            self.stub.set(wait_exit=exit_code)
            self.assertEqual(self.go()[0], exit_code)
        self.assertNotIn(['job', 'fetch'], [c[:2] for c in self.stub.others()])


class Results(Base):
    def collect(self, pages=(PAGE,), name='out.json', **results):
        self.stub.results(list(pages), ['a11y-worker-2'], **results)
        out = os.path.join(self.dir, name)
        fc.write_pending(self.dir, FleetStub.JOB, 'A11-246', {p: {'1': name} for p in pages[:1]})
        return run(fc.main, ['collect', out])

    def test_a_record_lands_under_its_name_as_the_service_wrote_it(self):
        code, out, _ = self.collect()
        record = self.read('out.json')
        self.assertEqual((code, record['worker'], record['status'], record['capture']['transcript']), (0, 'a11y-worker-2', 200, ['a', 'b']))
        self.assertEqual(self.stub.others(), [['job', 'fetch', FleetStub.JOB, '--to', self.stub.others()[0][4]]])

    def test_a_capture_the_service_has_no_file_for_is_a_status_zero_record_naming_the_box_and_the_error(self):
        code, out, _ = self.collect(missing={(PAGE, 1)})
        record = self.read('out.json')
        self.assertEqual((record['status'], record['worker']), (0, 'a11y-worker-2'))
        self.assertIn('left the fleet', record['capture']['error']); self.assertIn('left the fleet', out)

    def test_a_failed_capture_is_the_workers_record_of_it(self):
        self.collect(failed={(PAGE, 1)})
        self.assertEqual((self.read('out.json')['status'], self.read('out.json')['capture']['error']), (429, 'a capture is already in progress'))

    def test_a_page_server_given_as_an_ip_literal_is_written_by_name_in_the_record_and_the_manifest(self):
        address = 'http://192.0.2.7:8000/p.html'
        self.collect(pages=(address,), records={(address, 1): ok_record('a11y-worker-2', address)})
        self.assertEqual(self.read('out.json')['capture']['url'], 'http://capture-host:8000/p.html')
        manifest_path = os.path.join(self.dir, fc.PENDING_DIR, FleetStub.JOB + '.manifest.json')
        with open(manifest_path) as f: text = f.read()
        self.assertNotIn('192.0.2.7', text); self.assertIn('http://capture-host:8000/p.html', text)

    def test_a_host_name_is_left_as_it_is(self):
        self.collect()
        self.assertEqual(self.read('out.json')['capture']['url'], PAGE)

    def test_the_manifest_is_kept_under_the_pending_directory_and_not_beside_the_records(self):
        self.collect()
        self.assertEqual(self.read(fc.PENDING_DIR, FleetStub.JOB + '.manifest.json')['job'], FleetStub.JOB)
        self.assertEqual(sorted(f for f in os.listdir(self.dir) if f.endswith('.json')), ['out.json'])

    def test_write_record_keeps_an_existing_record_unless_it_is_told_to_overwrite(self):
        self.assertTrue(fc.write_record(self.dir, 'r.json', {'v': 1}))
        self.assertFalse(fc.write_record(self.dir, 'r.json', {'v': 2})); self.assertEqual(self.read('r.json'), {'v': 1})
        self.assertTrue(fc.write_record(self.dir, 'r.json', {'v': 3}, overwrite=True)); self.assertEqual(self.read('r.json'), {'v': 3})

    def test_a_capture_is_written_again_over_the_file_it_was_named_for(self):
        with open(os.path.join(self.dir, 'out.json'), 'w') as f: json.dump({'stale': True}, f)
        self.collect()
        self.assertNotIn('stale', self.read('out.json'))

    def test_a_job_that_has_not_finished_has_no_results_to_collect(self):
        for state in ('running', 'failed', 'cancelled'):
            code, _, err = self.collect(state=state, reason='no box is left' if state == 'failed' else None)
            self.assertEqual(code, 1, state); self.assertIn(state, err); self.assertFalse(os.path.exists(os.path.join(self.dir, 'out.json')))

    def test_a_capture_this_entry_point_did_not_submit_is_refused(self):
        self.stub.results(['https://other.example/'], ['a11y-worker-2'])
        fc.write_pending(self.dir, FleetStub.JOB, 'A11-246', {PAGE: {'1': 'out.json'}})
        code, _, err = run(fc.main, ['collect', os.path.join(self.dir, 'out.json')])
        self.assertEqual(code, 1); self.assertIn('did not submit', err)

    def test_collect_with_nothing_submitted_says_so(self):
        code, _, err = run(fc.main, ['collect', os.path.join(self.dir, 'out.json')])
        self.assertEqual(code, 1); self.assertIn('nothing was submitted', err); self.assertEqual(self.stub.calls(), [])

    def test_the_newest_job_naming_the_file_is_collected_when_no_job_is_given(self):
        fc.write_pending(self.dir, 'fj-20261025T090000Z-000001', 'A11-246', {PAGE: {'1': 'out.json'}})
        fc.write_pending(self.dir, 'fj-20261025T090000Z-000002', 'A11-246', {PAGE: {'1': 'other.json'}})
        self.assertEqual(fc.read_pending(self.dir, name='out.json')['job'], 'fj-20261025T090000Z-000001')


class ControlCapture(Base):
    """control_capture.py: the sample of static pages is one job, and its records are `<rel with / as __, less .html>.json`."""
    def setUp(self):
        super().setUp()
        self.pages = os.path.join(self.dir, 'pages'); self.out = os.path.join(self.dir, 'control')
        for rel in ('good/a.html', 'good/b.html', 'bad/c.html', 'bad/d.html'):
            os.makedirs(os.path.join(self.pages, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(self.pages, rel), 'w') as f: f.write('<p>x')
        self.addresses = [f'http://192.0.2.7:8000/{rel}' for rel in ('bad/c.html', 'bad/d.html', 'good/a.html', 'good/b.html')]      # sorted: bad before good

    def submit(self, n='4', *extra): return run(ctl.main, [self.pages, 'http://192.0.2.7:8000/', self.out, n, '--boxes', '2', '--label', 'A11-246', *extra])

    def test_the_sample_is_one_job_of_its_addresses_with_the_default_body_and_one_pass(self):
        code, out, _ = self.submit()
        (submit,) = self.stub.submits()
        self.assertEqual((code, out.strip()), (0, FleetStub.JOB)); self.assertEqual(submit['pages'], self.addresses)
        self.assertEqual({k: submit['options'][k] for k in ('--boxes', '--label', '--passes', '--steps')}, {'--boxes': '2', '--label': 'A11-246', '--passes': '1', '--steps': '600'})
        self.assertNotIn('--probe', submit['options']); self.assertEqual(self.stub.others(), [])

    def test_the_sample_is_every_kth_page_so_it_is_fixed_by_n(self):
        self.submit('2')
        self.assertEqual(self.stub.submits()[0]['pages'], [self.addresses[0], self.addresses[2]])

    def test_collect_writes_each_page_to_its_slug_and_leaves_an_existing_record(self):
        self.submit()
        os.makedirs(self.out, exist_ok=True)
        with open(os.path.join(self.out, 'bad__c.json'), 'w') as f: json.dump({'earlier': True}, f)
        self.stub.results(self.addresses, ['a11y-worker-2', 'a11y-worker-3'])
        code, out, _ = run(ctl.main, ['collect', self.out])
        self.assertEqual(code, 0); self.assertEqual(sorted(f for f in os.listdir(self.out) if f.endswith('.json')), ['bad__c.json', 'bad__d.json', 'good__a.json', 'good__b.json'])
        self.assertEqual(self.read('control', 'bad__c.json'), {'earlier': True}); self.assertEqual(self.read('control', 'good__a.json')['capture']['url'], 'http://capture-host:8000/good/a.html')

    def test_a_page_with_a_record_is_left_out_of_the_job(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, 'bad__c.json'), 'w') as f: f.write('{}')
        self.submit()
        self.assertEqual(self.stub.submits()[0]['pages'], self.addresses[1:])

    def test_with_wait_one_job_wait_runs_and_a_done_job_is_collected(self):
        self.stub.results(self.addresses, ['a11y-worker-2', 'a11y-worker-3'])
        code, _, _ = self.submit('4', '--wait', '1h')
        self.assertEqual(self.stub.others()[0], ['job', 'wait', FleetStub.JOB, '--timeout', '1h']); self.assertEqual((code, len(os.listdir(self.out)) - 1), (0, 4))

    def test_the_old_workers_file_is_refused_with_the_new_form(self):
        code, _, err = self.submit('4', '--workers', 'w.txt')
        self.assertEqual(code, 1); self.assertIn('--boxes', err); self.assertEqual(self.stub.calls(), [])


class NoShellCaptures(unittest.TestCase):
    """No entry point runs a capture in the caller's shell, waits in a loop, or looks for a process by its command line."""
    ENTRY_POINTS = ['q3/fleet_capture.py', 'q3/control_capture.py', 'q3/corpus_capture.py', 'middleware/agreement/capture_fleet.py', 'q3/replay/fleet/box.sh']
    FORBIDDEN = {'pgrep': r'pgrep', 'a sleep': r'\bsleep\b', 'a while or until loop': r'^\s*(while|until)\b', 'a request to a worker': r'/capture\b(?!_)', 'the removed node script': r'fleet_capture\.mjs', 'a node capture': r'\bnode\b'}

    def test_none_of_them_has_any_of_it(self):
        for path in self.ENTRY_POINTS:
            with open(os.path.join(ROOT, path)) as f: lines = f.read().splitlines()
            for what, pattern in self.FORBIDDEN.items():
                self.assertEqual([n + 1 for n, line in enumerate(lines) if re.search(pattern, line)], [], f'{path} has {what}')

    def test_the_removed_script_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(HERE, 'fleet_capture.mjs')))

    def test_fleet_capture_is_the_only_code_that_calls_fleet(self):
        calls = []
        for folder in ('q3', 'middleware/agreement'):
            for dirpath, _, names in os.walk(os.path.join(ROOT, folder)):
                for n in names:
                    if n.endswith(('.py', '.sh')) and not n.startswith('test_') and n not in ('fleet_capture.py', 'fleet_stub.py'):
                        with open(os.path.join(dirpath, n)) as f:
                            if re.search(r"""run_fleet\(|subprocess\.\w+\(\s*\[\s*['"]fleet['"]|environ(\.get)?[(\[]\s*['"]FLEET['"]""", f.read()): calls.append(os.path.relpath(os.path.join(dirpath, n), ROOT))
        self.assertEqual(calls, [])


if __name__ == '__main__': unittest.main()
