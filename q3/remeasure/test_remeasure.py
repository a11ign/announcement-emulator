"""python3 -m unittest discover -s q3/remeasure -t q3/remeasure   (from the repository root; needs node, as the capture does)"""
import sys, os, json, tempfile, subprocess, unittest, io, contextlib, threading, time, http.server
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, Q3)
import readback as rb, check, corpus_capture as cc, policy_override as po, explain_visited as ev

def write(path, text):
    with open(path, 'w') as f: f.write(text)

def record(worker='a11y-worker-2', links=('History probe self, link', 'History probe cookies, link'), status=200, transcript=(), url='http://capture-host:8000/visited-probe.html'):
    return {'capturedAt': '2026-10-21T10:00:00.000Z', 'worker': worker, 'status': status, 'capture': {'url': url, 'transcript': list(transcript), 'structure': {'links': list(links), 'headings': ['History probe, heading, level 1']}}}

def held_box():
    return passing_box() | {'after-run': rb.probe_outcome(record() | {'capturedAt': '2026-10-21T12:00:00.000Z'})}


def passing_box(visited_after=False):
    return {'before': rb.probe_outcome(record(links=('a, visited, link', 'b, link')) | {'capturedAt': '2026-10-21T08:00:00.000Z'}),
            'policy': {'name': rb.POLICY, 'value': 1, 'readAt': '2026-10-21T09:00:00Z', 'evidence': 'all 11 policy values verified'}, 'emptied': {'at': '2026-10-21T09:05:00Z', 'what': 'History'},
            'after': rb.probe_outcome(record(links=('a, visited, link', 'b, link') if visited_after else ('a, link', 'b, link')))}


class ProbeOutcome(unittest.TestCase):
    def test_visited_token_in_a_swept_link_is_seen(self):
        self.assertTrue(rb.probe_outcome(record(links=('History probe self, visited, link', 'x, link')))['visited'])
    def test_visited_token_in_the_spoken_transcript_is_seen(self):
        self.assertTrue(rb.probe_outcome(record(transcript=['History probe cookies, visited, link']))['visited'])
    def test_the_word_inside_a_name_is_not_the_state(self):
        self.assertFalse(rb.probe_outcome(record(links=('Recently visited pages, link', 'x, link')))['visited'])
    def test_a_probe_that_did_not_read_the_page_reads_nothing(self):
        for r in (record(links=('only one, link',)), record(status=500)):
            o = rb.probe_outcome(r); self.assertFalse(o['read']); self.assertFalse(rb.stage_passes('after', o)); self.assertFalse(rb.stage_passes('before', o))
    def test_before_must_see_history_and_after_must_not(self):
        seen, clean = rb.probe_outcome(record(links=('a, visited, link', 'b, link'))), rb.probe_outcome(record())
        self.assertTrue(rb.stage_passes('before', seen)); self.assertFalse(rb.stage_passes('before', clean))
        self.assertFalse(rb.stage_passes('after', seen)); self.assertTrue(rb.stage_passes('after', clean))


