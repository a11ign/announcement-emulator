"""python3 -m unittest discover -s q3/replay -t q3/replay   (from the repository root)

The matching, the join, the read-back and the capture hooks need nothing; the tests that start the replay proxy or the emulator's Chrome need the replay virtualenv and the Chrome build `setup.sh` makes under
$EMU_DOWNLOADS (and curl), and are skipped without them."""
import sys, os, io, re, json, shutil, time, contextlib, subprocess, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE); ROOT = os.path.dirname(Q3)
sys.path.insert(0, HERE); sys.path.insert(0, Q3); sys.path.insert(0, os.path.join(Q3, 'remeasure')); sys.path.insert(0, os.path.join(ROOT, 'emu'))
import export_freeze, evidence, explain, oracle_summary, run_replayed, process, archive as ar, join, replay_readback as rrb, capture_hooks, readback as rb, corpus_capture as cc
from archive import Entry

try:
    import proxy as px
    HAVE_PROXY = (px.VENV / 'mitmdump').exists() and shutil.which('curl') is not None
    from paths import DOWNLOADS
    HAVE_CHROME = (DOWNLOADS / 'chrome155' / 'chrome-linux64' / 'chrome').exists() and HAVE_PROXY
except Exception:
    HAVE_PROXY = HAVE_CHROME = False


def read(path):
    with open(path) as f: return f.read()


def write(path, text):
    with open(path, 'w') as f: f.write(text)


def entry(url, status=200, body=b'x', method='GET', request_body=b''): return Entry(method, url, status, [('content-type', 'text/html')], body, ar.body_sha(request_body))


class Matching(unittest.TestCase):
    def test_an_address_is_found_whatever_the_fragment_the_host_case_or_the_default_port(self):
        a = ar.Archive([entry('https://Example.org:443/a?x=1#top')])
        for url in ('https://example.org/a?x=1', 'https://EXAMPLE.org/a?x=1#else', 'https://example.org:443/a?x=1'):
            self.assertEqual(a.find('GET', url)[1], 'exact', url)
        self.assertEqual(a.find('GET', 'http://example.org/a?x=1')[1], 'miss')       # another scheme is another address
        self.assertEqual(a.find('GET', 'https://example.org:8443/a?x=1')[1], 'miss')

    def test_the_method_is_part_of_the_address(self):
        self.assertEqual(ar.Archive([entry('https://e.org/a')]).find('POST', 'https://e.org/a')[1], 'miss')

    def test_a_request_made_again_gets_the_next_recording_and_then_the_last_again(self):
        a = ar.Archive([entry('https://e.org/a', body=b'one'), entry('https://e.org/a', body=b'two')])
        got = [a.find('GET', 'https://e.org/a') for _ in range(3)]
        self.assertEqual([g[0].body for g in got], [b'one', b'two', b'two']); self.assertEqual([g[2] for g in got], [False, False, True])
        a.reset(); self.assertEqual(a.find('GET', 'https://e.org/a')[0].body, b'one')

    def test_a_query_whose_values_differ_is_answered_by_the_recording_with_the_same_names(self):
        a = ar.Archive([entry('https://e.org/t?ts=100&q=a', body=b'a'), entry('https://e.org/t?ts=200&q=b', body=b'b')])
        e, kind, _ = a.find('GET', 'https://e.org/t?ts=999&q=b'); self.assertEqual((e.body, kind), (b'b', 'fuzzy'))      # most values in common
        e, kind, _ = a.find('GET', 'https://e.org/t?ts=999&q=zzz'); self.assertEqual((e.body, kind), (b'a', 'fuzzy'))     # a tie: the earlier recording

    def test_other_query_names_or_another_path_are_a_miss(self):
        a = ar.Archive([entry('https://e.org/t?ts=100')])
        self.assertEqual(a.find('GET', 'https://e.org/t?other=1')[1], 'miss'); self.assertEqual(a.find('GET', 'https://e.org/t')[1], 'miss'); self.assertEqual(a.find('GET', 'https://e.org/u?ts=1')[1], 'miss')

    def test_posts_to_one_address_are_told_apart_by_their_body(self):
        a = ar.Archive([entry('https://e.org/p', body=b'first', method='POST', request_body=b'a=1'), entry('https://e.org/p', body=b'second', method='POST', request_body=b'a=2')])
        self.assertEqual(a.find('POST', 'https://e.org/p', b'a=2')[0].body, b'second'); self.assertEqual(a.find('POST', 'https://e.org/p', b'a=1')[0].body, b'first')


def log(*items): return [{'method': m, 'url': u, 'kind': k, 'reused': False, 'status': 200, 'dest': '', 'mode': ''} for m, u, k in items]


class Join(unittest.TestCase):
    def test_a_request_missed_on_one_side_and_answered_on_the_other_is_a_difference(self):
        j = ar.page_join(log(('GET', 'https://e.org/a', 'exact'), ('GET', 'https://e.org/b', 'miss')), log(('GET', 'https://e.org/a', 'exact'), ('GET', 'https://e.org/b', 'exact')))
        self.assertEqual(j['missedOnFleetAnsweredOnEmulator'], ['GET https://e.org/b']); self.assertEqual(j['missedOnEmulatorAnsweredOnFleet'], [])
        j = ar.page_join(log(('GET', 'https://e.org/b', 'fuzzy')), log(('GET', 'https://e.org/b', 'miss')))
        self.assertEqual(j['missedOnEmulatorAnsweredOnFleet'], ['GET https://e.org/b'])

    def test_a_miss_on_both_sides_or_a_request_only_one_side_made_is_not_a_difference(self):
        j = ar.page_join(log(('GET', 'https://e.org/x', 'miss'), ('GET', 'https://e.org/only-fleet', 'exact')), log(('GET', 'https://e.org/x', 'miss')))
        self.assertEqual((j['missedOnFleetAnsweredOnEmulator'], j['missedOnEmulatorAnsweredOnFleet']), ([], [])); self.assertEqual(j['onlyFleetAnswered'], ['GET https://e.org/only-fleet'])

    def test_counts_are_of_every_request(self):
        self.assertEqual(ar.summarise(log(('GET', 'https://e.org/a', 'exact'), ('GET', 'https://e.org/b', 'fuzzy'), ('GET', 'https://e.org/c', 'miss'), ('GET', 'https://e.org/c', 'miss'))), {'requests': 4, 'exact': 1, 'fuzzy': 1, 'miss': 2})


