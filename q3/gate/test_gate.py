"""python3 -m unittest discover -s q3/gate -t q3/gate   (from the repository root)

The batch-2 snapshot and the run list need nothing but the committed files."""
import contextlib, io, sys, os, json, hashlib, shutil, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, Q3); sys.path.insert(0, os.path.join(Q3, 'remeasure'))
import snapshot_batch2 as sb, consent_report as cr, comparability as cmp, views, probes, attribute_gate as ag, check, fixed_at_head as fh
import corpus_capture as cc, readback as rb
from split import split_of

RESULTS = os.path.join(Q3, 'results'); GATE = os.path.join(RESULTS, 'gate')


def load(path):
    with open(path) as f: return json.load(f)


def write(path, text):
    with open(path, 'w') as f: f.write(text)


LAB_TEXT = '''export const REAL_PAGES = [
  { url: "https://a.example/old", batch: 2, publishedClaim: "conformant" },
];
export const BATCH_2_PAGES = /** @type {BatchTwoPage[]} */ ([
  { url: "https://one.example/a", batch: 2, publishedClaim: "conformant", source: "x", claimExcludes: ["1.1.1"], drawnFrom: "https://one.example/sitemap.xml" },
  { url: "https://two.example/b", batch: 2, publishedClaim: "conformant", source: "y", claimExcludes: [], drawnFrom: "https://two.example/sitemap.xml" },
  { url: "https://three.example/c", publishedClaim: "conformant", source: "z" },
]);
export const OTHER = [
  { url: "https://four.example/d", batch: 2 },
];
'''


class Snapshot(unittest.TestCase):
    def test_only_the_entries_of_the_batch_2_array_that_are_marked_batch_2_are_read(self):
        self.assertEqual(sb.batch_two_entries(LAB_TEXT), [('https://one.example/a', 'https://one.example/sitemap.xml'), ('https://two.example/b', 'https://two.example/sitemap.xml')])

    def test_a_lab_file_without_the_array_is_refused(self):
        with self.assertRaises(SystemExit): sb.batch_two_entries('export const REAL_PAGES = [];\n')

    def test_an_address_in_batch_2_twice_is_refused(self):
        with self.assertRaises(SystemExit): sb.snapshot('c' * 40, LAB_TEXT.replace('https://two.example/b', 'https://one.example/a'))

    def test_the_snapshot_names_the_lab_commit_the_files_sha256_and_each_addresss_split(self):
        s = sb.snapshot('c' * 40, LAB_TEXT)
        self.assertEqual((s['source']['commit'], s['source']['sha256']), ('c' * 40, hashlib.sha256(LAB_TEXT.encode()).hexdigest()))
        self.assertEqual([(p['url'], p['split']) for p in s['pages']], [(u, split_of(u)) for u in ('https://one.example/a', 'https://two.example/b')])


