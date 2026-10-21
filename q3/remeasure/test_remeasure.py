"""python3 -m unittest discover -s q3/remeasure -t q3/remeasure   (from the repository root; needs node, as the capture does)"""
import sys, os, json, tempfile, subprocess, unittest, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, Q3)
import readback as rb, check, corpus_capture as cc, policy_override as po

def write(path, text):
    with open(path, 'w') as f: f.write(text)

def record(worker='a11y-worker-2', links=('History probe self, link', 'History probe cookies, link'), status=200, transcript=(), url='http://capture-host:8000/visited-probe.html'):
    return {'capturedAt': '2026-10-21T10:00:00.000Z', 'worker': worker, 'status': status, 'capture': {'url': url, 'transcript': list(transcript), 'structure': {'links': list(links), 'headings': ['History probe, heading, level 1']}}}

def passing_box(visited_after=False):
    return {'policy': {'name': rb.POLICY, 'value': 1, 'readAt': '2026-10-21T09:00:00Z', 'evidence': 'all 11 policy values verified'}, 'emptied': {'at': '2026-10-21T09:05:00Z', 'what': 'History'},
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
    def test_an_after_run_probe_that_reads_visited_fails_the_box(self):
        b = passing_box(); b['after-run'] = rb.probe_outcome(record(links=('a, visited, link', 'b, link'))); self.assertFalse(rb.box_passes(b))


class CorpusCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name
        self.readback = {'workers': {f'a11y-worker-{n}': passing_box() for n in (2, 3, 4)} | {'a11y-worker-5': passing_box(visited_after=True)}}
        self.stub = os.path.join(self.dir, 'stub.mjs')       # stands in for fleet_capture.mjs: writes a record for the address, or fails for one address
        write(self.stub, """import { writeFileSync } from 'node:fs'; const [, , w, url, out] = process.argv; const name = w.split('=')[0];
if (url.endsWith('/broken')) { writeFileSync(out, JSON.stringify({ worker: name, status: 500, capture: { error: 'boom' } })); process.exit(0); }
writeFileSync(out, JSON.stringify({ capturedAt: 'now', worker: name, status: 200, capture: { url, transcript: [], structure: { links: ['a, link'], headings: [] } } }));""")
    def tearDown(self): self.tmp.cleanup()

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
    def test_it_does_not_leak_other_variables_into_the_override(self):
        self.assertEqual(list(po.override(self.DEFAULTS)), ['worker_edge_policy'])
    def test_it_refuses_when_the_policy_is_already_declared(self):
        with self.assertRaises(SystemExit): po.override(self.DEFAULTS + "  - { name: SavingBrowserHistoryDisabled, value: 1 }\n")


class Check(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name
    def tearDown(self): self.tmp.cleanup()
    def write_readback(self, boxes, before=True):
        if before: boxes['a11y-worker-2']['before'] = rb.probe_outcome(record(links=('a, visited, link', 'b, link')))
        path = os.path.join(self.dir, 'history-readback.json'); rb.save(path, {'policy': rb.POLICY, 'workers': boxes}); return path
    def oracle(self, **per_file):
        d = os.path.join(self.dir, 'oracle'); os.makedirs(d, exist_ok=True)
        for name, rec in per_file.items(): rb.write_json(os.path.join(d, name + '.json'), rec)
        return d
    def stamped(self, links=('a, link',), worker='a11y-worker-2'):
        rec = record(worker=worker, links=links); rec['history'] = cc.history_block(passing_box()); return rec

    def test_readback_without_a_positive_control_fails(self):
        self.assertEqual(check.check_readback(self.write_readback({'a11y-worker-2': passing_box()}, before=False))[0], check.FAIL)
    def test_readback_whose_before_probe_saw_no_history_fails(self):
        path = self.write_readback({'a11y-worker-2': passing_box()}, before=False)
        data = rb.load(path); data['workers']['a11y-worker-2']['before'] = rb.probe_outcome(record()); rb.save(path, data)
        self.assertEqual(check.check_readback(path)[0], check.FAIL)
    def test_readback_passes_with_a_control_and_clean_boxes(self):
        self.assertEqual(check.check_readback(self.write_readback({'a11y-worker-2': passing_box(), 'a11y-worker-3': passing_box()}))[0], check.OK)
    def test_one_visited_announcement_in_the_oracle_fails_the_check(self):
        rb_path = self.write_readback({'a11y-worker-2': passing_box()})
        state, msg = check.check_oracle(self.oracle(a=self.stamped(), b=self.stamped(links=('Cookies, visited, link',))), rb_path)
        self.assertEqual(state, check.FAIL); self.assertIn('1 announcements carry `visited`', msg)
    def test_a_record_without_the_history_block_fails_the_check(self):
        rb_path = self.write_readback({'a11y-worker-2': passing_box()})
        self.assertEqual(check.check_oracle(self.oracle(a=record()), rb_path)[0], check.FAIL)
    def test_a_record_from_a_worker_that_did_not_pass_fails_the_check(self):
        rb_path = self.write_readback({'a11y-worker-2': passing_box()})
        self.assertEqual(check.check_oracle(self.oracle(a=self.stamped(worker='a11y-worker-9')), rb_path)[0], check.FAIL)
    def test_a_clean_stamped_oracle_passes(self):
        rb_path = self.write_readback({'a11y-worker-2': passing_box()})
        self.assertEqual(check.check_oracle(self.oracle(a=self.stamped(), b=self.stamped()), rb_path)[0], check.OK)
    def test_an_ipv4_literal_is_found_and_a_version_number_is_not(self):
        f = os.path.join(self.dir, 'r.txt')
        write(f, 'Edge 155.0.4283.101 on a11y-worker-2, build 2026.1.1\n'); self.assertEqual(check.check_addresses([f])[0], check.OK)
        write(f, 'worker at http://192.0.2.12:8765\n'); self.assertEqual(check.check_addresses([f])[0], check.FAIL)
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
        write(doc, base.replace('## Q3\n', '## Re-measure\n\nfigure\n\n## Q3\n')); self.assertEqual(run()[0], check.FAIL)


if __name__ == '__main__': unittest.main()
