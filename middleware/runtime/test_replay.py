"""Recorded sessions of the sample suite (fixtures/*.jsonl.gz: what the extension and the page told the runtime during one test), run through the predictor with NVDA and without a browser.

Needs the emulator's virtualenv and NVDA's source (`setup.sh`, or the bundle) in $EMU_DOWNLOADS; skipped without them. Each recording is of a test in middleware/sample-suite/tests/fixtures."""
import json, os, pathlib, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'emu'))
from paths import DOWNLOADS

PYTHON = next((p for p in (DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python', DOWNLOADS / 'python' / 'bin' / 'python3') if p.exists()), None)
HAVE = PYTHON is not None and (DOWNLOADS / 'nvda-src' / 'source').is_dir()
_cache = {}


def replay(name, *flags):
    key = (name, flags)
    if key not in _cache:
        out = subprocess.run([str(PYTHON), '-I', str(HERE / 'replay.py'), str(HERE / 'fixtures' / f'{name}.jsonl.gz'), *flags], capture_output=True, text=True, env={**os.environ, 'EMU_DOWNLOADS': str(DOWNLOADS)}, timeout=300)
        if out.returncode: raise RuntimeError(out.stderr[-2000:])
        d = json.loads(out.stdout)
        _cache[key] = d
    return _cache[key]


def said(name, *flags, kinds=('speech',)):
    return [(r['cause'], r['text']) for r in sorted(replay(name, '--no-sweeps', *flags)['records'], key=lambda r: r['t']) if r['kind'] in kinds]


def flagged(name): return [r['flag'] for r in replay(name, '--no-sweeps')['records'] if r['kind'] == 'flag']


@unittest.skipUnless(HAVE, "needs the emulator's virtualenv and NVDA's source (setup.sh)")
class Replay(unittest.TestCase):
    def test_every_tab_stop_is_spoken_though_the_tree_updates_batch_them(self):
        """Seven stops, the tree saw six of them (measured): the page's own focusin events carry the rest."""
        focus = [t for c, t in said('tab-order') if c == 'focus']
        self.assertEqual([t.split(', ')[-2] if t.endswith('link') or t.endswith('button') else t for t in focus][:2], ['Home', 'Basket'])
        self.assertEqual(len(focus), 6)
        self.assertTrue(focus[-1].endswith('Create account, button'))

    def test_a_document_that_has_loaded_is_spoken_before_what_the_first_key_did_in_it(self):
        first = said('tab-order')[0]
        self.assertEqual(first[0], 'load')
        self.assertTrue(first[1].startswith('Create an account - Example shop, document'))

    def test_typing_in_a_field_is_echoed_key_by_key_and_filling_it_is_not(self):
        self.assertEqual([t for c, t in said('typing') if c == 'typed'], ['A', 'd', 'a'])

    def test_a_live_region_says_each_change_the_page_made(self):
        self.assertEqual([t for c, t in said('basket-live') if c == 'live'], ['1 item in your basket', '2 items in your basket'])

    def test_an_alert_that_appears_on_the_last_change_of_a_test_is_still_heard(self):
        self.assertEqual([t for c, t in said('error-alert') if c == 'live'], ['Enter an email address'])
        self.assertEqual(flagged('error-alert'), [])

    def test_a_route_change_of_the_page_is_not_spoken(self):
        self.assertEqual([c for c, t in said('spa-route')], ['load', 'focus'])

    def test_the_flags_are_raised_for_what_should_raise_them_and_for_nothing_else(self):
        self.assertEqual(flagged('toolbar-unnamed'), ['focus-without-name'])
        self.assertEqual(flagged('cookie-panel'), ['silent-dialog'])
        self.assertEqual(flagged('error-silent'), ['unheard-error'])
        self.assertEqual(flagged('error-focus'), ['unheard-error'])
        self.assertEqual(flagged('delete-dialog'), [])
        self.assertEqual(flagged('tab-order'), [])

    def test_a_dialog_that_takes_the_focus_is_said_by_the_focus_move(self):
        self.assertEqual([t for c, t in said('delete-dialog') if c == 'focus'], ['Delete account, button', 'Keep my account, button'])

    def test_each_state_a_test_reaches_is_swept_once_and_no_key_reaches_the_browser(self):
        sweeps = [r for r in replay('tab-order')['records'] if r['kind'] == 'sweep']
        self.assertEqual(len(sweeps), 1)
        self.assertEqual(sweeps[0]['trigger'], 'load')
        self.assertEqual(sweeps[0]['counts']['headings'], 1)
        self.assertGreater(sweeps[0]['keys'], 0)
        self.assertGreater(sweeps[0]['notDelivered'], 0)      # the keys the sweep pressed, and the page was not sent one
        self.assertEqual(sweeps[0]['errors'], [])

    def test_a_state_is_swept_over_the_last_tree_it_had_and_not_the_first(self):
        """A page's iframes and its late content are in the tree some time after it has loaded; a sweep over the first tree would not see them."""
        import gzip
        with gzip.open(HERE / 'fixtures' / 'basket-live.jsonl.gz', 'rt') as f: snaps = [json.loads(l)['body'] for l in f if json.loads(l)['k'] == 'snap']
        sweep = next(r for r in replay('basket-live')['records'] if r['kind'] == 'sweep')
        self.assertEqual(sweep['treeAt'], max(s['t'] for s in snaps))
        self.assertGreater(sweep['treeAt'], min(s['t'] for s in snaps))

    def test_a_dialog_is_a_state_of_its_own(self):
        sweeps = [r['trigger'] for r in replay('delete-dialog')['records'] if r['kind'] == 'sweep']
        self.assertEqual(sorted(sweeps), ['dialog', 'load'])

    def test_with_the_report_flag_each_focus_move_also_carries_what_repeating_the_focus_says(self):
        records = [r for r in replay('tab-order', '--no-sweeps', '--report-focus')['records'] if r['kind'] == 'speech' and r['cause'] == 'focus']
        self.assertTrue(all('repeatFocus' in r for r in records))
        self.assertEqual(records[0]['repeatFocus'], 'Home, link, focused, linked')

    def test_the_emulator_boots_where_nothing_is_in_the_home_directory(self):
        """emu/winuser_standin.py read NVDA's source from a path in one machine's home; a bundle is unpacked into a cache, and a CI runner's home has no such directory."""
        with tempfile.TemporaryDirectory() as home:
            out = subprocess.run([str(PYTHON), '-I', str(HERE / 'replay.py'), str(HERE / 'fixtures' / 'basket-live.jsonl.gz'), '--no-sweeps'], capture_output=True, text=True,
                                 env={**os.environ, 'HOME': home, 'EMU_DOWNLOADS': str(DOWNLOADS)}, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-1500:])
        self.assertIn('1 item in your basket', out.stdout)

    def test_nothing_it_writes_is_named_for_an_a11ign_evidence_field(self):
        banned = {'transcript', 'structure', 'interaction', 'observed', 'media', 'formInputs', 'diagnostics', 'focusOrder', 'typedFeedback', 'dialogEscape'}
        def keys(x):
            if isinstance(x, dict): return set(x) | set().union(*[keys(v) for v in x.values()]) if x else set()
            if isinstance(x, list): return set().union(*[keys(v) for v in x]) if x else set()
            return set()
        self.assertEqual(keys(replay('tab-order')['records']) & banned, set())


if __name__ == '__main__': unittest.main()