def served(sha, *items, worker=None):
    return {'archive': 'x.flows', 'sha256': sha, 'requests': log(*items)} | ({'worker': worker} if worker else {})


class JoinFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name
        self.manifest = {'pages': [{'url': 'https://e.org/', 'slug': 'e-org', 'sha256': 'a' * 64}]}
        for d in ('fleet', 'gate', 'head'): os.makedirs(os.path.join(self.dir, d))
    def tearDown(self): self.tmp.cleanup()
    def put(self, where, name, data): write(os.path.join(self.dir, where, name), json.dumps(data))
    def build(self): return join.build(self.manifest, os.path.join(self.dir, 'fleet'), {'gate': os.path.join(self.dir, 'gate'), 'head': os.path.join(self.dir, 'head')})

    def test_a_page_served_alike_on_both_sides_joins_clean_and_a_browsers_own_traffic_is_not_compared(self):
        self.put('fleet', 'e-org.a11y-worker-2.json', served('a' * 64, ('GET', 'https://e.org/', 'exact'), ('POST', 'https://update.googleapis.com/service/update2/json?cup2key=1', 'fuzzy'), worker='a11y-worker-2'))
        for d in ('gate', 'head'):
            for k in (1, 2): self.put(d, f'e-org.run{k}.json', served('a' * 64, ('GET', 'https://e.org/', 'exact'), ('GET', 'http://clients2.google.com/time/1/current?cup2key=9', 'miss')))
        page = self.build()['pages'][0]
        self.assertEqual(page['differences'], []); self.assertEqual(page['fleet']['browserOwn'], 1); self.assertEqual(set(page['emulator']), {'gate.run1', 'gate.run2', 'head.run1', 'head.run2'})

    def test_a_difference_in_one_emulator_run_is_named_with_its_run(self):
        self.put('fleet', 'e-org.a11y-worker-2.json', served('a' * 64, ('GET', 'https://e.org/', 'exact'), ('GET', 'https://e.org/late.js', 'miss')))
        self.put('gate', 'e-org.run1.json', served('a' * 64, ('GET', 'https://e.org/', 'exact'), ('GET', 'https://e.org/late.js', 'exact'))); self.put('gate', 'e-org.run2.json', served('a' * 64, ('GET', 'https://e.org/', 'exact')))
        self.put('head', 'e-org.run1.json', served('a' * 64, ('GET', 'https://e.org/', 'exact')))
        self.assertEqual([(d['run'], d['request']) for d in self.build()['pages'][0]['differences']], [('gate.run1', 'GET https://e.org/late.js')])

    def test_a_page_with_no_fleet_log_or_no_emulator_log_is_reported_missing(self):
        self.assertIn('missing', self.build()['pages'][0])
        self.put('fleet', 'e-org.a11y-worker-2.json', served('a' * 64)); self.assertIn('missing', self.build()['pages'][0])


