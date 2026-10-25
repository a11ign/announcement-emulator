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

    def test_a_browser_launched_again_is_heard_as_the_first_was(self):
        """Playwright replaces a worker after a timeout; the new browser's extension numbers its snapshots and its pages from the start. Two sessions run one after the other must give twice one session's speech."""
        import gzip
        with gzip.open(HERE / 'fixtures' / 'basket-live.jsonl.gz', 'rt') as f: rows = f.read().splitlines()
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'two.jsonl.gz'
            with gzip.open(path, 'wt') as f: f.write('\n'.join(rows + [json.dumps({'k': 'ready', 'arrived': 0, 'body': {'t': 1}})] + rows) + '\n')
            out = subprocess.run([str(PYTHON), '-I', str(HERE / 'replay.py'), str(path), '--no-sweeps'], capture_output=True, text=True, env={**os.environ, 'EMU_DOWNLOADS': str(DOWNLOADS)}, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-1500:])
        records = [r for r in json.loads(out.stdout)['records'] if r['kind'] == 'speech']
        self.assertEqual([r['text'] for r in records if r['cause'] == 'live'], ['1 item in your basket', '2 items in your basket'] * 2)
        self.assertEqual(sum(r['cause'] == 'load' for r in records), 2)      # the second browser's page is a new page, and its load is heard

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

    def test_the_emulators_own_launch_of_a_browser_is_still_the_one_that_runs_when_no_session_is_given(self):
        """LiveDoc gained a `session` argument; inside it the name once stood for the module that launches Chrome, and the system tests of Q2 and the sweeps of Q3 broke (`'NoneType' has no attribute 'Session'`)."""
        probe = (
            "import sys, json; sys.path[:0] = [%r, %r]\n"
            "import boot, live, replay\n"
            "snap = [json.loads(l) for l in __import__('gzip').open(%r, 'rt')]\n"
            "snap = next(r['body'] for r in snap if r['k'] == 'snap' and len(r['body']['nodes']) > 5)\n"
            "import predict\n"
            "class Launched(predict.SnapshotSession):\n"
            "    def __init__(self, page=None, url=None, port=None): super().__init__(snap)\n"
            "    def navigate(self, url): return {'href': url}\n"
            "live.launcher.Session = Launched\n"
            "d = live.LiveDoc(url='http://x/')\n"
            "print(json.dumps(d.navigated))\n") % (str(ROOT / 'emu'), str(HERE), str(HERE / 'fixtures' / 'basket-live.jsonl.gz'))
        out = subprocess.run([str(PYTHON), '-I', '-c', probe], capture_output=True, text=True, env={**os.environ, 'EMU_DOWNLOADS': str(DOWNLOADS)}, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-1500:])
        self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1]), {'href': 'http://x/'})

    def test_nothing_it_writes_is_named_for_an_a11ign_evidence_field(self):
        banned = {'transcript', 'structure', 'interaction', 'observed', 'media', 'formInputs', 'diagnostics', 'focusOrder', 'typedFeedback', 'dialogEscape'}
        def keys(x):
            if isinstance(x, dict): return set(x) | set().union(*[keys(v) for v in x.values()]) if x else set()
            if isinstance(x, list): return set().union(*[keys(v) for v in x]) if x else set()
            return set()
        self.assertEqual(keys(replay('tab-order')['records']) & banned, set())


@unittest.skipUnless(HAVE, "needs the emulator's virtualenv and NVDA's source (setup.sh)")
class ReplayDevtools(unittest.TestCase):
    """The same sessions with the tree read through the DevTools port (axtree.py, where the extension is given none: macOS). Recorded with ANNOUNCEMENT_EMULATOR_TREE=devtools."""
    def test_every_tab_stop_is_spoken(self):
        focus = [t for c, t in said('devtools-tab-order') if c == 'focus']
        self.assertEqual(focus, ['Home, link', 'Basket, link', 'main landmark | form landmark | Full name, edit, blank', 'Email address, edit, blank', 'Send me news, check box, not checked', 'Create account, button'])
        self.assertTrue(said('devtools-tab-order')[0][1].startswith('Create an account - Example shop, document'))

    def test_typing_is_echoed_and_a_live_region_is_said(self):
        self.assertEqual([t for c, t in said('devtools-typing') if c == 'typed'], ['A', 'd', 'a'])
        self.assertEqual([t for c, t in said('devtools-basket-live') if c == 'live'], ['1 item in your basket', '2 items in your basket'])

    def test_a_button_with_no_name_is_flagged_and_the_page_with_none_is_not(self):
        self.assertEqual(flagged('devtools-toolbar-unnamed'), ['focus-without-name'])
        self.assertEqual(flagged('devtools-tab-order'), [])


