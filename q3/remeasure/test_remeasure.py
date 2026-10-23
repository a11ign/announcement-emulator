"""python3 -m unittest discover -s q3/remeasure -t q3/remeasure   (from the repository root; needs node, as the capture does)"""
import sys, os, json, shutil, datetime, tempfile, subprocess, unittest, io, contextlib, threading, time, http.server
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, Q3)
import readback as rb, check, corpus_capture as cc, policy_override as po, explain_visited as ev, make_views
sys.path.insert(0, os.path.join(Q3, 'replay')); sys.path.insert(0, os.path.join(Q3, 'gate'))
import replay_readback as rrb, make_freeze

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
    def test_a_static_copy_is_captured_at_its_address_and_the_record_stays_the_originals(self):
        out = os.path.join(self.dir, 'oracle'); url = 'https://example.org/live/page'
        entries = cc.entries_of([{'url': url, 'role': 'training'}], 'http://capture-host:8001/')
        self.assertEqual(entries[0]['address'], f'http://capture-host:8001/{cc.slug_of(url)}/index.html')
        s = cc.run(entries, self.workers('a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'), self.readback, out, self.stub, log=lambda *a, **k: None)
        rec = rb.read_json(os.path.join(out, cc.slug_of(url) + '.json'))
        self.assertEqual((s['captured'], rec['staticOf'], rec['capture']['url']), (1, url, entries[0]['address']))
    def test_the_views_give_the_scripts_the_address_each_needs(self):
        src, orig, run = (os.path.join(self.dir, d) for d in ('src', 'orig', 'run')); os.makedirs(src); url = 'https://example.org/live/page'
        rb.write_json(os.path.join(src, cc.slug_of(url) + '.json'), record(url='http://capture-host:8001/x/index.html') | {'staticOf': url, 'role': 'training'})
        make_views.main(src, orig, run, 'http://127.0.0.1:8001/')
        self.assertEqual(rb.read_json(os.path.join(orig, cc.slug_of(url) + '.json'))['capture']['url'], url)
        self.assertEqual(rb.read_json(os.path.join(run, cc.slug_of(url) + '.json'))['capture']['url'], f'http://127.0.0.1:8001/{cc.slug_of(url)}/index.html')
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


CHROME = os.path.join(os.environ.get('EMU_DOWNLOADS') or os.path.expanduser('~/spikes/announcement-emulator-5661'), 'chrome155/chrome-linux64/chrome')
PAGE = '''<!doctype html><html lang="en"><head><title>Original</title><link rel="stylesheet" href="/style.css"><script>document.title = "Changed by script"</script></head>
<body><h1 onclick="alert(1)">Heading</h1><a id=self href="/page.html">Itself</a> <a id=frag href="#late">Place</a> <a id=other href="other.html">Other</a>
<iframe src="/inner.html"></iframe><input id=name value="typed"><noscript><p>no script</p></noscript><script>document.body.insertAdjacentHTML("beforeend", "<p id=late>added by script</p>")</script></body></html>'''