class ReplayReadback(unittest.TestCase):
    MARKER = 'replay probe plum heron quartz'

    def box(self, **over):
        b = {'proxy': {'server': 'capture-host:3201', 'readAt': '2026-10-21T09:00:00Z'}, 'certificate': {'thumbprint': 'A' * 40, 'readAt': '2026-10-21T09:01:00Z'},
             'on': {'capturedAt': '2026-10-21T09:05:00.000Z', 'read': True}, 'after-run': {'capturedAt': '2026-10-21T11:00:00.000Z', 'read': True}}
        return b | over

    def restored(self, **over):
        return self.box() | {'removed': {'at': '2026-10-21T11:05:00Z'}, 'restored': {'at': '2026-10-21T11:05:00Z'}, 'off': {'capturedAt': '2026-10-21T11:10:00.000Z', 'read': False}, 'status': {'state': 'ready', 'at': '2026-10-21T11:15:00Z'}} | over

    def record(self, headings=(MARKER + ', heading, level 1',), status=200, error=None):
        return {'capturedAt': 'now', 'worker': 'a11y-worker-2', 'status': status, 'capture': {'structure': {'headings': list(headings)}} | ({'error': error} if error else {})}

    def test_a_box_that_read_the_marker_behind_the_server_passes(self): self.assertTrue(rrb.box_passes(self.box()))

    def test_each_reading_is_required(self):
        for gone in ('proxy', 'certificate', 'on'):
            b = self.box(); del b[gone]; self.assertFalse(rrb.box_passes(b), gone)
        self.assertFalse(rrb.box_passes(self.box(on={'capturedAt': '2026-10-21T09:05:00.000Z', 'read': False})))

    def test_the_readings_are_in_the_order_of_the_steps(self):
        self.assertFalse(rrb.box_passes(self.box(on={'capturedAt': '2026-10-21T08:00:00.000Z', 'read': True})))        # the probe predates the proxy
        self.assertFalse(rrb.box_passes(self.box(certificate={'thumbprint': 'A' * 40, 'readAt': '2026-10-21T08:30:00Z'})))

    def test_a_probe_reads_the_marker_only_as_the_pages_heading_of_a_good_capture(self):
        self.assertTrue(rrb.read_marker(self.record(), self.MARKER)['read'])
        for bad in (self.record(headings=('Some other page, heading, level 1',)), self.record(status=500), self.record(error='net::ERR_NAME_NOT_RESOLVED')): self.assertFalse(rrb.read_marker(bad, self.MARKER)['read'])
        self.assertFalse(rrb.read_marker(self.record(headings=('replay probe plum heron quartzite, heading',)), self.MARKER)['read'])      # a longer word is not the marker
        self.assertTrue(rrb.read_marker(self.record(headings=('Replay probe: plum-heron quartz, heading, level 1',)), self.MARKER)['read'])      # as it is said, not as it is written

    def test_before_and_during_the_run_the_marker_must_be_read_and_after_the_restore_it_must_not(self):
        self.assertTrue(rrb.stage_passes('on', {'read': True})); self.assertFalse(rrb.stage_passes('on', {'read': False})); self.assertTrue(rrb.stage_passes('off', {'read': False})); self.assertFalse(rrb.stage_passes('off', {'read': True}))
        self.assertFalse(rrb.stage_passes('off', None))

    def test_holding_needs_the_later_probe_before_any_restore(self):
        self.assertTrue(rrb.box_held(self.box()))
        self.assertFalse(rrb.box_held(self.box(**{'after-run': {'capturedAt': '2026-10-21T09:04:00.000Z', 'read': True}})))
        self.assertFalse(rrb.box_held(self.box(**{'after-run': {'capturedAt': '2026-10-21T11:00:00.000Z', 'read': False}})))
        self.assertFalse(rrb.box_held(self.box(restored={'at': '2026-10-21T10:00:00Z'})))        # put back before the later probe
        self.assertTrue(rrb.box_held(self.box(restored={'at': '2026-10-21T12:00:00Z'})))

    def test_a_restored_box_shows_the_values_gone_the_probe_off_and_the_box_ready_in_that_order(self):
        self.assertTrue(rrb.box_restored(self.restored())); self.assertFalse(rrb.box_passes(self.restored()))
        for gone in ('removed', 'off', 'status'):
            b = self.restored(); del b[gone]; self.assertFalse(rrb.box_restored(b), gone)
        self.assertFalse(rrb.box_restored(self.restored(off={'capturedAt': '2026-10-21T11:10:00.000Z', 'read': True})))      # the probe still reaches the archive
        self.assertFalse(rrb.box_restored(self.restored(status={'state': 'busy', 'at': '2026-10-21T11:15:00Z'})))
        self.assertFalse(rrb.box_restored(self.restored(off={'capturedAt': '2026-10-21T11:02:00.000Z', 'read': False})))      # read before the values were removed


def stub_capture(dir_):
    path = os.path.join(dir_, 'stub.mjs')
    write(path, """import { writeFileSync } from 'node:fs'; const [, , w, url, out] = process.argv;
writeFileSync(out, JSON.stringify({ capturedAt: 'now', worker: w.split('=')[0], status: 200, capture: { url, transcript: [], structure: { links: ['a, link'], headings: [] } } }));""")
    return path


class FleetHooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name; self.calls = []
        os.makedirs(os.path.join(self.dir, 'archives')); self.slug = cc.slug_of('https://e.org/'); open(os.path.join(self.dir, 'archives', self.slug + '.flows'), 'w').close()
        box = {'proxy': {'readAt': 'p'}, 'certificate': {'readAt': 'c'}, 'on': {'capturedAt': 'o'}}
        self.readback = {'runId': 'run1', 'workers': {'a11y-worker-2': box}}
        def fake(port, path):
            self.calls.append((port, path))
            return {'archive': 'x', 'sha256': 'b' * 64, 'entries': 3} if path.startswith('/use') else {'archive': 'x', 'sha256': 'b' * 64, 'requests': log(('GET', 'https://e.org/', 'exact'), ('GET', 'https://e.org/x.js', 'miss'), ('GET', 'https://e.org/y.js', 'miss'))}
        self.hooks = capture_hooks.FleetReplay(self.dir, {'a11y-worker-2': 3201}, self.readback, control_fn=fake)
    def tearDown(self): self.tmp.cleanup()

    def test_the_page_is_loaded_into_the_boxes_own_server_and_its_log_is_kept_and_counted(self):
        used = self.hooks.before('a11y-worker-2', self.slug); block = self.hooks.after('a11y-worker-2', self.slug, used)
        self.assertEqual(self.calls[0], (3201, f'/use?archive={self.slug}.flows')); self.assertEqual(self.calls[1], (3201, '/log'))
        self.assertEqual((block['archiveSha256'], block['requests'], block['unmatched']), ('b' * 64, 3, 2))
        self.assertEqual(json.loads(read(os.path.join(self.dir, 'fleet-logs', f'{self.slug}.a11y-worker-2.json')))['worker'], 'a11y-worker-2')

    def test_a_page_with_no_archive_is_not_captured(self):
        with self.assertRaises(RuntimeError): self.hooks.before('a11y-worker-2', 'no-such-page')

    def test_a_server_that_changed_archive_during_the_capture_is_refused(self):
        with self.assertRaises(RuntimeError): self.hooks.after('a11y-worker-2', self.slug, {'sha256': 'c' * 64})

    def test_the_capture_stamps_the_record_with_the_replay_block(self):
        stub = stub_capture(self.dir); dest = os.path.join(self.dir, 'oracle', self.slug + '.json'); os.makedirs(os.path.dirname(dest))
        ok, why = cc.capture_one({'url': 'https://e.org/', 'role': None}, 'a11y-worker-2', 'http://w', ReplayBox.history(), dest, stub, self.hooks); self.assertTrue(ok, why)
        rec = json.loads(read(dest)); self.assertEqual(rec['replay']['unmatched'], 2); self.assertEqual(rec['replay']['runId'], 'run1'); self.assertEqual(rec['capture']['url'], 'https://e.org/')

    def test_the_log_of_a_failed_capture_is_dropped_so_a_page_keeps_only_the_log_of_the_capture_that_was_kept(self):
        broken = os.path.join(self.dir, 'broken.mjs'); write(broken, "import { writeFileSync } from 'node:fs'; const [, , w, url, out] = process.argv; writeFileSync(out, JSON.stringify({ worker: 'a11y-worker-2', status: 500, capture: { error: 'HTTP 503' } }));")
        dest = os.path.join(self.dir, 'oracle', self.slug + '.json'); os.makedirs(os.path.dirname(dest))
        ok, why = cc.capture_one({'url': 'https://e.org/', 'role': None}, 'a11y-worker-2', 'http://w', ReplayBox.history(), dest, broken, self.hooks); self.assertFalse(ok)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fleet-logs', f'{self.slug}.a11y-worker-2.json'))); self.assertFalse(os.path.exists(dest))

    def test_a_record_on_disk_is_kept_only_if_it_is_this_runs_from_the_archive_now_on_disk_by_a_box_that_passes(self):
        """What a resumed run keeps: a record of another run, of another archive, or by a box that no longer passes is captured again."""
        self.readback['workers']['a11y-worker-2'] = ReplayBox.box()
        history = {'workers': {'a11y-worker-2': ReplayBox.history()}}; dest = os.path.join(self.dir, self.slug + '.json')
        archive_sha = self.hooks.archive_sha256(self.slug)
        record = lambda **block: {'history': {'x': 1}, 'worker': 'a11y-worker-2', 'replay': {'runId': 'run1', 'archiveSha256': archive_sha, **block}}
        write(dest, json.dumps(record())); self.assertTrue(cc.already_captured(dest, history, self.hooks))
        for stale in (record(runId='an-earlier-run'), record(archiveSha256='0' * 64), {**record(), 'worker': 'a11y-worker-9'}, {k: v for k, v in record().items() if k != 'replay'}):
            write(dest, json.dumps(stale)); self.assertFalse(cc.already_captured(dest, history, self.hooks), stale)
        write(dest, json.dumps(record())); self.assertTrue(cc.already_captured(dest, history, None))      # without a replay the base rule: stamped, and its worker passes

    def test_a_worker_must_pass_both_read_backs(self):
        history = {'workers': {f'a11y-worker-{n}': passing for n in (2, 3, 4) for passing in [ReplayBox.history()]}}
        replay = {'workers': {f'a11y-worker-{n}': ReplayBox.box() for n in (2, 3, 4)}}
        replay['workers']['a11y-worker-4'].pop('on')
        with self.assertRaises(SystemExit): cc.usable_workers({f'a11y-worker-{n}': 'http://w' for n in (2, 3, 4)}, history, replay)      # only two pass both: fewer than three
        replay['workers']['a11y-worker-4'] = ReplayBox.box(); self.assertEqual(sorted(cc.usable_workers({f'a11y-worker-{n}': 'http://w' for n in (2, 3, 4)}, history, replay)), ['a11y-worker-2', 'a11y-worker-3', 'a11y-worker-4'])

    def test_the_live_capture_imports_nothing_of_the_replay_until_one_is_asked_for(self):
        done = subprocess.run([sys.executable, '-c', "import sys; sys.path.insert(0, %r); import corpus_capture; print('replay_readback' in sys.modules, 'capture_hooks' in sys.modules)" % Q3], capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), 'False False', done.stderr)

    def test_the_replay_flags_go_together_and_not_with_static_copies(self):
        base = ['corpus.json', 'out', '--workers', 'a11y-worker-2=http://w', '--readback', 'rb.json']
        for extra in (['--replay-run', 'r'], ['--replay-run', 'r', '--replay-ports', 'a=1'], ['--replay-ports', 'a=1'], ['--replay-readback', 'x.json']):
            with self.assertRaises(SystemExit) as e: cc.main(base + extra)
            self.assertIn('go together', str(e.exception), extra)
        with self.assertRaises(SystemExit) as e: cc.main(base + ['--replay-run', 'r', '--replay-ports', 'a=1', '--replay-readback', 'x.json', '--static-base', 'http://h'])
        self.assertIn('--static-base', str(e.exception))

    def test_a_worker_refused_for_its_replay_read_back_is_told_so(self):
        history = {'workers': {f'a11y-worker-{n}': ReplayBox.history() for n in (2, 3, 4)}}; replay = {'workers': {f'a11y-worker-{n}': ReplayBox.box() for n in (2, 3, 4)}}; replay['workers']['a11y-worker-4'].pop('on')
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit): cc.usable_workers({f'a11y-worker-{n}': 'http://w' for n in (2, 3, 4)}, history, replay)
        self.assertIn('history and replay', err.getvalue()); self.assertIn('a11y-worker-4', err.getvalue())


class ReplayBox:
    @staticmethod
    def box():
        return {'proxy': {'server': 'capture-host:3201', 'readAt': '2026-10-21T09:00:00Z'}, 'certificate': {'thumbprint': 'A' * 40, 'readAt': '2026-10-21T09:01:00Z'}, 'on': {'capturedAt': '2026-10-21T09:05:00.000Z', 'read': True}}

    @staticmethod
    def history():
        links = ('a, link', 'b, link')
        mk = lambda stamp: rb.probe_outcome({'capturedAt': stamp, 'worker': 'w', 'status': 200, 'capture': {'url': 'http://capture-host:8000/visited-probe.html', 'transcript': [], 'structure': {'links': list(links)}}})
        return {'policy': {'name': rb.POLICY, 'value': 1, 'readAt': '2026-10-21T08:00:00Z'}, 'emptied': {'at': '2026-10-21T08:05:00Z'}, 'after': mk('2026-10-21T08:10:00.000Z')}