class CommittedBatch2(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.batch2 = load(os.path.join(GATE, 'corpus-batch2.json')); cls.corpus = load(os.path.join(RESULTS, 'corpus.json'))

    def test_there_are_at_least_120_addresses_once_each(self):
        urls = [p['url'] for p in self.batch2['pages']]
        self.assertGreaterEqual(len(urls), 120); self.assertEqual(len(urls), len(set(urls)))

    def test_no_batch_2_address_is_in_the_earlier_corpus(self):
        self.assertEqual({p['url'] for p in self.batch2['pages']} & {e['url'] for e in self.corpus}, set())

    def test_each_addresss_split_is_the_one_the_split_rule_gives(self):
        for p in self.batch2['pages']: self.assertEqual(p['split'], split_of(p['url']), p['url'])
        self.assertEqual({p['split'] for p in self.batch2['pages']}, {'dev', 'held'})      # both halves exist: the Gate uses the held one

    def test_the_snapshot_names_the_lab_commit_and_the_files_sha256(self):
        s = self.batch2['source']
        self.assertRegex(s['commit'], r'^[0-9a-f]{40}$'); self.assertRegex(s['sha256'], r'^[0-9a-f]{64}$'); self.assertEqual(s['repo'], 'a11ign/lab')


class RunList(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.batch2 = load(os.path.join(GATE, 'corpus-batch2.json')); cls.corpus = load(os.path.join(RESULTS, 'corpus.json')); cls.listed = load(os.path.join(GATE, 'corpus-run.json'))

    def test_the_committed_list_is_what_the_two_snapshots_make(self): self.assertEqual(self.listed, sb.run_list(self.batch2, self.corpus))

    def test_it_holds_every_batch_2_address_and_the_60_held_addresses_of_the_earlier_corpus_once_each(self):
        self.assertEqual(len([r for r in self.listed if r['set'] == 'batch2']), len(self.batch2['pages']))
        old = [r for r in self.listed if r['set'] == 'old60']
        self.assertEqual(len(old), 60); self.assertEqual({r['url'] for r in old}, {e['url'] for e in self.corpus if e['split'] == 'held'})
        self.assertEqual(len({r['url'] for r in self.listed}), len(self.listed))

    def test_the_earlier_corpus_files_split_is_the_rules(self):
        for e in self.corpus: self.assertEqual(e['split'], split_of(e['url']), e['url'])


class ConsentReport(unittest.TestCase):
    def test_a_dialog_or_a_banner_about_cookies_is_a_surface_and_a_cookie_settings_button_the_page_keeps_is_not(self):
        for line in ('Cookies on GOV dot WALES, banner landmark', 'We use cookies to collect anonymous data to help us improve your site', 'Cookie compliance banner', 'tab, selected, Consent', 'same page, link, Accept all cookies',
                     'Cookies on MOJ Design System, region, heading, level 2, Cookies on MOJ Design System', 'heading, level 2, Your cookie settings', 'Accept all cookies, button'):
            self.assertTrue(cr.is_surface(line), line)
        for line in ('button, collapsed, Set cookie preferences', 'button, collapsed, Cookie options', 'Cookie preferences, region, Set cookie preferences, button, collapsed', 'Manage Cookies, button', 'button, collapsed, opens dialog, Open search',
                     'Open cookie settings widget, button', 'Cookiecutter, heading', 'Cookies, link', 'Cookie policy, link'):
            self.assertFalse(cr.is_surface(line), line)

    def test_a_capture_begins_in_a_surface_by_the_first_lines_of_the_transcript_and_contains_one_by_any_swept_channel(self):
        r = cr.reading(['Cookies on GOV.UK, dialog', 'x'], {'links': ['a, link']}); self.assertEqual((r['begins'], r['contains'], r['surface']), (['Cookies on GOV.UK, dialog'], [], True))
        r = cr.reading(['a', 'b'], {'formFields': ['Accept all cookies, button'], 'links': ['Cookies, link']}); self.assertEqual((r['begins'], r['contains'], r['surface']), ([], ['Accept all cookies, button'], True))
        self.assertEqual(cr.reading(['1', '2', '3', '4', '5', '6', 'Cookies on x, dialog'], {})['surface'], False)      # past the first lines: not where it begins
        self.assertEqual(cr.reading(['Skip to main content, link'], {'links': ['Cookies, link']})['surface'], False)

    def test_the_lines_are_short_and_few(self):
        got = cr.reading(['cookie dialog ' + 'x' * 300, 'cookie dialog 2', 'cookie dialog 3'], {})
        self.assertEqual(len(got['lines']), 2); self.assertTrue(all(len(l) <= 100 for l in got['lines']))

    def test_a_side_with_no_reading_is_none_and_a_surface_in_either_run_is_the_sides(self):
        self.assertIn('unread', cr.side_of([]))      # a side with nothing to read says so; it is not a side with no surface
        self.assertFalse(cr.side_of([])['surface'])
        self.assertTrue(cr.side_of([{'structure': {'links': ['a, link']}}, {'structure': {'landmarks': ['Cookies on Example, region landmark']}}])['surface'])

    def test_the_report_is_each_manifest_page_with_its_outcome_both_sides_and_whether_they_differ(self):
        with tempfile.TemporaryDirectory() as d:
            oracle, emu = os.path.join(d, 'oracle'), os.path.join(d, 'emu'); os.makedirs(oracle); os.makedirs(emu)
            url, same = 'https://e.org/a', 'https://e.org/c'; slug = cc.slug_of(url)
            rb.write_json(os.path.join(oracle, slug + '.json'), {'capture': {'url': url, 'transcript': ['Cookies on e, dialog'], 'structure': {'formFields': ['Accept all cookies, button']}}})
            for k in (1, 2): rb.write_json(os.path.join(emu, f'{slug}.run{k}.json'), {'structure': {'links': ['Home, link']}})
            rb.write_json(os.path.join(oracle, cc.slug_of(same) + '.json'), {'capture': {'url': same, 'transcript': [], 'structure': {'formFields': ['Accept all cookies, button']}}})
            rb.write_json(os.path.join(emu, cc.slug_of(same) + '.run1.json'), {'structure': {'formFields': ['Accept all cookies, button']}})
            r = cr.report({'pages': [{'url': url, 'consent': 'given', 'consentWhy': 'w', 'consentCookies': 3}, {'url': 'https://e.org/b', 'consent': 'no-dialog'}, {'url': same, 'consent': 'given'}]}, oracle, emu)
        self.assertEqual(r['outcomes'], {'given': 2, 'no-dialog': 1}); a, b, c = r['pages']
        self.assertEqual((a['outcome'], a['cookies'], a['fleet']['surface'], a['emulator']['surface'], a['asymmetric']), ('given', 3, True, False, True)); self.assertEqual(('unread' in b['fleet'], 'unread' in b['emulator'], b['asymmetric']), (True, True, False))
        self.assertEqual((c['fleet']['surface'], c['emulator']['surface'], c['asymmetric']), (True, True, False))      # the dialog is there for both: the same page on both sides


class Comparability(unittest.TestCase):
    def build(self, statuses, consent=None):
        return cmp.build({'pages': [{'url': f'https://e.org/{i}', 'status': s} for i, s in enumerate(statuses)]}, {'pages': [{'url': f'https://e.org/{i}', **c} for i, c in enumerate(consent or [{}] * len(statuses))]})

    def test_each_status_of_measure_py_is_one_reason(self):
        got = self.build(['comparable', 'unstable: the two emulator runs differ', 'not comparable: heading fleet 3 / emulator 4', 'not comparable: heading fleet 3 / emulator 3, document title fleet \'a\' / emulator \'b\'',
                          'not comparable: headings read fleet names 5, 10% of them found in the emulator\'s / a different document', 'emulator fault: timeout 900s', 'emulator fault: ValueError: x', 'second run fault: timeout 900s', 'no emulator run', 'oracle lacks a channel'])
        self.assertEqual([p.get('reason') for p in got['pages']], [None, 'two runs disagree', 'census differs', 'document differs', 'document differs', 'timeout', 'emulator fault', 'timeout', 'emulator fault', 'fleet capture incomplete'])
        self.assertEqual((got['comparable'], got['total']), (1, 10)); self.assertTrue(all(p['detail'] for p in got['pages'] if not p['comparable']))

    def test_a_surface_on_either_side_or_a_dialog_nothing_matched_comes_before_measure_pys_own_reason(self):
        surface = {'outcome': 'given', 'fleet': {'surface': True, 'lines': ['transcript: Cookies, dialog']}, 'emulator': {'surface': False, 'lines': []}}
        got = self.build(['not comparable: heading fleet 3 / emulator 4', 'not comparable: heading fleet 3 / emulator 4', 'not comparable: heading fleet 3 / emulator 4'], [surface, {'outcome': 'not-matched'}, {'outcome': 'given'}])
        self.assertEqual([p['reason'] for p in got['pages']], ['consent surface', 'consent not matched', 'census differs']); self.assertIn('Cookies, dialog', got['pages'][0]['detail'])

    def test_a_title_that_differs_only_in_how_it_was_spoken_is_that_and_not_a_different_document(self):
        got = self.build(["not comparable: document title fleet 'Lintaine Court Q 2 - 2025 to 2026 Estate' / emulator 'Lintaine Court Q2 - 2025 to 2026 Estate '", "not comparable: document title fleet 'smartsurvey dot co dot uk slash s slash ' / emulator 'Interruption pages'",
                          "not comparable: heading fleet 0 / emulator 14, document title fleet 'a' / emulator 'b'"],
                         [{'outcome': 'given', 'fleet': {'surface': True, 'lines': ['tab, selected, Consent']}, 'emulator': {'surface': False, 'lines': []}}, {}, {}])
        self.assertEqual([p['reason'] for p in got['pages']], ['title spoken differently', 'document differs', 'document differs'])      # a title that differs along with a count is a different document
        self.assertIn('Consent', got['pages'][0]['detail'])      # the surface is said, and is not the reason

    def test_a_comparable_page_that_began_in_a_surface_stays_comparable_and_is_counted(self):
        got = self.build(['comparable', 'comparable'], [{'outcome': 'given', 'fleet': {'surface': True, 'lines': ['x']}, 'emulator': None}, {'outcome': 'given'}])
        self.assertEqual((got['comparable'], got['comparableInASurface']), (2, 1)); self.assertEqual(got['pages'][0]['inASurface'], ['x'])
        both = self.build(['comparable'], [{'outcome': 'given', 'fleet': {'surface': True, 'lines': ['x']}, 'emulator': {'surface': True, 'lines': ['x']}, 'asymmetric': False}])
        self.assertEqual((both['comparableInASurface'], both['comparableInASurfaceForOneSideOnly']), (1, 0))      # the dialog is there for both sides: the same page

    def test_the_reasons_are_counted(self):
        self.assertEqual(self.build(['unstable: x', 'unstable: y', 'comparable'])['reasons'], {'two runs disagree': 2})

    def test_every_reason_it_gives_is_one_check_py_accepts(self):
        import check
        for status in ('unstable: x', 'not comparable: heading fleet 1 / emulator 2', 'not comparable: document title a / b', 'emulator fault: timeout 900s', 'emulator fault: y', 'no emulator run', 'oracle lacks a channel'):
            self.assertIn(cmp.reason_of(status, 'given', {'surface': False, 'lines': []})[0], check.NOT_COMPARABLE_REASONS)
        self.assertIn(cmp.reason_of('unstable: x', 'not-matched', {'surface': False, 'lines': []})[0], check.NOT_COMPARABLE_REASONS); self.assertIn(cmp.reason_of('unstable: x', 'given', {'surface': True, 'lines': []})[0], check.NOT_COMPARABLE_REASONS)


class Views(unittest.TestCase):
    def test_the_oracle_is_read_as_two_by_the_run_lists_sets_and_nothing_is_copied(self):
        with tempfile.TemporaryDirectory() as d:
            oracle = os.path.join(d, 'oracle'); os.makedirs(oracle)
            for name, url in (('a', 'https://e.org/a'), ('b', 'https://e.org/b'), ('c', 'https://e.org/c')): rb.write_json(os.path.join(oracle, name + '.json'), {'capture': {'url': url}})
            counts = views.make(oracle, [{'url': 'https://e.org/a', 'set': 'batch2'}, {'url': 'https://e.org/b', 'set': 'old60'}], os.path.join(d, 'views'))
            self.assertEqual(counts, {'batch2': 1, 'old60': 1}); self.assertEqual(sorted(os.listdir(os.path.join(d, 'views', 'batch2'))), ['a.json']); self.assertTrue(os.path.islink(os.path.join(d, 'views', 'old60', 'b.json')))
            self.assertEqual(views.make(oracle, [{'url': 'https://e.org/a', 'set': 'batch2'}], os.path.join(d, 'views')), {'batch2': 1})      # run again: the links are made again, not doubled


class Probes(unittest.TestCase):
    """A probe is one named change to a COPY of the frozen emulator; it refuses a tree that does not have the line it is made at exactly once."""
    def tree(self, d):
        for name, (path, old, new) in probes.VARIANTS.items():
            os.makedirs(os.path.dirname(os.path.join(d, path)), exist_ok=True)
            with open(os.path.join(d, path), 'a') as f: f.write('before\n' + old + 'after\n')

    def test_each_variant_changes_one_line_of_a_copy_and_leaves_the_export_as_it_was(self):
        with tempfile.TemporaryDirectory() as d:
            export = os.path.join(d, 'export'); self.tree(export)
            for name, (path, old, new) in probes.VARIANTS.items():
                diff = probes.make_variant(export, os.path.join(d, name), name)
                with open(os.path.join(d, name, path)) as f: self.assertEqual(f.read().count(new), 1)
                with open(os.path.join(export, path)) as f: self.assertIn(old, f.read())
                self.assertEqual(len([l for l in diff.splitlines() if l.startswith('-') and not l.startswith('---')]), 1); self.assertEqual(len([l for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]), 1)

    def test_a_tree_without_the_line_or_with_it_twice_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            export = os.path.join(d, 'export'); self.tree(export)
            path, old, _ = probes.VARIANTS['linked']
            with open(os.path.join(export, path), 'a') as f: f.write(old)
            with self.assertRaises(SystemExit): probes.make_variant(export, os.path.join(d, 'twice'), 'linked')
            with open(os.path.join(export, path), 'w') as f: f.write('nothing\n')
            with self.assertRaises(SystemExit): probes.make_variant(export, os.path.join(d, 'none'), 'linked')

    def test_the_lines_the_probes_are_made_at_are_in_the_frozen_emulator_exactly_once(self):
        """The emulator has been fixed since the freeze (A11-176), so the lines are read from the frozen commit and not from the working tree."""
        import subprocess
        root = os.path.dirname(Q3); commit = load(os.path.join(GATE, 'freeze.json'))['commit']
        if subprocess.run(['git', '-C', root, 'cat-file', '-e', commit + '^{commit}'], capture_output=True).returncode: self.skipTest('the frozen commit is not in this clone')
        for name, (path, old, new) in probes.VARIANTS.items():
            frozen = subprocess.run(['git', '-C', root, 'show', f'{commit}:{path}'], capture_output=True, text=True, check=True).stdout
            self.assertEqual(frozen.count(old), 1, name)


class SourcesOfTheQuotedLines(unittest.TestCase):
    def test_the_lines_are_read_from_the_checkout_it_is_given_not_from_this_one(self):
        """The emulator has been fixed since the freeze (A11-176): the quoted lines are the frozen ones only when it is pointed at an export of the frozen commit."""
        here, there = ag.Sources('o', 'e', 'p', 'd'), ag.Sources('o', 'e', 'p', 'd', repo='/frozen')
        self.assertEqual((here.standin, there.standin, there.sweep), (os.path.join(os.path.dirname(Q3), 'emu', 'standin.py'), '/frozen/emu/standin.py', '/frozen/q3/sweep.py'))
        usage = io.StringIO()
        with contextlib.redirect_stdout(usage), self.assertRaises(SystemExit): ag.main(['--help'])
        self.assertIn('--repo', usage.getvalue())


class FixedAtHead(unittest.TestCase):
    A, B = 'https://one.example/a', 'https://two.example/b'

    def miss(self, url, channel, expected, predicted=None, **extra): return {'url': url, 'channel': channel, 'expected': expected, 'predicted': predicted, **extra}

    def reading(self, pages, misses): return {'pages': [{'url': u, 'status': s} for u, s in pages.items()], 'misses': misses}

    def test_the_rows_are_the_ten_misses_and_the_access_key_rows_of_the_same_pages_once_each(self):
        attributed = {'misses': [{'page': self.A, 'channel': 'links', 'expected': 'x', 'predicted': 'y', 'evidence': ['evidence/e.json']},
                                 {'page': self.A, 'channel': 'links', 'expected': 'Log in, link, Alt plus, m', 'predicted': None, 'evidence': ['evidence/f.json']}]}
        gate = {'misses': [self.miss(self.A, 'links', 'Log in, link, Alt plus, m'), self.miss(self.A, 'links', 'Menu, Alt plus, m'), self.miss(self.A, 'links', 'other'), self.miss(self.B, 'links', 'Menu, Alt plus, m')]}
        rows = fh.rows_of(attributed, gate)
        self.assertEqual([(r['url'], r['expected'], r['cause']) for r in rows], [(self.A, 'x', 'evidence/e.json'), (self.A, 'Log in, link, Alt plus, m', 'evidence/f.json'), (self.A, 'Menu, Alt plus, m', 'access key')])

    def test_a_row_is_reproduced_at_the_freeze_and_fixed_at_head_when_only_the_freeze_misses_it(self):
        row = self.miss(self.A, 'links', 'x'); freeze = self.reading({self.A: 'comparable'}, [self.miss(self.A, 'links', 'x', 'y')]); head = self.reading({self.A: 'comparable'}, [])
        (got,) = fh.statuses([row], freeze, head)
        self.assertEqual((got['freeze'], got['head']), ({'status': 'reproduced', 'reading': 'still a miss', 'now': 'y'}, {'status': 'fixed', 'now': None}))
        self.assertTrue(fh.all_fixed([got]))

    def test_a_row_the_fresh_reading_does_not_miss_at_the_freeze_is_not_reproduced_and_is_not_called_fixed(self):
        row = self.miss(self.A, 'links', 'x'); both = self.reading({self.A: 'comparable'}, [])
        (got,) = fh.statuses([row], both, both)
        self.assertEqual((got['freeze']['status'], got['head']['status']), ('not reproduced', 'fixed'))
        self.assertFalse(fh.all_fixed([got]))

    def test_a_row_head_still_misses_says_what_the_emulator_says_now(self):
        row = self.miss(self.A, 'links', 'x'); still = self.reading({self.A: 'comparable'}, [self.miss(self.A, 'links', 'x', 'z')])
        (got,) = fh.statuses([row], still, still)
        self.assertEqual(got['head'], {'status': 'still a miss', 'now': 'z'}); self.assertFalse(fh.all_fixed([got]))

    def test_a_page_the_reading_cannot_compare_is_not_fixed(self):
        row = self.miss(self.A, 'links', 'x'); freeze = self.reading({self.A: 'comparable'}, [self.miss(self.A, 'links', 'x', 'y')]); head = self.reading({self.A: 'not comparable'}, [])
        (got,) = fh.statuses([row], freeze, head)
        self.assertEqual(got['head']['status'], 'page not comparable'); self.assertFalse(fh.all_fixed([got]))

    def test_the_exit_status_and_the_file_follow_the_rows(self):
        with tempfile.TemporaryDirectory() as d:
            files = {}
            for name, body in {'attributed': {'misses': [{'page': self.A, 'channel': 'links', 'expected': 'x', 'predicted': 'y', 'evidence': ['evidence/e.json']}]}, 'gate': {'misses': []},
                               'freeze': self.reading({self.A: 'comparable'}, [self.miss(self.A, 'links', 'x', 'y')]), 'fixed': self.reading({self.A: 'comparable'}, []),
                               'broken': self.reading({self.A: 'comparable'}, [self.miss(self.A, 'links', 'x', 'y')])}.items():
                files[name] = os.path.join(d, name + '.json'); write(files[name], json.dumps(body))
            out = os.path.join(d, 'out.json')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fh.main([files['attributed'], files['gate'], files['freeze'], files['fixed'], out]), 0); self.assertEqual(load(out)[0]['head']['status'], 'fixed')
                self.assertEqual(fh.main([files['attributed'], files['gate'], files['freeze'], files['broken']]), 1)


class Attribution(unittest.TestCase):
    def test_a_miss_is_what_the_longest_order_preserving_matching_leaves_of_the_fleets_list(self):
        self.assertEqual(ag.disagreements(['a', 'b', 'c', 'd'], ['a', 'x', 'c', 'd']), ['b'])
        self.assertEqual(ag.disagreements(['a', 'b'], ['b', 'a']), ['b']); self.assertEqual(ag.disagreements(['a'], []), ['a']); self.assertEqual(ag.disagreements([], ['a']), [])

    def test_every_miss_is_covered_by_one_cause_with_its_class_and_its_evidence_and_one_no_cause_covers_is_refused(self):
        gate = [{'url': 'https://sheffield.ac.uk/a', 'channel': 'links', 'i': 3, 'expected': 'x', 'predicted': 'y'}, {'url': 'https://ico.org.uk/b', 'channel': 'links', 'i': 5, 'expected': 'z', 'predicted': None}]
        pages = {'sheffield': ['https://sheffield.ac.uk/a'], 'scroll': ['https://ico.org.uk/b'], 'hes': []}
        evidence = {'evidence/empty-anchor-is-a-link.json': {'class': 'emulator bug', 'miss': 'm1'}, 'evidence/page-scroll-state.json': {'class': 'emulator bug', 'miss': 'm2'}}
        got = ag.attribute(gate, pages, evidence)
        self.assertEqual([(e['page'], e['i'], e['class'], e['evidence']) for e in got], [('https://sheffield.ac.uk/a', 3, 'emulator bug', ['evidence/empty-anchor-is-a-link.json']), ('https://ico.org.uk/b', 5, 'emulator bug', ['evidence/page-scroll-state.json'])])
        with self.assertRaises(SystemExit): ag.attribute(gate + [{'url': 'https://other.org/', 'channel': 'links', 'i': 0, 'expected': 'q', 'predicted': None}], pages, evidence)

    def test_what_it_attributes_is_what_check_py_explained_accepts(self):
        gate = [{'url': 'https://sheffield.ac.uk/a', 'channel': 'links', 'i': 3, 'expected': 'Page text x', 'predicted': 'y', 'shape': ['a']}]
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'evidence')); write(os.path.join(d, 'evidence', 'empty-anchor-is-a-link.json'), '{}')
            entries = ag.attribute(gate, {'sheffield': ['https://sheffield.ac.uk/a'], 'scroll': [], 'hes': []}, {'evidence/empty-anchor-is-a-link.json': {'class': 'emulator bug', 'miss': 'm'}})
            rb.write_json(os.path.join(d, 'misses-attributed.json'), {'misses': entries}); page = os.path.join(d, 'page.md'); write(page, 'Page text x')
            figure = {'gate': {'exact': 9, 'total': 10}, 'top': ['a'], 'misses': gate}
            self.assertEqual(check.check_explained(os.path.join(d, 'misses-attributed.json'), d, page, figure)[0], check.OK)

    def test_a_quoted_line_that_is_not_in_the_file_exactly_once_is_refused(self):
        with tempfile.NamedTemporaryFile('w', suffix='.py') as f:
            f.write('a = 1\nb = 2\nb = 2\n'); f.flush()
            self.assertEqual(ag.find_line(f.name, 'a = 1'), (1, 'a = 1'))
            for needle in ('b = 2', 'c = 3'):
                with self.assertRaises(SystemExit): ag.find_line(f.name, needle)


if __name__ == '__main__': unittest.main()