@unittest.skipUnless(os.path.exists(CHROME), 'the emulator\'s Chrome is not built here (setup.sh)')
class Snapshot(unittest.TestCase):
    def test_a_copy_is_inert_self_contained_and_keeps_same_page_links_same_page(self):
        files = {'/page.html': ('text/html', PAGE), '/style.css': ('text/css', 'h1 { background: url(bg.png) }'), '/inner.html': ('text/html', '<!doctype html><title>inner</title><p>inside</p>')}
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                kind, body = files.get(self.path, ('text/plain', 'x')); self.send_response(200); self.send_header('content-type', kind); self.end_headers(); self.wfile.write(body.encode())
            def log_message(self, *a): pass
        server = http.server.HTTPServer(('127.0.0.1', 0), H); threading.Thread(target=server.serve_forever, daemon=True).start(); self.addCleanup(server.shutdown); self.addCleanup(server.server_close)
        base = f'http://127.0.0.1:{server.server_port}'; out = tempfile.TemporaryDirectory(); self.addCleanup(out.cleanup)
        done = subprocess.run(['node', os.path.join(HERE, 'snapshot.mjs'), base + '/page.html', out.name], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        html = open(os.path.join(out.name, 'index.html')).read()
        self.assertNotIn('<script', html); self.assertNotIn('onclick', html); self.assertNotIn('no script', html)           # inert
        self.assertIn('added by script', html); self.assertIn('<title>Changed by script</title>', html)                    # what the page did before the copy is kept
        self.assertIn(f'url("{base}/bg.png")', html); self.assertNotIn('<link rel="stylesheet"', html)                        # the stylesheet is in, its url() absolute
        self.assertIn('id="self" href="index.html"', html); self.assertIn('id="frag" href="#late"', html); self.assertIn(f'id="other" href="{base}/other.html"', html)
        self.assertNotIn('data-snap', html)                                                                                    # nothing of the tool's own marks is left
        self.assertIn('srcdoc=', html); self.assertIn('inside', html); self.assertIn('value="typed"', html)                   # the same-origin iframe is inline, a form value is kept

    def test_frames_can_be_written_as_documents_and_lazy_loading_taken_off(self):
        files = {'/page.html': ('text/html', '<!doctype html><title>p</title><iframe loading="lazy" src="/inner.html"></iframe><img loading="lazy" src="/i.png" alt="x">'), '/inner.html': ('text/html', '<!doctype html><title>inner</title><p>inside</p>')}
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                kind, body = files.get(self.path, ('image/png', 'x')); self.send_response(200); self.send_header('content-type', kind); self.end_headers(); self.wfile.write(body.encode())
            def log_message(self, *a): pass
        server = http.server.HTTPServer(('127.0.0.1', 0), H); threading.Thread(target=server.serve_forever, daemon=True).start(); self.addCleanup(server.shutdown); self.addCleanup(server.server_close)
        out = tempfile.TemporaryDirectory(); self.addCleanup(out.cleanup)
        done = subprocess.run(['node', os.path.join(HERE, 'snapshot.mjs'), f'http://127.0.0.1:{server.server_port}/page.html', out.name, '--frames', 'files', '--lazy', 'eager'], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        html = open(os.path.join(out.name, 'index.html')).read()
        self.assertIn('src="frame-0.html"', html); self.assertNotIn('srcdoc', html); self.assertNotIn('loading="lazy"', html); self.assertIn('inside', open(os.path.join(out.name, 'frame-0.html')).read())


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
    def test_a_run_without_a_before_probe_takes_its_control_from_the_run_that_had_one(self):
        boxes = self.three()
        for b in boxes.values(): del b['before']
        path = self.write_readback(boxes); self.assertEqual(check.check_readback(path)[0], check.FAIL)
        other = os.path.join(self.dir, 'other.json'); rb.save(other, {'policy': rb.POLICY, 'workers': self.three()})
        self.assertEqual(check.check_readback(path, other)[0], check.OK)
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
        rb.write_json(path, [{**entry(a), 'status': 200}, {**entry(b), 'status': 200}]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.OK)
        rb.write_json(path, [entry(a), entry(a)]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
        rb.write_json(path, [entry(a), entry(b, 'a11y-worker-99')]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
        rb.write_json(path, [entry(a), {'url': b, 'worker': 'a11y-worker-2'}]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
        rb.write_json(path, [entry(a), {**entry(b), 'status': 500}]); self.assertEqual(check.check_summary(path, rb_path, self.corpus(a, b))[0], check.FAIL)
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
    def test_a_static_copy_counts_as_the_address_it_is_a_copy_of(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        rec = self.stamped(url=f'http://capture-host:8001/{cc.slug_of(a)}/index.html'); rec['staticOf'] = a
        self.assertEqual(check.check_oracle(self.oracle(a=rec), rb_path, self.corpus(a))[0], check.OK)
    def test_a_copy_read_at_another_address_than_its_own_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        rec = self.stamped(url='https://example.org/a'); rec['staticOf'] = a      # `staticOf` on a record of the live address
        self.assertEqual(check.check_oracle(self.oracle(a=rec), rb_path, self.corpus(a))[0], check.FAIL)
    def test_an_extra_record_for_an_address_already_covered_fails_the_check(self):
        rb_path = self.write_readback(self.three()); a = 'https://example.org/a'
        oracle = self.oracle(a=self.stamped(url=a), b=self.stamped(url=a))
        self.assertEqual(check.check_oracle(oracle, rb_path, self.corpus(a))[0], check.FAIL)
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
    def test_a_figure_that_is_not_on_the_page_fails_the_check(self):
        rb.write_json(os.path.join(self.dir, 'misses-held-freeze.json'), {'gate': {'exact': 4497, 'total': 4607}})
        write(os.path.join(self.dir, 'measure-held-freeze.txt'), 'GATE: 4497 of 4607 = 97.61% exact\n')
        page = os.path.join(self.dir, 'page.md')
        write(page, 'the figure is 4,497 of 4,607\n'); self.assertEqual(check.check_figures(self.dir, page)[0], check.OK)
        write(page, 'the figure is 4,498 of 4,607\n'); self.assertEqual(check.check_figures(self.dir, page)[0], check.FAIL)
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


    def doc_repo(self, base):
        """A repository whose page is `base`, committed; returns a function that checks the working page against that commit."""
        repo = os.path.join(self.dir, 'doc-repo'); os.makedirs(repo)
        git = lambda *a: subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)
        git('init', '-q'); doc = os.path.join(repo, 'spike.md'); write(doc, base); git('add', '.'); git('commit', '-qm', 'base')
        def run(text):
            write(doc, text); cwd = os.getcwd(); os.chdir(repo)
            try: return check.check_doc('spike.md', 'HEAD')
            finally: os.chdir(cwd)
        return run

    def test_once_the_base_has_the_re_measure_section_one_subsection_at_its_end_is_accepted_and_nothing_else(self):
        base = '# Spike\n\n## Gate\n\nnot passed\n\n## Re-measure\n\nfigure\n\n### Drift-free re-score\n\nstatic\n\n## Follow-ups\n\nmore\n'
        run = self.doc_repo(base); sub = '### Scripted replay: the same bytes, scripts included\n\nreplayed\n\n'
        self.assertEqual(run(base)[0], check.PENDING)
        self.assertEqual(run(base.replace('## Follow-ups', sub + '## Follow-ups'))[0], check.OK)
        self.assertEqual(run(base.replace('## Follow-ups', sub.rstrip('\n') + '\n\n## Follow-ups'))[0], check.OK)      # however the diff places the blank line
        # a second subsection, a section, a line of an earlier part, or an edit of an old line is refused
        self.assertEqual(run(base.replace('## Follow-ups', sub + '### And another\n\nmore\n\n## Follow-ups'))[0], check.FAIL)
        self.assertEqual(run(base.replace('## Follow-ups', sub + '## A new section\n\ntext\n\n## Follow-ups'))[0], check.FAIL)
        self.assertEqual(run(base.replace('static', 'static, changed').replace('## Follow-ups', sub + '## Follow-ups'))[0], check.FAIL)
        self.assertEqual(run(base.replace('figure\n', 'figure\n\nan extra paragraph\n'))[0], check.FAIL)      # text added inside the section, not a subsection
        self.assertEqual(run(base.replace('### Drift-free re-score', sub + '### Drift-free re-score'))[0], check.FAIL)      # not at the end of the section
        self.assertEqual(run(base.replace('## Gate\n', '## Gate\n\n' + sub))[0], check.FAIL)      # inside another section
        self.assertEqual(run(base.replace('## Follow-ups', '#### A smaller heading\n\ntext\n\n## Follow-ups'))[0], check.FAIL)      # not a `### `

    def test_a_subsection_at_the_very_end_of_the_page_is_at_the_end_of_re_measure_too(self):
        base = '# Spike\n\n## Gate\n\nnot passed\n\n## Re-measure\n\nfigure\n'
        self.assertEqual(self.doc_repo(base)(base + '\n### Scripted replay\n\nreplayed\n')[0], check.OK)

    def test_the_page_is_found_in_the_base_from_any_directory_and_by_an_absolute_path(self):
        base = '# Spike\n\n## Gate\n\nnot passed\n\n## Re-measure\n\nfigure\n\n## Follow-ups\n\nmore\n'
        repo = os.path.join(self.dir, 'doc-repo2'); os.makedirs(os.path.join(repo, 'docs'))
        git = lambda *a: subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)
        doc = os.path.join(repo, 'docs', 'spike.md'); git('init', '-q'); write(doc, base); git('add', '.'); git('commit', '-qm', 'base')
        write(doc, base.replace('## Follow-ups', '### Scripted replay\n\nreplayed\n\n## Follow-ups')); cwd = os.getcwd()
        try:
            os.chdir(os.path.join(repo, 'docs')); self.assertEqual(check.check_doc('spike.md', 'HEAD')[0], check.OK)      # from the page's own directory
            os.chdir(repo); self.assertEqual(check.check_doc(doc, 'HEAD')[0], check.OK)      # an absolute path
            os.chdir(os.path.join(repo, 'docs')); self.assertEqual(check.check_doc(doc, 'HEAD')[0], check.OK)      # an absolute path from elsewhere in the repository
        finally: os.chdir(cwd)

    def write_manifest(self, urls, **over):
        path = os.path.join(self.dir, 'archive-manifest.json')
        rb.write_json(path, {'pages': [{'url': u, 'slug': cc.slug_of(u), 'archive': f'archives/{cc.slug_of(u)}.flows', 'sha256': f'{i + 1:064x}', **over} for i, u in enumerate(urls)]}); return path

    def test_the_manifest_is_one_archive_per_corpus_address_each_with_its_sha256(self):
        a, b = 'https://example.org/a', 'https://example.org/b'; corpus = self.corpus(a, b)
        self.assertEqual(check.check_manifest(os.path.join(self.dir, 'none.json'), corpus)[0], check.PENDING)
        self.assertEqual(check.check_manifest(self.write_manifest([a, b]), corpus)[0], check.OK)
        self.assertEqual(check.check_manifest(self.write_manifest([a]), corpus)[0], check.FAIL)            # an address without an archive
        self.assertEqual(check.check_manifest(self.write_manifest([a, a]), corpus)[0], check.FAIL)         # one twice
        self.assertEqual(check.check_manifest(self.write_manifest([a, b], sha256='nothex'), corpus)[0], check.FAIL)
        self.assertEqual(check.check_manifest(self.write_manifest([a, b], archive='archives/same.flows'), corpus)[0], check.FAIL)      # two addresses, one file
        self.assertEqual(check.check_manifest(self.write_manifest([a, b], mainStatus=503), corpus)[0], check.FAIL)      # recorded as an error page and served as one: the worker refuses it
        self.assertEqual(check.check_manifest(self.write_manifest([a, b], mainStatus=503, servedStatus=200), corpus)[0], check.OK)

    def served(self, manifest, **per_page):
        """A join summary: every page served `sha`, with the differences given (page -> list)."""
        pages = []
        for p in rb.read_json(manifest)['pages']:
            sha = per_page.get('sha', {}).get(p['url'], p['sha256']); diffs = per_page.get('differences', {}).get(p['url'], [])
            entry = {'url': p['url'], 'slug': p['slug'], 'fleet': {'archiveSha256': p['sha256']}, 'emulator': {'gate.run1': {'archiveSha256': sha}}, 'differences': [{'run': 'gate.run1', 'kind': 'k', 'request': r} for r in diffs]}
            if p['url'] in per_page.get('explained', {}): entry['explained'] = per_page['explained'][p['url']]
            if p['url'] in per_page.get('missing', {}): entry = {'url': p['url'], 'slug': p['slug'], 'missing': '0 fleet logs, 4 emulator logs'}
            pages.append(entry)
        path = os.path.join(self.dir, 'served-identically.json'); rb.write_json(path, {'pages': pages}); return path

    def test_served_identically_is_proven_by_the_join_and_each_refusal_is_a_failure(self):
        a, b = 'https://example.org/a', 'https://example.org/b'; m = self.write_manifest([a, b])
        self.assertEqual(check.check_served(os.path.join(self.dir, 'none.json'), m)[0], check.PENDING)
        self.assertEqual(check.check_served(self.served(m), m)[0], check.OK)
        self.assertEqual(check.check_served(self.served(m, differences={a: ['GET https://example.org/late.js']}), m)[0], check.FAIL)         # answered on one side only, unexplained
        self.assertEqual(check.check_served(self.served(m, differences={a: ['GET https://example.org/late.js']}, explained={a: 'a timer'}), m)[0], check.OK)      # explained in the write-up
        self.assertEqual(check.check_served(self.served(m, sha={b: 'f' * 64}), m)[0], check.FAIL)           # a side was served another archive than the manifest's
        self.assertEqual(check.check_served(self.served(m, missing={b: 1}), m)[0], check.FAIL)              # a page without its logs
        rb.write_json(os.path.join(self.dir, 'served-identically.json'), {'pages': rb.read_json(self.served(m))['pages'][:1]}); self.assertEqual(check.check_served(os.path.join(self.dir, 'served-identically.json'), m)[0], check.FAIL)      # an address missing

    def eleven(self, edit=None):
        os.makedirs(os.path.join(self.dir, 'evidence'), exist_ok=True); write(os.path.join(self.dir, 'evidence', 'one.json'), '{}')
        misses = [{'page': f'p{i}', 'channel': 'formFields', 'expected': f'Field {i}, check box', 'class': 'method', 'evidence': ['evidence/one.json']} for i in range(11)]
        if edit: edit(misses)
        path = os.path.join(self.dir, 'misses-explained.json'); rb.write_json(path, {'misses': misses}); return path

    def test_the_eleven_misses_are_each_classed_with_evidence_or_kept_unexplained_with_what_was_tried(self):
        page = os.path.join(self.dir, 'page.md'); write(page, '\n'.join(f'Field {i}, check box' for i in range(11)))
        self.assertEqual(check.check_explained(os.path.join(self.dir, 'none.json'), self.dir)[0], check.PENDING)
        self.assertEqual(check.check_explained(self.eleven(), self.dir, page)[0], check.OK)
        self.assertEqual(check.check_explained(self.eleven(lambda m: m.pop()), self.dir, page)[0], check.FAIL)                                  # fewer than 11
        self.assertEqual(check.check_explained(self.eleven(lambda m: m.append(dict(m[0]))), self.dir, page)[0], check.FAIL)                      # more than 11
        self.assertEqual(check.check_explained(self.eleven(lambda m: m[0].update(evidence=[])), self.dir, page)[0], check.FAIL)                  # a class without evidence
        self.assertEqual(check.check_explained(self.eleven(lambda m: m[0].update(evidence=['evidence/gone.json'])), self.dir, page)[0], check.FAIL)      # evidence that is not there
        self.assertEqual(check.check_explained(self.eleven(lambda m: m[0].update(**{'class': 'a bug I think'})), self.dir, page)[0], check.FAIL)
        self.assertEqual(check.check_explained(self.eleven(lambda m: m[0].update(**{'class': 'unexplained'})), self.dir, page)[0], check.FAIL)      # unexplained, and nothing said of what was tried
        self.assertEqual(check.check_explained(self.eleven(lambda m: m[0].update(**{'class': 'unexplained', 'tried': 'the sweep order, the frames, the focus'})), self.dir, page)[0], check.OK)
        write(page, 'Field 1, check box'); self.assertEqual(check.check_explained(self.eleven(), self.dir, page)[0], check.FAIL)                  # the page does not name them

    def test_the_replay_readback_check_wants_three_boxes_behind_the_server_and_honest_flags(self):
        path = os.path.join(self.dir, 'replay-readback.json'); box = lambda: {'proxy': {'server': 'capture-host:3202', 'readAt': '2026-10-21T09:00:00Z'}, 'certificate': {'thumbprint': 'A' * 40, 'readAt': '2026-10-21T09:01:00Z'},
                                                                         'on': {'capturedAt': '2026-10-21T09:05:00.000Z', 'read': True}, 'after-run': {'capturedAt': '2026-10-21T11:00:00.000Z', 'read': True}}
        self.assertEqual(check.check_replay_readback(path)[0], check.PENDING)
        rrb.save(path, {'workers': {f'a11y-worker-{n}': box() for n in (2, 3, 4)}}); self.assertEqual(check.check_replay_readback(path)[0], check.OK)
        rrb.save(path, {'workers': {f'a11y-worker-{n}': box() for n in (2, 3)}}); self.assertEqual(check.check_replay_readback(path)[0], check.FAIL)
        data = rb.read_json(path); data['workers']['a11y-worker-2']['passed'] = False; data['workers']['a11y-worker-4'] = dict(box(), passed=True, heldRun=True, restoredOk=False); rb.write_json(path, data)
        self.assertEqual(check.check_replay_readback(path)[0], check.FAIL)      # a stored flag that is not what the readings give

    def test_every_replay_record_names_the_archive_the_manifest_holds_for_its_address(self):
        a = 'https://example.org/a'; m = self.write_manifest([a]); sha = rb.read_json(m)['pages'][0]['sha256']; path = os.path.join(self.dir, 'replay-readback.json')
        box = {'proxy': {'server': 'x', 'readAt': '2026-10-21T09:00:00Z'}, 'certificate': {'readAt': '2026-10-21T09:01:00Z'}, 'on': {'capturedAt': '2026-10-21T09:05:00.000Z', 'read': True}, 'after-run': {'capturedAt': '2026-10-21T11:00:00.000Z', 'read': True}}
        rrb.save(path, {'workers': {'a11y-worker-2': box}})
        rec = lambda **block: {'worker': 'a11y-worker-2', 'capture': {'url': a}, 'replay': {'archiveSha256': sha, 'unmatched': 3, **block}}
        ok = self.oracle(a=rec()); self.assertEqual(check.check_replay_stamps(ok, m, path)[0], check.OK)
        self.assertEqual(check.check_replay_stamps(self.oracle(a=rec(archiveSha256='0' * 64)), m, path)[0], check.FAIL)      # another archive than the manifest's
        self.assertEqual(check.check_replay_stamps(self.oracle(a=rec(unmatched=None)), m, path)[0], check.FAIL)
        self.assertEqual(check.check_replay_stamps(self.oracle(a={'worker': 'a11y-worker-2', 'capture': {'url': a}}), m, path)[0], check.FAIL)      # no block at all
        self.assertEqual(check.check_replay_stamps(self.oracle(a=rec() | {'worker': 'a11y-worker-9'}), m, path)[0], check.FAIL)      # a box that did not hold


class GateChecks(unittest.TestCase):
    """The checks of the Gate's re-run on new pages (A11-166): the freeze, the consent report, the comparable account, the attribution of every miss, the verdict, the labels."""
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name
    def tearDown(self): self.tmp.cleanup()

    def git(self, repo, *args, when=None):
        env = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t', **({'GIT_COMMITTER_DATE': when, 'GIT_AUTHOR_DATE': when} if when else {})}
        return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True, text=True, env=env).stdout.strip()

    def repo(self):
        """A repository with the emulator and its harness, A11-164's table and a merge for it, then one commit of tooling after the frozen one. Returns (path, frozen commit, A11-164's commit)."""
        repo = os.path.join(self.dir, 'repo'); os.makedirs(repo); self.git(repo, 'init', '-q', '-b', 'main')
        files = {'emu/session.mjs': 'one', 'emu/langnames/language-names.json': '{}', **{p: p for p in check.FREEZE_OBJECTS if p != 'emu'}}
        for path, text in files.items(): os.makedirs(os.path.dirname(os.path.join(repo, path)), exist_ok=True); write(os.path.join(repo, path), text)
        self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'A11-164 merged', when='2026-10-21T20:00:00Z'); table = self.git(repo, 'rev-parse', 'HEAD')
        write(os.path.join(repo, 'README.md'), 'x'); self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'the freeze', when='2026-10-22T08:00:00Z'); frozen = self.git(repo, 'rev-parse', 'HEAD')
        os.makedirs(os.path.join(repo, 'q3/replay')); write(os.path.join(repo, 'q3/replay/addon.py'), 'tooling'); self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'tooling after the freeze', when='2026-10-22T09:00:00Z')
        return repo, frozen, table

    def freeze(self, repo, frozen, table, **edit):
        freeze = make_freeze.freeze_of(repo, frozen, {'A11-164': table}, datetime.datetime(2026, 10, 23, 10, 0, 0, tzinfo=datetime.timezone.utc)) | edit
        path = os.path.join(repo, 'freeze.json'); rb.write_json(path, freeze); self.git(repo, 'add', 'freeze.json'); self.git(repo, 'commit', '-qm', 'name the freeze', when='2026-10-23T10:05:00Z'); return path

    def summary(self, *stamps):
        path = os.path.join(self.dir, 'oracle-summary.json'); rb.write_json(path, [{'url': f'https://e.org/{i}', 'capturedAt': t} for i, t in enumerate(stamps)]); return path

    def test_a_freeze_is_the_commit_the_emulator_and_harness_still_are_with_the_table_named_before_every_capture(self):
        repo, frozen, table = self.repo(); path = self.freeze(repo, frozen, table)
        later = self.summary('2026-10-23T11:00:00.000Z', '2026-10-23T12:00:00.000Z')
        self.assertEqual(check.check_freeze(path, repo, None, later)[0], check.OK)
        self.assertEqual(check.check_freeze(path, repo, None, os.path.join(self.dir, 'none.json'))[0], check.PENDING)      # nothing captured yet: the freeze is in order, and nothing to compare it with
        self.assertEqual(check.check_freeze(os.path.join(self.dir, 'none.json'), repo)[0], check.PENDING)

    def test_a_capture_at_or_before_the_freeze_was_named_fails(self):
        repo, frozen, table = self.repo(); path = self.freeze(repo, frozen, table)
        self.assertEqual(check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z', '2026-10-23T10:00:00.000Z'))[0], check.FAIL)      # at the instant it was named
        self.assertEqual(check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z', '2026-10-23T09:59:59.000Z'))[0], check.FAIL)
        self.assertEqual(check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z', '2026-10-23T10:01:00.000Z'))[0], check.FAIL)      # named, but before freeze.json was committed (10:05)
        self.assertEqual(check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z', None))[0], check.FAIL)      # a record that says no time

    def test_a_change_to_the_emulator_or_its_harness_or_the_measure_after_the_freeze_fails(self):
        for changed in ('emu/session.mjs', 'q3/emulate.py', 'q3/sweep.py', 'q3/livepage.py', 'q3/shapes.py', 'q3/measure.py', 'q3/attribute.py', 'q3/split.py'):
            repo, frozen, table = self.repo(); path = self.freeze(repo, frozen, table)
            write(os.path.join(repo, changed), 'changed'); self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'a fix', when='2026-10-23T12:00:00Z')
            state, msg = check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z')); self.assertEqual(state, check.FAIL, changed); self.assertIn('emu' if changed.startswith('emu/') else changed, msg)
            shutil.rmtree(repo)

    def test_a_new_file_under_the_emulator_is_a_change_of_its_tree(self):
        repo, frozen, table = self.repo(); path = self.freeze(repo, frozen, table)
        write(os.path.join(repo, 'emu/new.py'), 'x'); self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'a new file', when='2026-10-23T12:00:00Z')
        self.assertEqual(check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z'))[0], check.FAIL)

    def test_a_freeze_that_names_other_objects_or_a_commit_that_is_not_behind_this_one_or_has_no_table_fails(self):
        repo, frozen, table = self.repo(); good = self.freeze(repo, frozen, table); times = self.summary('2026-10-23T11:00:00.000Z')
        bad = rb.read_json(good); bad['objects']['q3/sweep.py'] = '0' * 40; rb.write_json(good, bad); self.assertEqual(check.check_freeze(good, repo, None, times)[0], check.FAIL)
        bad = rb.read_json(good); bad['objects'].pop('emu'); bad['objects']['q3/sweep.py'] = self.git(repo, 'rev-parse', f'{frozen}:q3/sweep.py'); rb.write_json(good, bad); self.assertEqual(check.check_freeze(good, repo, None, times)[0], check.FAIL)      # a part not named
        bad = rb.read_json(good); bad['commit'] = '1' * 40; rb.write_json(good, bad); self.assertEqual(check.check_freeze(good, repo, None, times)[0], check.FAIL)      # not a commit at all
        rb.write_json(good, rb.read_json(good) | {'commit': frozen, 'objects': make_freeze.freeze_of(repo, frozen, {'A11-164': table})['objects'], 'includes': {}}); self.assertEqual(check.check_freeze(good, repo, None, times)[0], check.FAIL)      # does not say it has A11-164
        self.git(repo, 'checkout', '-qf', '-b', 'other', table); write(os.path.join(repo, 'x.txt'), 'x'); self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'beside', when='2026-10-22T10:00:00Z')
        beside = self.git(repo, 'rev-parse', 'HEAD'); self.git(repo, 'checkout', '-qf', 'main'); rb.write_json(good, rb.read_json(good) | {'commit': beside, 'includes': {'A11-164': table}})
        self.assertEqual(check.check_freeze(good, repo, None, times)[0], check.FAIL)      # a commit that is not an ancestor of the branch

    def test_the_table_must_be_in_the_frozen_commit(self):
        repo = os.path.join(self.dir, 'repo2'); os.makedirs(repo); self.git(repo, 'init', '-q', '-b', 'main')
        for path in check.FREEZE_OBJECTS:
            if path != 'emu': os.makedirs(os.path.dirname(os.path.join(repo, path)), exist_ok=True); write(os.path.join(repo, path), path)
        os.makedirs(os.path.join(repo, 'emu')); write(os.path.join(repo, 'emu/session.mjs'), 'x'); self.git(repo, 'add', '.'); self.git(repo, 'commit', '-qm', 'no table', when='2026-10-21T20:00:00Z'); head = self.git(repo, 'rev-parse', 'HEAD')
        path = self.freeze(repo, head, head); state, msg = check.check_freeze(path, repo, None, self.summary('2026-10-23T11:00:00.000Z')); self.assertEqual(state, check.FAIL); self.assertIn('language-names.json', msg)

    def test_a_freeze_named_before_its_commit_was_made_or_committed_before_it_was_named_fails(self):
        repo, frozen, table = self.repo(); times = self.summary('2026-10-23T11:00:00.000Z')
        path = self.freeze(repo, frozen, table, namedAt='2026-10-22T07:00:00Z'); self.assertEqual(check.check_freeze(path, repo, None, times)[0], check.FAIL)      # before the frozen commit was made (08:00)
        path = self.freeze(repo, frozen, table, namedAt='2026-10-23T10:30:00Z'); self.assertEqual(check.check_freeze(path, repo, None, times)[0], check.FAIL)      # after freeze.json was committed (10:05)

    def test_the_freeze_is_named_from_a_commit_and_refuses_one_that_lacks_what_it_must_contain(self):
        repo, frozen, table = self.repo(); freeze = make_freeze.freeze_of(repo, frozen, {'A11-164': table})
        self.assertEqual(sorted(freeze['objects']), sorted(check.FREEZE_OBJECTS)); self.assertEqual(freeze['commit'], frozen); self.assertEqual(freeze['includes'], {'A11-164': table}); self.assertEqual(freeze['objects']['emu'], self.git(repo, 'rev-parse', f'{frozen}:emu'))
        with self.assertRaises(SystemExit): make_freeze.freeze_of(repo, table, {'A11-164': frozen})      # the frozen commit does not contain a commit that comes after it

    def gate(self, exact=96, total=100): return {'gate': {'exact': exact, 'total': total}, 'top': ['a + b'], 'pages': [{'url': 'https://e.org/p', 'status': 'comparable'}],
                                                  'misses': [{'url': 'https://e.org/p', 'channel': 'links', 'i': i, 'expected': f'Link {i}, link', 'shape': ['a', 'b']} for i in range(total - exact)] + [{'url': 'https://e.org/q', 'channel': 'frames', 'i': 0, 'expected': 'f', 'shape': ['a', 'b']},
                                                                                                                                                                   {'url': 'https://e.org/q', 'channel': 'links', 'i': 9, 'expected': 'other shape', 'shape': ['c']}]}

    def attributed(self, gate, edit=None, cls='emulator bug'):
        os.makedirs(os.path.join(self.dir, 'evidence'), exist_ok=True); write(os.path.join(self.dir, 'evidence', 'one.json'), '{}')
        entries = [{'page': m['url'], 'channel': m['channel'], 'i': m['i'], 'expected': m['expected'], 'class': cls, 'evidence': ['evidence/one.json']} for m in check.gate_misses(gate)]
        if edit: edit(entries)
        path = os.path.join(self.dir, 'misses-attributed.json'); rb.write_json(path, {'misses': entries}); return path

    def test_every_miss_of_the_gate_figure_is_attributed_once_and_nothing_else_is(self):
        gate = self.gate(); page = os.path.join(self.dir, 'page.md'); write(page, '\n'.join(f'Link {i}, link' for i in range(4)))
        self.assertEqual(len(check.gate_misses(gate)), 4)      # not the frames channel, not another shape
        self.assertEqual(check.check_explained(self.attributed(gate), self.dir, page, gate)[0], check.OK)
        self.assertEqual(check.check_explained(self.attributed(gate, lambda e: e.pop()), self.dir, page, gate)[0], check.FAIL)      # one not attributed
        self.assertEqual(check.check_explained(self.attributed(gate, lambda e: e.append(dict(e[0]))), self.dir, page, gate)[0], check.FAIL)      # one attributed twice
        self.assertEqual(check.check_explained(self.attributed(gate, lambda e: e.append(dict(e[0], i=77))), self.dir, page, gate)[0], check.FAIL)      # a miss that is not one
        self.assertEqual(check.check_explained(self.attributed(gate, lambda e: e[0].update(i=5)), self.dir, page, gate)[0], check.FAIL)      # another place in the list is another miss
        self.assertEqual(check.check_explained(self.attributed(gate, lambda e: e[0].update(evidence=[])), self.dir, page, gate)[0], check.FAIL)
        self.assertEqual(check.check_explained(self.attributed(gate), self.dir, page, self.gate(exact=95))[0], check.FAIL)      # a figure whose misses are not the file's
        write(page, 'Link 1, link'); self.assertEqual(check.check_explained(self.attributed(gate), self.dir, page, gate)[0], check.FAIL)      # not named on the page

    def test_two_misses_with_the_same_words_at_two_places_of_one_list_are_two_misses(self):
        gate = self.gate(); gate['misses'] = [m | {'expected': 'Same, link'} for m in gate['misses']]
        self.assertEqual(len(check.gate_misses(gate)), 4); page = os.path.join(self.dir, 'p.md'); write(page, 'Same, link')
        self.assertEqual(check.check_explained(self.attributed(gate), self.dir, page, gate)[0], check.OK)
        self.assertEqual(check.check_explained(self.attributed(gate, lambda e: e.__setitem__(1, dict(e[0]))), self.dir, page, gate)[0], check.FAIL)      # the first twice, the second never

    def test_the_old_eleven_check_is_as_it_was_without_a_misses_file(self):
        self.assertEqual(check.EXPECTED_MISSES, 11); self.assertEqual(check.check_explained(os.path.join(self.dir, 'none.json'), self.dir)[0], check.PENDING)

    def test_the_gate_is_passed_only_at_98_percent_with_every_miss_an_emulator_bug_or_windows_only(self):
        cases = [(98, 100, ['emulator bug', 'Windows-only'], 'passed'), (97, 100, ['emulator bug'], 'not passed'), (100, 100, [], 'passed'), (98, 100, ['emulator bug', 'method'], 'not passed'), (99, 100, ['unexplained'], 'not passed'),
                 (990, 1000, ['Windows-only'] * 10, 'passed'), (979, 1000, ['Windows-only'] * 21, 'not passed'), (980, 1000, ['Windows-only'] * 20, 'passed')]
        for exact, total, classes, expected in cases: self.assertEqual(check.verdict_of({'exact': exact, 'total': total}, [{'class': c} for c in classes]), expected, (exact, total, classes))

    def verdict_files(self, exact, total, classes):
        gate = self.gate(exact, total); misses = os.path.join(self.dir, 'misses-held-freeze.json'); rb.write_json(misses, gate)
        path = os.path.join(self.dir, 'misses-attributed.json'); rb.write_json(path, {'misses': [{'class': c} for c in classes]}); return misses, path

    def test_the_page_says_the_verdict_the_figure_and_classes_give_once_in_bold_in_the_new_subsection_and_not_the_other(self):
        page = os.path.join(self.dir, 'page.md'); head = '## Gate\n\n**The Gate is not passed**\n\n## Re-measure\n\n### Earlier\n\n**The Gate is passed** (an earlier reading)\n\n### The Gate on new pages\n\n'
        misses, attributed = self.verdict_files(97, 100, ['emulator bug'] * 3)
        write(page, head + 'text. **The Gate is not passed**\n\n## Follow-ups\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.OK)      # the earlier and the Gate section's sentences are not the subsection's
        write(page, head + 'text. **The Gate is passed**\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.FAIL)      # the other call
        write(page, head + 'text. The Gate is not passed\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.FAIL)      # not in bold
        write(page, head + '**The Gate is not passed** and **The Gate is not passed**\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.FAIL)      # twice
        write(page, head + '**The Gate is not passed** **The Gate is passed**\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.FAIL)      # both
        misses, attributed = self.verdict_files(98, 100, ['Windows-only', 'method']); write(page, head + '**The Gate is passed**\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.FAIL)      # a method miss fails the Gate
        write(page, head + '**The Gate is not passed**\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.OK)
        self.assertEqual(check.check_verdict(misses, os.path.join(self.dir, 'none.json'), page)[0], check.PENDING)
        write(page, '## Gate\n\n**The Gate is not passed**\n'); self.assertEqual(check.check_verdict(misses, attributed, page)[0], check.PENDING)      # no subsection yet

    def test_the_comparable_account_is_of_the_figures_pages_with_one_reason_for_each_that_is_not(self):
        misses = os.path.join(self.dir, 'misses-held-freeze.json'); rb.write_json(misses, {'pages': [{'url': 'https://e.org/a', 'status': 'comparable'}, {'url': 'https://e.org/b', 'status': 'unstable: the two emulator runs differ'}]})
        path = os.path.join(self.dir, 'comparability.json'); account = lambda **b: {'comparable': 1, 'total': 2, 'pages': [{'url': 'https://e.org/a', 'comparable': True}, {'url': 'https://e.org/b', 'comparable': False, 'reason': 'two runs disagree', 'detail': 'unstable'} | b]}
        self.assertEqual(check.check_comparable(os.path.join(self.dir, 'none.json'), misses)[0], check.PENDING)
        rb.write_json(path, account()); self.assertEqual(check.check_comparable(path, misses)[0], check.OK)
        rb.write_json(path, account(reason='it looked odd')); self.assertEqual(check.check_comparable(path, misses)[0], check.FAIL)
        rb.write_json(path, account(detail='')); self.assertEqual(check.check_comparable(path, misses)[0], check.FAIL)
        rb.write_json(path, account(comparable=True)); self.assertEqual(check.check_comparable(path, misses)[0], check.FAIL)      # measure.py says it is not
        rb.write_json(path, account() | {'comparable': 2}); self.assertEqual(check.check_comparable(path, misses)[0], check.FAIL)
        rb.write_json(path, {'comparable': 1, 'total': 1, 'pages': account()['pages'][:1]}); self.assertEqual(check.check_comparable(path, misses)[0], check.FAIL)      # a page missing

    def test_the_consent_report_is_of_the_manifests_pages_and_outcomes_and_says_where_a_surface_was(self):
        manifest = os.path.join(self.dir, 'archive-manifest.json'); rb.write_json(manifest, {'pages': [{'url': 'https://e.org/a', 'consent': 'given'}, {'url': 'https://e.org/b', 'consent': 'not-matched'}]})
        path = os.path.join(self.dir, 'consent-report.json'); side = lambda surface=False: {'surface': surface, 'lines': ['Cookies, dialog'] if surface else []}
        report = lambda **b: {'outcomes': {'given': 1, 'not-matched': 1}, 'pages': [{'url': 'https://e.org/a', 'outcome': 'given', 'fleet': side(), 'emulator': side()}, {'url': 'https://e.org/b', 'outcome': 'not-matched', 'fleet': side(True), 'emulator': side()}]} | b
        self.assertEqual(check.check_consent(os.path.join(self.dir, 'none.json'), manifest)[0], check.PENDING)
        rb.write_json(path, report()); state, msg = check.check_consent(path, manifest); self.assertEqual(state, check.OK); self.assertIn('1 begin in or contain a cookie or consent surface', msg)
        rb.write_json(path, report(outcomes={'given': 2})); self.assertEqual(check.check_consent(path, manifest)[0], check.FAIL)
        rb.write_json(path, report(pages=report()['pages'][:1])); self.assertEqual(check.check_consent(path, manifest)[0], check.FAIL)
        wrong = report(); wrong['pages'][0]['outcome'] = 'no-dialog'; rb.write_json(path, wrong); self.assertEqual(check.check_consent(path, manifest)[0], check.FAIL)
        wrong = report(); wrong['pages'][1]['fleet'] = {'surface': True, 'lines': []}; rb.write_json(path, wrong); self.assertEqual(check.check_consent(path, manifest)[0], check.FAIL)      # a surface and no line to show it
        wrong = report(); wrong['pages'][1]['emulator'] = None; rb.write_json(path, wrong); self.assertEqual(check.check_consent(path, manifest)[0], check.FAIL)      # a side not read
        unread = report(); unread['pages'][1]['emulator'] = {'surface': False, 'lines': [], 'unread': 'timed out'}; rb.write_json(path, unread); self.assertEqual(check.check_consent(path, manifest)[0], check.OK)      # a side that had nothing to read says so

    def test_the_manifest_of_a_gate_run_has_each_pages_consent_outcome(self):
        a = 'https://example.org/a'; path = os.path.join(self.dir, 'archive-manifest.json'); corpus = os.path.join(self.dir, 'corpus.json'); rb.write_json(corpus, [{'url': a}])
        page = {'url': a, 'archive': 'a.flows', 'sha256': 'a' * 64, 'mainStatus': 200}
        rb.write_json(path, {'pages': [page | {'consent': 'given'}]}); self.assertEqual(check.check_manifest(path, corpus, require_consent=True)[0], check.OK)
        rb.write_json(path, {'pages': [page]}); self.assertEqual(check.check_manifest(path, corpus, require_consent=True)[0], check.FAIL); self.assertEqual(check.check_manifest(path, corpus)[0], check.OK)      # the earlier run's manifest has none
        rb.write_json(path, {'pages': [page | {'consent': 'declined'}]}); self.assertEqual(check.check_manifest(path, corpus, require_consent=True)[0], check.FAIL)

    def test_the_earlier_figure_is_labelled_not_held_out_and_the_dev_half_dev_half_on_the_page(self):
        page = os.path.join(self.dir, 'page.md'); write(os.path.join(self.dir, 'measure-old60-freeze.txt'), 'GATE: 4488 of 4491 = 99.93%\n'); write(os.path.join(self.dir, 'measure-dev-freeze.txt'), 'GATE: 3000 of 3100 = 96.77%\n')
        write(page, '| the earlier 60 pages at this freeze (not held out) | 4,488 of 4,491 | \n| the other pages of batch 2 | 3,000 of 3,100 |\n'); self.assertEqual(check.check_labels(self.dir, page)[0], check.FAIL)
        write(page, '| the earlier 60 pages at this freeze (not held out) | 4,488 of 4,491 | \n| the dev half of batch 2 (dev half) | 3,000 of 3,100 |\n'); self.assertEqual(check.check_labels(self.dir, page)[0], check.OK)
        write(page, '| the earlier 60 pages at this freeze | 4,488 of 4,491 | \n| the dev half of batch 2 (dev half) | 3,000 of 3,100 |\n'); self.assertEqual(check.check_labels(self.dir, page)[0], check.FAIL)
        write(page, '| the dev half of batch 2 (dev half) | 3,000 of 3,100 |\n'); self.assertEqual(check.check_labels(self.dir, page)[0], check.FAIL)      # a figure not on the page
        self.assertEqual(check.check_labels(os.path.join(self.dir, 'empty'), page)[0], check.PENDING)

if __name__ == '__main__': unittest.main()