class Evidence(unittest.TestCase):
    def test_two_lists_agree_differ_in_order_or_differ_in_entries(self):
        a = ['x, check box', 'y, check box', 'z, check box']
        self.assertEqual(evidence.classify_order(a, list(a)), 'agree')
        self.assertEqual(evidence.classify_order(a, [a[1], a[0], a[2]]), 'sameSetOtherOrder')
        self.assertEqual(evidence.classify_order(a, a + ['w, check box']), 'differentEntries')
        self.assertEqual(evidence.classify_order(a + a[:1], a + a[1:2]), 'differentEntries')      # the same entries, but one twice here and another twice there

    def test_the_entries_only_one_side_has_are_counted_not_just_named(self):
        self.assertEqual(evidence.only_in(['a', 'a', 'b'], ['a', 'b']), ['a']); self.assertEqual(evidence.only_in(['a', 'b'], ['a', 'a', 'b']), [])

    def test_the_frame_headers_are_the_entries_that_open_an_example_frame(self):
        self.assertEqual(evidence.frame_headers(['Example, frame, Small, grouping', 'Small, check box', 'Other, frame, x']), [0, 2])

    def test_a_pages_evidence_names_each_side_each_run_and_where_the_sweep_started(self):
        fleet = {'worker': 'a11y-worker-2', 'capturedAt': 't', 'capture': {'structure': {'formFields': ['a', 'b']}, 'observed': {'formFields': {'complete': True}}}}
        run = {'structure': {'formFields': ['b', 'a']}, 'readThrough': {'count': 5, 'stopReason': 'wrap'}, 'sweeps': [{'type': 'formField', 'found': 2, 'prevCount': 1}]}
        page = evidence.build('https://e.org/', fleet, {'head.run1': run}, 'formFields')
        self.assertEqual(page['emulator']['head.run1']['order'], 'sameSetOtherOrder'); self.assertEqual(page['emulator']['head.run1']['start']['sweep']['prevCount'], 1)
        self.assertEqual(page['fleetObserved'], {'complete': True}); self.assertEqual(page['emulator']['head.run1']['start']['readThrough']['stopReason'], 'wrap')

    def test_the_fleets_own_diagnostics_say_where_its_read_through_ended_and_whether_focus_moved_on_load(self):
        events = [{'event': 'readThrough', 'count': 107, 'stopReason': 'wrap', 'atMs': 50595}, {'event': 'pageState', 'beforeProbe': 'sweep:formField', 'focusFrame': None},
                  {'event': 'focusEventLog', 'events': [{'type': 'focusin', 'name': 'A', 'atMs': 66387, 'id': 0}]}]
        start = evidence.fleet_start({'diagnostics': events}, 'formFields')
        self.assertEqual(start['readThrough'], {'count': 107, 'stopReason': 'wrap', 'atMs': 50595}); self.assertIsNone(start['focusFrameBeforeSweep']); self.assertFalse(start['focusBeforeReadThroughEnded'])
        events[2]['events'][0]['atMs'] = 900      # focus moved before the read-through ended: a page that took focus on load
        self.assertTrue(evidence.fleet_start({'diagnostics': events}, 'formFields')['focusBeforeReadThroughEnded'])
        self.assertEqual(evidence.fleet_start({}, 'links')['readThrough'], None)

    def test_one_entry_is_shown_with_the_earlier_readings_rows_and_what_each_side_holds_now(self):
        before = {'misses': [{'url': 'https://e.org/', 'channel': 'links', 'expected': 'English, Zulu, link', 'predicted': None, 'class': 'unexplained'}, {'url': 'https://e.org/', 'channel': 'links', 'expected': 'Other, link', 'predicted': 'x', 'class': 'language'}]}
        fleet = {'capture': {'structure': {'links': []}, 'transcript': ['button, Cookie settings']}}; run = {'structure': {'links': ['Zulu, zu (not supported), link', 'Dutch, link']}}
        e = evidence.entry_evidence('https://e.org/', before, fleet, {'head.run1': run}, 'links', 'Zulu')
        self.assertEqual([r['expected'] for r in e['earlierReading']], ['English, Zulu, link']); self.assertEqual(e['fleetOnTheReplay']['entries'], 0)
        self.assertEqual(e['emulatorOnTheReplay']['head.run1']['withNeedle'], ['Zulu, zu (not supported), link'])