class BoxPasses(unittest.TestCase):
    def test_a_clean_box_with_the_policy_read_back_and_the_store_emptied_passes(self): self.assertTrue(rb.box_passes(passing_box()))
    def test_a_box_whose_after_probe_reads_visited_fails(self): self.assertFalse(rb.box_passes(passing_box(visited_after=True)))
    def test_each_step_is_required(self):
        for gone in ('policy', 'emptied', 'after'):
            b = passing_box(); del b[gone]; self.assertFalse(rb.box_passes(b), gone)
        b = passing_box(); b['policy']['value'] = 0; self.assertFalse(rb.box_passes(b))
    def test_a_box_whose_before_probe_saw_no_history_still_passes_but_is_not_the_control(self):
        b = passing_box(); b['before'] = rb.probe_outcome(record() | {'capturedAt': '2026-10-21T08:00:00.000Z'}); self.assertTrue(rb.box_passes(b)); self.assertFalse(rb.has_control(b))
    def test_a_box_with_no_before_probe_at_all_passes_on_its_other_readings(self):
        b = passing_box(); del b['before']; self.assertTrue(rb.box_passes(b))
    def test_readings_out_of_order_fail_the_box(self):
        b = passing_box(); b['after'] = rb.probe_outcome(record() | {'capturedAt': '2026-10-21T08:30:00.000Z'}); self.assertFalse(rb.box_passes(b))      # the clean probe predates the policy
    def test_a_capture_that_is_not_the_probe_page_is_not_a_reading(self):
        other = rb.probe_outcome(record(url='https://example.org/some-corpus-page'))
        self.assertFalse(other['read']); self.assertFalse(rb.stage_passes('after', other)); self.assertFalse(rb.stage_passes('before', rb.probe_outcome(record(links=('a, visited, link', 'b, link'), url='https://example.org/'))))
    def test_a_restored_box_no_longer_passes_but_still_counts_as_having_held(self):
        b = held_box(); self.assertTrue(rb.box_held(b)); b['restored'] = {'at': '2026-10-21T13:00:00Z'}
        self.assertFalse(rb.box_passes(b)); self.assertTrue(rb.box_held(b))
    def test_holding_needs_the_after_run_probe_after_the_after_probe_and_the_restore_after_both(self):
        b = held_box(); b['after-run'] = rb.probe_outcome(record() | {'capturedAt': '2026-10-21T10:00:00.000Z'}); self.assertFalse(rb.box_held(b))      # not later than `after`
        b = held_box(); b['restored'] = {'at': '2026-10-21T11:00:00Z'}; self.assertFalse(rb.box_held(b))                                              # put back before the after-run probe
        b = held_box(); b['restored'] = {'at': '2026-10-21T13:00:00Z'}; self.assertTrue(rb.box_held(b))
    def test_holding_through_the_run_needs_a_clean_after_run_probe(self):
        self.assertFalse(rb.box_held(passing_box()))
        b = held_box(); b['after-run'] = rb.probe_outcome(record(links=('a, visited, link', 'b, link'))); self.assertFalse(rb.box_held(b))


class CorpusCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name
        self.readback = {'workers': {f'a11y-worker-{n}': passing_box() for n in (2, 3, 4)} | {'a11y-worker-5': passing_box(visited_after=True)}}
        self.stub = os.path.join(self.dir, 'stub.mjs')       # stands in for fleet_capture.mjs: writes a record for the address, or fails for one address
        write(self.stub, """import { writeFileSync } from 'node:fs'; const [, , w, url, out] = process.argv; const name = w.split('=')[0];
if (url.endsWith('/silent')) process.exit(0);        // the worker was unreachable: nothing is written
if (url.endsWith('/garbled')) { writeFileSync(out, '{not json'); process.exit(0); }
if (url.endsWith('/broken')) { writeFileSync(out, JSON.stringify({ worker: name, status: 500, capture: { error: 'boom' } })); process.exit(0); }
writeFileSync(out, JSON.stringify({ capturedAt: 'now', worker: name, status: 200, capture: { url, transcript: [], structure: { links: ['a, link'], headings: [] } } }));""")
    def tearDown(self): self.tmp.cleanup()

    def test_a_failing_capture_command_fails_the_page_without_killing_the_worker(self):
        out = os.path.join(self.dir, 'oracle'); crash = os.path.join(self.dir, 'crash.mjs'); write(crash, "process.exit(3);")
        s = cc.run([{'url': f'https://example.org/{i}', 'role': None} for i in range(3)], self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, crash, attempts=1, log=lambda *a, **k: None)
        self.assertEqual((s['captured'], len(s['failed'])), (0, 3))
        s = cc.run([{'url': 'https://example.org/x', 'role': None}], self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, os.path.join(self.dir, 'missing.mjs'), attempts=1, log=lambda *a, **k: None)
        self.assertEqual(len(s['failed']), 1)
    def test_an_unreadable_record_fails_its_page_and_the_run_goes_on(self):
        out = os.path.join(self.dir, 'oracle'); bad, good = 'https://example.org/garbled', 'https://example.org/fine'
        s = cc.run([{'url': bad, 'role': None}, {'url': good, 'role': None}], self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, self.stub, attempts=1, log=lambda *a, **k: None)
        self.assertEqual((s['captured'], s['failed']), (1, [bad]))
    def test_a_record_of_an_earlier_unstamped_run_is_captured_again(self):
        out = os.path.join(self.dir, 'oracle'); os.makedirs(out); url = 'https://example.org/old'
        rb.write_json(os.path.join(out, cc.slug_of(url) + '.json'), record(url=url))
        s = cc.run([{'url': url, 'role': None}], self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, self.stub, log=lambda *a, **k: None)
        self.assertIn('history', rb.read_json(os.path.join(out, cc.slug_of(url) + '.json'))); self.assertEqual(s['captured'], 1)
    def test_a_part_file_left_by_an_interrupted_run_is_not_taken_for_a_capture(self):
        out = os.path.join(self.dir, 'oracle'); os.makedirs(out); url = 'https://example.org/broken'
        url = 'https://example.org/silent'
        rb.write_json(os.path.join(out, cc.slug_of(url) + '.json.part'), record(url=url))      # a good-looking record left by the interrupted run; the stub writes nothing for this address
        s = cc.run([{'url': url, 'role': None}], self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, self.stub, attempts=1, log=lambda *a, **k: None)
        self.assertEqual(s['failed'], [url])

    def workers(self, *names): return {n: f'http://box-{n}:8765' for n in names}
    def test_a_worker_without_a_passing_readback_is_refused(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err): use = cc.usable_workers(self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4', 'a11y-worker-5', 'a11y-worker-9'), self.readback)
        self.assertEqual(sorted(use), ['a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'])
        self.assertIn('a11y-worker-5', err.getvalue()); self.assertIn('a11y-worker-9', err.getvalue())
    def test_fewer_than_three_passing_workers_stop_the_run(self):
        with self.assertRaises(SystemExit): cc.usable_workers(self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-5'), self.readback)
    def test_every_record_is_stamped_with_the_history_block_and_the_role(self):
        out = os.path.join(self.dir, 'oracle')
        entries = [{'url': f'https://example.org/{i}', 'role': 'training'} for i in range(5)]
        s = cc.run(entries, self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, self.stub, log=lambda *a, **k: None)
        self.assertEqual((s['captured'], s['failed']), (5, []))
        files = sorted(os.listdir(out)); self.assertEqual(len(files), 5)
        for f in files:
            rec = rb.read_json(os.path.join(out, f))
            self.assertEqual(rec['history']['policy'], {'name': rb.POLICY, 'value': 1}); self.assertTrue(rec['history']['storeEmptied']); self.assertEqual(rec['role'], 'training')
            self.assertFalse(rec['history']['probeAfter']['visited'])
    def test_a_page_that_fails_is_named_and_leaves_no_record(self):
        out = os.path.join(self.dir, 'oracle')
        s = cc.run([{'url': 'https://example.org/broken', 'role': None}, {'url': 'https://example.org/fine', 'role': None}], self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, self.stub, log=lambda *a, **k: None)
        self.assertEqual(s['failed'], ['https://example.org/broken']); self.assertEqual(len(os.listdir(out)), 1)
    def test_slugs_are_distinct_for_addresses_that_differ_only_in_punctuation(self):
        self.assertNotEqual(cc.slug_of('https://a.org/x?y=1'), cc.slug_of('https://a.org/x/y/1'))


class PolicyOverride(unittest.TestCase):
    DEFAULTS = "worker_other: 1\nworker_edge_policy:\n  # a comment\n  - { name: HideFirstRunExperience, value: 1 }\n  - { name: BrowserSignin, value: 0 }\n"
    def test_it_restates_every_entry_and_adds_the_history_policy_last(self):
        self.assertEqual(po.override(self.DEFAULTS), {'worker_edge_policy': [{'name': 'HideFirstRunExperience', 'value': 1}, {'name': 'BrowserSignin', 'value': 0}, {'name': rb.POLICY, 'value': 1}]})
    def test_restore_sets_the_history_policy_to_the_browsers_default_in_the_same_list(self):
        self.assertEqual(po.override(self.DEFAULTS, history=0)['worker_edge_policy'][-1], {'name': rb.POLICY, 'value': 0}); self.assertEqual(len(po.override(self.DEFAULTS, history=0)['worker_edge_policy']), 3)
    def test_it_does_not_leak_other_variables_into_the_override(self):
        self.assertEqual(list(po.override(self.DEFAULTS)), ['worker_edge_policy'])
    def test_it_refuses_when_the_policy_is_already_declared(self):
        with self.assertRaises(SystemExit): po.override(self.DEFAULTS + "  - { name: SavingBrowserHistoryDisabled, value: 1 }\n")


class FleetCapture(unittest.TestCase):
    """fleet_capture.mjs against a worker that answers late, as a real one does (the answer comes when the capture is done)."""
    def serve(self, status, body, delay):
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['content-length'])); time.sleep(delay)
                self.send_response(status); self.end_headers(); self.wfile.write(body.encode())
            def log_message(self, *a): pass
        server = http.server.HTTPServer(('127.0.0.1', 0), H); threading.Thread(target=server.serve_forever, daemon=True).start(); self.addCleanup(server.shutdown); self.addCleanup(server.server_close)
        return f'http://127.0.0.1:{server.server_port}'
    def capture(self, worker_url, address='http://127.0.0.1:8000/page.html'):
        out = tempfile.NamedTemporaryFile(suffix='.json', delete=False); out.close(); self.addCleanup(os.remove, out.name)
        done = subprocess.run(['node', os.path.join(Q3, 'fleet_capture.mjs'), f'a11y-worker-2={worker_url}', address, out.name], capture_output=True, text=True, timeout=60)
        return done, rb.read_json(out.name)
    def test_a_late_answer_is_written_as_the_workers_record(self):
        done, rec = self.capture(self.serve(200, json.dumps({'url': 'http://127.0.0.1:8000/page.html', 'transcript': ['a'], 'structure': {}}), delay=2))
        self.assertEqual((rec['status'], rec['worker'], rec['capture']['transcript']), (200, 'a11y-worker-2', ['a']))
    def test_a_busy_worker_is_a_record_with_its_status_and_reason(self):
        done, rec = self.capture(self.serve(429, 'a capture is already in progress', delay=0))
        self.assertEqual((rec['status'], rec['capture']['error']), (429, 'a capture is already in progress'))
    def test_a_refused_connection_is_a_record_that_names_the_worker_and_not_its_address(self):
        import socket
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]      # a port nothing listens on
        done, rec = self.capture(f'http://127.0.0.1:{port}')
        self.assertEqual(rec['status'], 0); self.assertIn('a11y-worker-2', rec['capture']['error']); self.assertNotIn('127.0.0.1', json.dumps(rec)); self.assertEqual(done.returncode, 0)
    def test_an_answer_cut_off_midway_is_a_record_with_an_error_not_a_hang(self):
        import socket
        server = socket.socket(); server.bind(('127.0.0.1', 0)); server.listen(1); self.addCleanup(server.close)
        def cut():
            conn, _ = server.accept(); conn.recv(65536); conn.sendall(b'HTTP/1.1 200 OK\r\ncontent-length: 100\r\n\r\n{"tran'); conn.close()
        threading.Thread(target=cut, daemon=True).start()
        done, rec = self.capture(f'http://127.0.0.1:{server.getsockname()[1]}')
        self.assertEqual(rec['status'], 0); self.assertIn('aborted', rec['capture']['error'])
    def test_a_worker_url_that_is_not_http_is_refused(self):
        done = subprocess.run(['node', os.path.join(Q3, 'fleet_capture.mjs'), 'a11y-worker-2=https://127.0.0.1:8765', 'http://127.0.0.1:8000/p.html', os.path.join(self.tmpdir(), 'x.json')], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(done.returncode, 0); self.assertIn('http: the workers speak no other', done.stderr)
    def tmpdir(self):
        d = tempfile.TemporaryDirectory(); self.addCleanup(d.cleanup); return d.name
    def test_the_server_is_written_by_name_when_given_as_an_address(self):
        done, rec = self.capture(self.serve(200, json.dumps({'url': 'http://192.0.2.7:8000/p.html', 'structure': {}}), delay=0), address='http://192.0.2.7:8000/p.html')
        self.assertEqual(rec['capture']['url'], 'http://capture-host:8000/p.html')


class Check(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name
    def tearDown(self): self.tmp.cleanup()
    def write_readback(self, boxes):
        path = os.path.join(self.dir, 'history-readback.json'); rb.save(path, {'policy': rb.POLICY, 'workers': boxes}); return path
    def oracle(self, **per_file):
        d = os.path.join(self.dir, 'oracle'); os.makedirs(d, exist_ok=True)
        for name, rec in per_file.items(): rb.write_json(os.path.join(d, name + '.json'), rec)
        return d
    def corpus(self, *urls):
        path = os.path.join(self.dir, 'corpus.json'); rb.write_json(path, [{'url': u} for u in urls]); return path
    def stamped(self, links=('a, link',), worker='a11y-worker-2', url='https://example.org/a', transcript=()):
        rec = record(worker=worker, links=links, url=url, transcript=transcript); rec['history'] = cc.history_block(passing_box()); return rec
    def three(self): return {f'a11y-worker-{n}': held_box() for n in (2, 3, 4)}

    def test_readback_with_fewer_than_three_passing_boxes_fails(self):
        self.assertEqual(check.check_readback(self.write_readback({'a11y-worker-2': held_box(), 'a11y-worker-3': held_box(), 'a11y-worker-4': passing_box(visited_after=True)}))[0], check.FAIL)
    def test_readback_where_no_box_showed_the_probe_seeing_history_fails(self):
        boxes = self.three()
        for b in boxes.values(): b['before'] = rb.probe_outcome(record() | {'capturedAt': '2026-10-21T08:00:00.000Z'})
        state, msg = check.check_readback(self.write_readback(boxes)); self.assertEqual(state, check.FAIL); self.assertIn('has not been shown to see history', msg)
    def test_readback_counts_restored_boxes_as_cleared(self):
        boxes = self.three()
        for b in boxes.values(): b['restored'] = {'at': '2026-10-21T13:00:00Z'}
        self.assertEqual(check.check_readback(self.write_readback(boxes))[0], check.OK)
    def test_readback_passes_with_three_clean_boxes(self):
        self.assertEqual(check.check_readback(self.write_readback(self.three()))[0], check.OK)
    def test_one_visited_announcement_in_the_oracle_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a, b = 'https://example.org/a', 'https://example.org/b'
        state, msg = check.check_oracle(self.oracle(a=self.stamped(url=a), b=self.stamped(links=('Cookies, visited, link',), url=b)), rb_path, self.corpus(a, b))
        self.assertEqual(state, check.FAIL); self.assertIn('1 announcements carry `visited`', msg)
    def test_a_visited_in_the_spoken_transcript_alone_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        self.assertEqual(check.check_oracle(self.oracle(a=self.stamped(url=a, transcript=['Cookies, visited, link'])), rb_path, self.corpus(a))[0], check.FAIL)
    def explained(self, found, unexplained=(), pages=None):
        path = os.path.join(self.dir, 'visited-explained.json'); rb.write_json(path, {'oracleVisitedAnnouncements': found, 'explained': found - len(unexplained), 'unexplained': list(unexplained), 'pages': pages or {}}); return path
    def test_visited_announcements_the_emulator_with_no_history_also_makes_are_accepted(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        oracle = self.oracle(a=self.stamped(url=a, links=('Clear filters, visited, link',), transcript=['visited, link, Clear filters']))
        self.assertEqual(check.check_oracle(oracle, rb_path, self.corpus(a), self.explained(1, pages={a: {'announcements': ['Clear filters, visited, link']}}))[0], check.OK)
    def test_visited_announcements_the_emulator_does_not_make_fail_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        oracle = self.oracle(a=self.stamped(url=a, links=('Cookies, visited, link',)))
        self.assertEqual(check.check_oracle(oracle, rb_path, self.corpus(a), self.explained(1, [{'announcement': 'Cookies, visited, link'}], pages={a: {'announcements': ['Cookies, visited, link']}}))[0], check.FAIL)
    def test_an_explanation_of_other_pages_or_strings_with_the_same_count_is_stale_too(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        oracle = self.oracle(a=self.stamped(url=a, links=('Cookies, visited, link',)))
        self.assertEqual(check.check_oracle(oracle, rb_path, self.corpus(a), self.explained(1, pages={a: {'announcements': ['Other, visited, link']}}))[0], check.FAIL)
        self.assertEqual(check.check_oracle(oracle, rb_path, self.corpus(a), self.explained(1, pages={'https://example.org/z': {'announcements': ['Cookies, visited, link']}}))[0], check.FAIL)
    def test_a_visited_in_a_channel_the_checker_did_not_list_is_still_counted(self):
        self.assertEqual(ev.visited_in({'structure': {'buttons': ['Go, visited, button'], 'links': ['a, link']}}), [('buttons', 'Go, visited, button')])
    def test_an_explanation_of_another_count_is_stale_and_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        oracle = self.oracle(a=self.stamped(url=a, links=('Cookies, visited, link',)))
        self.assertEqual(check.check_oracle(oracle, rb_path, self.corpus(a), self.explained(0))[0], check.FAIL)
    def test_the_explanation_names_what_the_emulator_with_no_history_does_not_say(self):
        d = os.path.join(self.dir, 'o'); os.makedirs(d); e = os.path.join(self.dir, 'e'); os.makedirs(e)
        rb.write_json(os.path.join(d, 'p.json'), record(url='https://example.org/p', links=('Same, visited, same page, link', 'Other, visited, link')))
        rb.write_json(os.path.join(e, 'p.run1.json'), {'structure': {'links': ['Same, visited, same page, link', 'Other, link']}})
        out = ev.explain(d, e)
        self.assertEqual((out['oracleVisitedAnnouncements'], out['explained'], [u['announcement'] for u in out['unexplained']]), (2, 1, ['Other, visited, link']))
    def test_a_visited_page_with_no_emulator_run_is_unexplained(self):
        d = os.path.join(self.dir, 'o'); os.makedirs(d); e = os.path.join(self.dir, 'e'); os.makedirs(e)
        rb.write_json(os.path.join(d, 'p.json'), record(url='https://example.org/p', links=('A, visited, link', 'B, link')))
        self.assertEqual(ev.explain(d, e)['unexplained'][0]['why'], 'no emulator run')
    def test_the_committed_summary_must_be_the_corpus_once_each_and_stamped(self):
        rb_path = self.write_readback(self.three()); a, b = 'https://example.org/a', 'https://example.org/b'
        path = os.path.join(self.dir, 'oracle-summary.json'); entry = lambda u, w='a11y-worker-2': {'url': u, 'worker': w, 'history': cc.history_block(passing_box())}
        rb.write_json(path, [entry(a), entry(b)]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.OK)
        rb.write_json(path, [entry(a), entry(a)]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
        rb.write_json(path, [entry(a), entry(b, 'a11y-worker-99')]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
        rb.write_json(path, [entry(a), {'url': b, 'worker': 'a11y-worker-2'}]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
    def test_a_record_without_the_history_block_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        self.assertEqual(check.check_oracle(self.oracle(a=record(url=a)), rb_path, self.corpus(a))[0], check.FAIL)
    def test_a_record_from_a_worker_that_did_not_hold_fails_the_check(self):
        rb_path = self.write_readback(self.three() | {'a11y-worker-9': passing_box()}); a = 'https://example.org/a'      # worker 9 has no after-run probe
        self.assertEqual(check.check_oracle(self.oracle(a=self.stamped(worker='a11y-worker-9', url=a)), rb_path, self.corpus(a))[0], check.FAIL)
    def test_an_oracle_that_is_not_the_corpus_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a, b = 'https://example.org/a', 'https://example.org/b'
        state, msg = check.check_oracle(self.oracle(a=self.stamped(url=a)), rb_path, self.corpus(a, b))
        self.assertEqual(state, check.FAIL); self.assertIn('1 corpus addresses missing', msg)
    def test_a_failed_capture_in_the_oracle_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'; rec = self.stamped(url=a); rec['status'] = 500
        self.assertEqual(check.check_oracle(self.oracle(a=rec), rb_path, self.corpus(a))[0], check.FAIL)
    def test_a_clean_stamped_oracle_of_the_whole_corpus_passes_even_after_the_fleet_is_restored(self):
        boxes = self.three()
        for b in boxes.values(): b['restored'] = {'at': '2026-10-21T13:00:00Z'}
        rb_path = self.write_readback(boxes); a, b = 'https://example.org/a', 'https://example.org/b'
        self.assertEqual(check.check_oracle(self.oracle(a=self.stamped(url=a), b=self.stamped(url=b)), rb_path, self.corpus(a, b))[0], check.OK)
    def test_an_ipv4_literal_is_found_and_a_version_number_is_not(self):
        f = os.path.join(self.dir, 'r.txt')
        write(f, 'Edge 155.0.4283.101 on a11y-worker-2, build 2026.1.1\n'); self.assertEqual(check.check_addresses([f])[0], check.OK)
        write(f, 'worker at http://192.0.2.12:8765\n'); self.assertEqual(check.check_addresses([f])[0], check.FAIL)
    def test_an_attributed_misses_file_that_is_a_list_is_not_a_gate_figure(self):
        rb.write_json(os.path.join(self.dir, 'misses-held-freeze-attributed.json'), [{'class': 'agree'}])
        self.assertEqual(check.check_figures(self.dir)[0], check.PENDING)
    def test_a_gate_figure_that_disagrees_with_its_text_fails(self):
        rb.write_json(os.path.join(self.dir, 'misses-held-freeze.json'), {'gate': {'exact': 4497, 'total': 4607}})
        t = os.path.join(self.dir, 'measure-held-freeze.txt')
        write(t, 'GATE: 4497 of 4607 = 97.61% exact\n'); self.assertEqual(check.check_figures(self.dir)[0], check.OK)
        write(t, 'GATE: 4498 of 4607 = 97.63% exact\n'); self.assertEqual(check.check_figures(self.dir)[0], check.FAIL)

    def test_the_doc_check_accepts_only_one_new_section_after_the_gate(self):
        repo = os.path.join(self.dir, 'repo'); os.makedirs(repo)
        git = lambda *a: subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)
        doc = os.path.join(repo, 'spike.md'); git('init', '-q')
        base = '# Spike\n\n## Q3\n\ntext\n\n## Gate\n\nnot passed\n\n## Follow-ups\n\nmore\n'
        write(doc, base); git('add', '.'); git('commit', '-qm', 'base')
        run = lambda: (lambda cwd: (os.chdir(repo), check.check_doc('spike.md', 'HEAD'), os.chdir(cwd))[1])(os.getcwd())
        self.assertEqual(run()[0], check.PENDING)
        write(doc, base.replace('## Follow-ups', '## Re-measure\n\nfigure\n\n## Follow-ups')); self.assertEqual(run()[0], check.OK)
        write(doc, base.replace('not passed', 'passed').replace('## Follow-ups', '## Re-measure\n\nfigure\n\n## Follow-ups')); self.assertEqual(run()[0], check.FAIL)
        write(doc, base.replace('## Gate\n', '## Gate\n\n## Re-measure\n\nfigure\n')); self.assertEqual(run()[0], check.FAIL)      # inside the Gate section
        write(doc, base.replace('## Q3\n', '## Re-measure\n\nfigure\n\n## Q3\n')); self.assertEqual(run()[0], check.FAIL)


if __name__ == '__main__': unittest.main()