def stops(name):
    """What was said for each focus move of a recording, in order."""
    return [t for c, t in said(name) if c == 'focus']


def frame_lists(name): return [r['lists']['frames'] for r in replay(name)['records'] if r['kind'] == 'sweep']


NEW_WINDOW = ['Read the guidance on accuracy(link opens a new window), link', 'Advanced search Link opens in new window, link', 'Tell us what you think (opens in a new tab), link', 'Home, link']
SAME_PAGE = ['Top, same page, link', 'Details, same page, link', 'This page, same page, link', 'This page, questions, same page, link', 'A path in the fragment, link', 'Step two, link', 'Another page, link']
AFTER_THE_ROUTE = ['Go to step two, button', 'Steps, navigation landmark, Step one, link', 'Step two, same page, link', 'Step two, questions, same page, link', 'Another page, link']
NESTED = ['Billing address, frame, Billing address, heading, level 2', 'Card details, frame, Card details, heading, level 3', 'Delivery notes, frame, Delivery notes, heading, level 2']


@unittest.skipUnless(HAVE, "needs the emulator's virtualenv and NVDA's source (setup.sh)")
class Misses(unittest.TestCase):
    """The faults the agreement measurement attributed to the middleware (A11-234), on pages written for them (middleware/sample-suite/pages/misses), recorded through the extension's tree (`PREFIX = ''`) and the
    DevTools port's (`devtools-`). Each recording is of the test of the same name in middleware/sample-suite/tests/misses."""
    PREFIX = ''

    def name(self, what): return f'misses/{self.PREFIX}{what}'

    def test_a_link_whose_name_is_longer_than_its_text_is_found_by_its_dom_node_and_every_stop_is_spoken(self):
        """The names the page script could make from the element miss a hidden span written with no space before it and a name CSS generates: four stops, and none unresolved."""
        self.assertEqual(stops(self.name('focus-by-node')), NEW_WINDOW)
        self.assertEqual(replay(self.name('focus-by-node'), '--no-sweeps')['stats']['unresolvedFocus'], 0)

    def test_a_link_to_the_address_of_the_page_is_same_page_and_a_link_that_goes_elsewhere_in_it_is_not(self):
        """NVDA's own rule (utils/urlUtils.py isSamePageURL): the address without its fragment is the document's, and a fragment with a slash in it is not one."""
        self.assertEqual(stops(self.name('same-page')), SAME_PAGE)

    def test_the_links_of_a_page_are_same_page_by_the_address_it_has_now_and_not_the_address_it_loaded_at(self):
        """pushState gives the document a new address with no load. Before the fix `Step one` was said `same page` and `Step two` was not (gecko_ia2.py:605: the buffer's address is the document's value, now)."""
        self.assertEqual(stops(self.name('same-page-route')), AFTER_THE_ROUTE)

    def test_every_frame_is_listed_as_quick_navigation_lists_it_nested_ones_too(self):
        self.assertEqual(frame_lists(self.name('frames')), [NESTED])

    def test_a_frame_below_the_fold_is_listed_with_what_the_browser_has_shown_of_it(self):
        """A frame the page has not scrolled to is listed by its name alone in the extension's tree: Chromium does not tell the browser of a frame it does not draw (attributed `offscreen frame`, not fixed here). The DevTools port asks the page and gets it."""
        listed = ['Opening hours, frame, Delivery notes, heading, level 2', 'Prices, frame' if self.PREFIX == '' else 'Prices, frame, Card details, heading, level 3']
        self.assertEqual(frame_lists(self.name('frames-below-the-fold')), [listed])

    def test_a_frame_the_test_scrolled_to_is_listed_with_its_first_line(self):
        self.assertEqual(frame_lists(self.name('frames-scrolled-to')), [['Opening hours, frame, Delivery notes, heading, level 2', 'Prices, frame, Card details, heading, level 3']])


@unittest.skipUnless(HAVE, "needs the emulator's virtualenv and NVDA's source (setup.sh)")
class MissesDevtools(Misses):
    PREFIX = 'devtools-'


if __name__ == '__main__': unittest.main()