class Explain(unittest.TestCase):
    ATTRIBUTED = [{'url': 'https://e.org/a/', 'channel': 'formFields', 'expected': 'Irish, check box', 'predicted': '', 'class': 'unexplained', 'shape': ['NAME', 'ROLE']},
                  {'url': 'https://e.org/b/', 'channel': 'links', 'expected': 'English, Zulu, link', 'predicted': None, 'class': 'unexplained', 'shape': ['NAME', 'ROLE']},
                  {'url': 'https://e.org/c/', 'channel': 'links', 'expected': 'Welsh, link', 'predicted': 'cy, link', 'class': 'language', 'shape': ['NAME', 'ROLE']},
                  {'url': 'https://e.org/d/', 'channel': 'links', 'expected': 'rare, shape', 'predicted': None, 'class': 'unexplained', 'shape': ['RARE']}]

    def reading(self, pages, misses=()):
        return {'top': ['NAME + ROLE'], 'pages': [{'url': u, 'status': st} for u, st in pages.items()], 'misses': list(misses)}

    def test_the_eleven_are_the_unexplained_misses_of_the_gates_shapes_only(self):
        self.assertEqual([m['url'] for m in explain.eleven(self.ATTRIBUTED, ['NAME + ROLE'])], ['https://e.org/a/', 'https://e.org/b/'])

    def test_a_miss_the_replay_does_not_repeat_on_a_comparable_page_is_the_methods(self):
        freeze = self.reading({'https://e.org/a/': 'comparable', 'https://e.org/b/': 'comparable'}); head = self.reading({'https://e.org/a/': 'comparable', 'https://e.org/b/': 'comparable'})
        got = explain.build(self.ATTRIBUTED, ['NAME + ROLE'], freeze, head, evidence_for=lambda url: ['evidence/x.json'])
        self.assertEqual([m['class'] for m in got['misses']], ['method', 'method']); self.assertEqual(got['misses'][0]['evidence'], [explain.EARLIER_ORDER_EVIDENCE, 'evidence/x.json'])

    def test_a_miss_the_replay_repeats_or_a_page_it_can_no_longer_compare_is_not_the_methods(self):
        repeated = {'url': 'https://e.org/a/', 'channel': 'formFields', 'expected': 'Irish, check box'}
        freeze = self.reading({'https://e.org/a/': 'comparable', 'https://e.org/b/': 'not comparable: headings'}, [repeated]); head = self.reading({'https://e.org/a/': 'comparable', 'https://e.org/b/': 'comparable'})
        got = explain.build(self.ATTRIBUTED, ['NAME + ROLE'], freeze, head)
        self.assertEqual([m['class'] for m in got['misses']], ['unexplained', 'unexplained']); self.assertIn('tried', got['misses'][0])
        self.assertEqual((got['misses'][0]['atFreeze']['missed'], got['misses'][1]['atFreeze']['comparable']), (True, False))

    def test_a_hand_made_class_with_its_evidence_stands_for_a_miss_the_replay_cannot_answer(self):
        freeze = self.reading({'https://e.org/a/': 'comparable', 'https://e.org/b/': 'not comparable: headings'}); head = self.reading({'https://e.org/a/': 'comparable', 'https://e.org/b/': 'not comparable: headings'})
        manual = {'English, Zulu, link': {'class': 'Windows-only', 'evidence': ['evidence/zulu.json'], 'why': 'the names differ'}}
        got = explain.build(self.ATTRIBUTED, ['NAME + ROLE'], freeze, head, manual)['misses'][1]
        self.assertEqual((got['class'], got['evidence'], got['why']), ('Windows-only', ['evidence/zulu.json'], 'the names differ'))


class OracleSummary(unittest.TestCase):
    def test_an_entry_keeps_what_is_committed_of_a_record_and_leaves_its_transcript_out(self):
        record = {'worker': 'a11y-worker-2', 'status': 200, 'capturedAt': 't', 'role': None, 'history': {'policy': {'value': 1}}, 'replay': {'archiveSha256': 'a' * 64, 'unmatched': 2},
                  'capture': {'url': 'https://e.org/', 'transcript': ['one', 'two'], 'structure': {'links': ['a, link'], 'headings': []}, 'environment': {'browserVersion': '155', 'other': 'x'},
                              'diagnostics': [{'event': 'documentReady', 'title': 'E'}]}}
        e = oracle_summary.entry(record)
        self.assertEqual((e['transcriptLines'], e['swept'], e['documentReadyTitle'], e['environment']['browserVersion']), (2, {'headings': 0, 'links': 1}, 'E', '155'))
        self.assertEqual(e['replay'], record['replay']); self.assertNotIn('"one"', json.dumps(e)); self.assertNotIn('other', e['environment'])


class RunReplayed(unittest.TestCase):
    def test_a_command_that_runs_past_its_time_is_killed_with_everything_it_started(self):
        with tempfile.TemporaryDirectory() as d:
            pid_file, child, parent = (os.path.join(d, n) for n in ('grandchild.pid', 'child.py', 'parent.py'))
            write(child, f"import os, time\nwith open({pid_file!r}, 'w') as f: f.write(str(os.getpid()))\ntime.sleep(60)\n")
            write(parent, f"import subprocess, sys, time\nsubprocess.Popen([sys.executable, {child!r}])\ntime.sleep(60)\n")
            with self.assertRaises(subprocess.TimeoutExpired): process.run_in_group([sys.executable, parent], 2)
            pid = int(read(pid_file)); time.sleep(0.5)
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)      # the grandchild is gone, and with it whatever port it held

    def test_a_command_that_ends_in_time_returns_its_status(self):
        self.assertEqual(process.run_in_group([sys.executable, '-c', 'import sys; sys.exit(3)'], 20), 3)

    def test_the_command_for_a_page_is_the_proxy_wrapper_around_the_emulator_of_the_chosen_checkout(self):
        c = run_replayed.command_for('/run', 'slug', '/freeze', 'https://e.org/', '/out.part', 9100, '/log.json', 900, python='/py')
        self.assertEqual(c[c.index('--archive') + 1], 'slug.flows'); self.assertEqual(c[c.index('--timeout') + 1], '900'); self.assertEqual(c[c.index('--') + 1:], ['/py', '/freeze/q3/emulate.py', 'https://e.org/', '/out.part', '--port', '9100'])


class ExportFreeze(unittest.TestCase):
    def test_the_frozen_launch_gets_the_one_change_this_branchs_session_has_and_nothing_else(self):
        current = read(os.path.join(ROOT, 'emu', 'session.mjs'))
        before = current.replace(export_freeze.REPLAY, '').replace(' ...REPLAY,\n', '\n')
        self.assertNotEqual(before, current); self.assertNotIn('REPLAY', before)
        self.assertEqual(export_freeze.patched(before), current)

    def test_a_session_without_the_launch_line_is_refused(self):
        with self.assertRaises(SystemExit): export_freeze.patched('const x = 1;\n')

    def test_the_launch_without_the_variable_is_the_commits_own(self):
        """`REPLAY` is an empty list unless EMU_PROXY is set, so the spawn's argument list is the one it was."""
        self.assertIn("process.env.EMU_PROXY ? [", export_freeze.REPLAY); self.assertTrue(export_freeze.REPLAY.rstrip().endswith(': [];'))


@unittest.skipUnless(shutil.which('node'), 'needs node')
class SessionLaunch(unittest.TestCase):
    def test_a_proxy_without_the_hash_of_its_authority_is_refused_before_a_browser_is_started(self):
        env = {**os.environ, 'EMU_PROXY': '127.0.0.1:1', 'EMU_PORT': '9740', 'EMU_CDP': '9741'}; env.pop('EMU_PROXY_SPKI', None)
        done = subprocess.run(['node', os.path.join(ROOT, 'emu', 'session.mjs'), 'url:https://replay-probe.test/', os.path.join(ROOT, 'emu', 'ext2'), '/nonexistent/chrome'], env=env, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0); self.assertIn('EMU_PROXY needs EMU_PROXY_SPKI', done.stderr)


@unittest.skipUnless(HAVE_PROXY, 'needs the replay virtualenv (setup.sh) and curl')
class ReplayServer(unittest.TestCase):
    """The proxy itself: a recorded archive, a client that trusts the run's CA, and what comes back."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.dir = cls.tmp.name; cls.archives = os.path.join(cls.dir, 'archives'); os.makedirs(cls.archives)
        cls.ca = os.path.join(cls.dir, 'ca'); py = str(px.VENV / 'python')
        subprocess.run([py, os.path.join(HERE, 'ca.py'), 'init', cls.ca], check=True, capture_output=True)
        subprocess.run([py, os.path.join(HERE, 'make_probe.py'), cls.archives, 'replay-probe-unit'], check=True, capture_output=True)
        cls.proxy = px.start_replay(cls.ca, cls.archives, archive='probe.flows'); cls.proxy.wait_ready()
    @classmethod
    def tearDownClass(cls): cls.proxy.stop(); cls.tmp.cleanup()

    def fetch(self, url):
        headers, content = os.path.join(self.dir, 'headers.txt'), os.path.join(self.dir, 'content.txt')
        done = subprocess.run(['curl', '-sS', '-D', headers, '-o', content, '-x', f'http://127.0.0.1:{self.proxy.port}', '--cacert', os.path.join(self.ca, 'mitmproxy-ca-cert.pem'), url], capture_output=True, text=True)
        if done.returncode: self.fail(f'curl: exit {done.returncode}, {done.stderr!r}')
        return [b for b in re.split(r'\r?\n\r?\n', read(headers).lower()) if b.strip()][-1], read(content)      # the last block: the proxy's own `200 Connection established` comes first

    def test_a_recorded_address_is_answered_from_the_archive_with_the_browsers_cache_told_not_to_keep_it(self):
        self.proxy.control('/use?archive=probe.flows'); head, body = self.fetch('https://replay-probe.test/')
        self.assertIn('replay-probe-unit', body); self.assertIn('x-replay: exact', head); self.assertIn('cache-control: no-store', head)

    def test_an_address_that_was_not_recorded_is_a_404_and_is_logged_as_a_miss_and_nothing_goes_out(self):
        self.proxy.control('/use?archive=probe.flows'); head, _ = self.fetch('https://example.com/never-recorded')
        self.assertIn('404', head.splitlines()[0]); log = self.proxy.control('/log')['requests']
        self.assertEqual([(r['kind'], r['url']) for r in log], [('miss', 'https://example.com/never-recorded')])        # no `blocked` entry: no connection to a real server was even tried

    def test_the_log_names_the_archive_by_its_sha256_and_use_clears_it(self):
        used = self.proxy.control('/use?archive=probe.flows'); self.fetch('https://replay-probe.test/')
        served = self.proxy.control('/log'); self.assertEqual(served['sha256'], used['sha256']); self.assertEqual(len(served['requests']), 1)
        self.proxy.control('/use?archive=probe.flows'); self.assertEqual(self.proxy.control('/log')['requests'], [])

    def test_an_archive_outside_the_archive_directory_is_refused(self):
        with self.assertRaises(RuntimeError): self.proxy.control('/use?archive=../ca/mitmproxy-ca.pem')

    def test_a_page_recorded_with_an_error_status_is_served_as_200_with_its_body_and_the_log_says_what_was_recorded(self):
        py = str(px.VENV / 'python'); archives = os.path.join(self.dir, 'archives')
        subprocess.run([py, '-c', "import sys; sys.path.insert(0, %r); import make_probe; make_probe.write(%r, 'replay probe down', name='down.flows', status=503)" % (HERE, archives)], check=True, capture_output=True)
        self.proxy.control('/use?archive=down.flows'); head, body = self.fetch('https://replay-probe.test/')
        self.assertIn('503', head.splitlines()[0])      # no sidecar: as recorded
        write(os.path.join(archives, 'down.flows.served.json'), json.dumps({'address': 'https://replay-probe.test/', 'recordedStatus': 503, 'servedStatus': 200}))
        self.proxy.control('/use?archive=down.flows'); head, body = self.fetch('https://replay-probe.test/')
        self.assertIn('200', head.splitlines()[0]); self.assertIn('replay probe down', body)
        entry = self.proxy.control('/log')['requests'][0]; self.assertEqual((entry['status'], entry['recordedStatus']), (200, 503))
        write(os.path.join(archives, 'down.flows.served.json'), json.dumps({'address': 'https://replay-probe.test/', 'recordedStatus': 500, 'servedStatus': 200}))
        self.proxy.control('/use?archive=down.flows'); head, _ = self.fetch('https://replay-probe.test/')
        self.assertIn('503', head.splitlines()[0])      # a sidecar for another recorded status leaves the page as it was

    def test_with_replay_gives_the_command_a_proxy_that_answers_and_keeps_the_log(self):
        run = os.path.join(self.dir, 'run'); os.makedirs(run); shutil.copytree(self.ca, os.path.join(run, 'ca')); shutil.copytree(self.archives, os.path.join(run, 'archives'))
        log_path = os.path.join(self.dir, 'served.json'); probe = os.path.join(self.dir, 'cmd.py')
        write(probe, "import os, sys; sys.exit(0 if os.environ.get('EMU_PROXY', '').startswith('127.0.0.1:') and os.environ.get('EMU_PROXY_SPKI') else 3)")
        done = subprocess.run([str(px.VENV / 'python'), os.path.join(HERE, 'with_replay.py'), '--run', run, '--archive', 'probe.flows', '--log', log_path, '--', sys.executable, probe]); self.assertEqual(done.returncode, 0)
        self.assertEqual(json.loads(read(log_path))['archive'], 'probe.flows')
        self.assertEqual(subprocess.run([str(px.VENV / 'python'), os.path.join(HERE, 'with_replay.py'), '--run', run, '--archive', 'none.flows', '--log', log_path, '--', sys.executable, probe]).returncode, 70)      # no such archive: the proxy does not start

    def test_a_command_that_runs_past_its_timeout_is_ended_and_what_the_proxy_served_is_still_kept(self):
        run = os.path.join(self.dir, 'run2'); os.makedirs(run); shutil.copytree(self.ca, os.path.join(run, 'ca')); shutil.copytree(self.archives, os.path.join(run, 'archives'))
        log_path = os.path.join(self.dir, 'timed-out.json'); slow = os.path.join(self.dir, 'slow.py'); write(slow, "import time; time.sleep(60)")
        done = subprocess.run([str(px.VENV / 'python'), os.path.join(HERE, 'with_replay.py'), '--run', run, '--archive', 'probe.flows', '--log', log_path, '--timeout', '3', '--', sys.executable, slow], timeout=60)
        self.assertEqual(done.returncode, process.TIMED_OUT); self.assertEqual(json.loads(read(log_path))['status'], process.TIMED_OUT)


@unittest.skipUnless(HAVE_CHROME, 'needs the emulator\'s Chrome (setup.sh) and the replay virtualenv')
class BrowserThroughReplay(unittest.TestCase):
    @staticmethod
    def closed(session):
        """The session as emu/session.py closes it, and its pipes closed too."""
        session.close(); session.p.stdin.close(); session.p.stdout.close()

    """The emulator's Chrome reads a page that exists only in an archive, and reads nothing of it when EMU_PROXY is not set."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.dir = cls.tmp.name; cls.ca = os.path.join(cls.dir, 'ca'); archives = os.path.join(cls.dir, 'archives'); os.makedirs(archives); py = str(px.VENV / 'python')
        cls.ident = json.loads(subprocess.run([py, os.path.join(HERE, 'ca.py'), 'init', cls.ca], check=True, capture_output=True, text=True).stdout)
        subprocess.run([py, os.path.join(HERE, 'make_probe.py'), archives, 'replay-probe-browser'], check=True, capture_output=True)
        cls.proxy = px.start_replay(cls.ca, archives, archive='probe.flows'); cls.proxy.wait_ready()
    @classmethod
    def tearDownClass(cls): cls.proxy.stop(); cls.tmp.cleanup()

    def test_record_mjs_loads_the_page_through_the_proxy_trusting_the_run_ca_by_its_hash(self):
        done = subprocess.run(['node', os.path.join(HERE, 'record.mjs'), 'https://replay-probe.test/', f'127.0.0.1:{self.proxy.port}', self.ident['spki']], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr); self.assertEqual(json.loads(done.stdout)['title'], 'Replay probe')

    def test_record_mjs_does_not_trust_another_authority(self):
        done = subprocess.run(['node', os.path.join(HERE, 'record.mjs'), 'https://replay-probe.test/', f'127.0.0.1:{self.proxy.port}', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='], capture_output=True, text=True, timeout=120)
        self.assertNotEqual(done.returncode, 0)

    def test_the_emulators_session_reads_the_page_through_the_proxy_and_without_the_variable_does_not(self):
        import session
        os.environ.update({'EMU_PROXY': f'127.0.0.1:{self.proxy.port}', 'EMU_PROXY_SPKI': self.ident['spki']})
        try:
            s = session.Session(url='https://replay-probe.test/', port=9700)
            try: s.navigate('https://replay-probe.test/', settle=500); self.assertEqual(s.eval('document.title'), 'Replay probe')
            finally: self.closed(s)
        finally: os.environ.pop('EMU_PROXY'); os.environ.pop('EMU_PROXY_SPKI')
        s = session.Session(url='https://replay-probe.test/', port=9702)
        try: s.navigate('https://replay-probe.test/', settle=500, timeout=8000); self.assertNotEqual(s.eval('document.title'), 'Replay probe')      # no proxy: the name does not resolve
        finally: self.closed(s)


if __name__ == '__main__': unittest.main()
