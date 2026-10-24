"""python3 -m unittest discover -s emu/gatefixes -t emu/gatefixes   (from the repository root)

The tests of the four fixes of A11-176: an anchor with no href is a link, the page is scrolled where NVDA's caret leaves it, the caret follows its field when the buffer is rebuilt,
and an access key is announced. Each one's expected strings are read from the evidence the Gate committed (q3/results/gate/evidence/ and misses-attributed.json), not copied here.

What builds the platform tree and the buffer runs without anything built. What runs the emulator over a page (`pages/`, each shaped like the evidence's page, with the scripts the evidence quotes)
needs the emulator's virtualenv and Chrome (`setup.sh` builds them into $EMU_DOWNLOADS) and is skipped without them."""
import concurrent.futures, contextlib, functools, http.server, json, pathlib, random, socket, subprocess, sys, tempfile, threading, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT / 'emu')]
import standin
from paths import DOWNLOADS

VENV_PYTHON = DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python'
HAVE_EMULATOR = VENV_PYTHON.exists() and (DOWNLOADS / 'chrome155' / 'chrome-linux64' / 'chrome').exists() and (DOWNLOADS / 'nvda-src' / 'source').is_dir()
needs_emulator = unittest.skipUnless(HAVE_EMULATOR, 'needs the emulator\'s virtualenv and Chrome (setup.sh)')
GATE = ROOT / 'q3' / 'results' / 'gate'
EVIDENCE = GATE / 'evidence'
PAGES = HERE / 'pages'

SHEFFIELD = 'https://sheffield.ac.uk/ijc/people/professional-services-staff/nastaran-bozorgzad-arbab'
ICO = 'https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/when-can-an-exemption-apply-to-information-about-other-people-in-a-sar/'
CASELAW = 'https://caselaw.nationalarchives.gov.uk/uksc/2010/38'
HISTORIC = 'https://www.historicenvironment.scot/visit/all/doune-castle/shop/'


def load(path): return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def evidence_of(channel, address):
    """The Gate's evidence for one page and channel: what the fleet's list had that the frozen emulator's did not (`onlyInFleet`) and the reverse."""
    (path,) = [p for p in (EVIDENCE / channel).glob('evidence-*.json') if load(p)['url'] == address]
    return load(path)['emulator']['gate.run1']


def missed(page, channel):
    """What the fleet said on `page` that the frozen emulator did not, as the Gate attributed the ten misses (misses-attributed.json)."""
    return [m['expected'] for m in load(GATE / 'misses-attributed.json')['misses'] if m['page'] == page and m['channel'] == channel]


def free_port():
    """A port for a session (it uses this one and the next, the browser's DevTools)."""
    while True:
        port = random.randrange(20000, 30000)
        with contextlib.ExitStack() as stack:
            try:
                for p in (port, port + 1): stack.enter_context(socket.socket()).bind(('127.0.0.1', p))
            except OSError: continue
        return port


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass


class Pages:
    """pages/ served on a port of its own, and the emulator's sweep (q3/emulate.py: load_lazy_content, anchor_to_top, read_through, scroll, structure_sweep) run over each page once."""
    def __init__(self):
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(PAGES)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = 'http://127.0.0.1:%d/' % self.server.server_port
        self.results = {}

    def url(self, name): return self.base + name

    def sweep_all(self, names):
        def one(name):
            out = pathlib.Path(self.tmp.name) / (name + '.json')
            done = subprocess.run([str(VENV_PYTHON), '-I', str(ROOT / 'q3' / 'emulate.py'), self.url(name), str(out), '--port', str(free_port())], capture_output=True, text=True, timeout=600)
            if not out.exists(): raise RuntimeError(done.stderr[-2000:])
            record = load(out)
            if record.get('fault'): raise RuntimeError(record['fault'])
            return name, record
        with concurrent.futures.ThreadPoolExecutor(len(names)) as pool: self.results = dict(pool.map(one, names))

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.tmp.cleanup()


def probe(*args):
    """probe_live.py under the emulator's virtualenv: its one line of JSON."""
    done = subprocess.run([str(VENV_PYTHON), '-I', str(HERE / 'probe_live.py'), *map(str, args)], capture_output=True, text=True, timeout=600)
    if done.returncode: raise RuntimeError(done.stderr[-2000:])
    return json.loads(done.stdout.strip().splitlines()[-1])


SITE = None


def setUpModule():
    global SITE
    if HAVE_EMULATOR:
        SITE = Pages(); SITE.sweep_all(['sheffield-empty-anchor.html', 'ico-back-to-top.html', 'caselaw-document-bar.html', 'menu-closes.html'])


def tearDownModule():
    if SITE: SITE.close()


def nodes_of(rows, uids=True):
    """The extension's dump of a tree from (depth, role, extra) rows: `ix` is the position, `uid` the row's own or a number made from the position (none, for a tree without them)."""
    return [{'depth': depth, 'ix': ix, 'state': {}, 'role': role, **({'uid': 1000 + ix} if uids else {}), **extra} for ix, (depth, role, extra) in enumerate(rows)]


def tree(*rows): return standin.build_platform_tree(nodes_of(rows))


def lines_of(buffer):
    out = []
    def walk(node, base):
        if isinstance(node, standin.TextField): out.append((base, node.text))
        else:
            for kid in node.kids: walk(kid, base); base += kid.length
    walk(buffer.root, 0)
    return out


class AnchorWithNoHref(unittest.TestCase):
    """Cause 1: Chromium on Windows reports STATE_SYSTEM_LINKED for every node whose role is a link (ax_platform_node_win.cc:8242-8245)."""
    NODE = load(EVIDENCE / 'empty-anchor-is-a-link.json')['what the emulator has']['node of <a id="main-content">'][0]

    def evidence_node(self, ix=1, **extra):
        """The evidence's node as the extension would dump it: its role, no name, only the state `offscreen`, and no `linked`."""
        n = self.NODE
        return standin.PN({'depth': 1, 'ix': ix, 'role': n['role'], 'name': n['name'], 'state': dict(n['state']), 'location': n['location'], 'htmlTag': n['tag'], **extra}, None)

    def test_the_evidence_node_has_no_linked_state_and_is_a_link(self):
        self.assertEqual((self.NODE['role'], 'linked' in self.NODE['state']), ('link', False))

    def test_an_anchor_with_no_href_is_linked(self):
        self.assertTrue(self.evidence_node().msaa_state() & standin.CONST['STATE_SYSTEM_LINKED'])

    def test_the_ax_state_linked_still_sets_it(self):
        node = standin.PN({'depth': 1, 'ix': 1, 'role': 'genericContainer', 'state': {'linked': True}}, None)
        self.assertTrue(node.msaa_state() & standin.CONST['STATE_SYSTEM_LINKED'])

    def test_a_node_that_is_not_a_link_is_not_linked(self):
        node = standin.PN({'depth': 1, 'ix': 1, 'role': 'genericContainer', 'state': {}}, None)
        self.assertFalse(node.msaa_state() & standin.CONST['STATE_SYSTEM_LINKED'])

    def test_the_link_leaves_a_line_in_the_buffer(self):
        """gecko_ia2 fillVBuf: in a link the node is interactive, and an interactive node with no text still has one character, so its line is there to be found."""
        root = tree((0, 'rootWebArea', {'name': 'page'}), (1, 'link', {'state': dict(self.NODE['state'])}), (1, 'paragraph', {}), (2, 'staticText', {'name': 'Text'}))
        buffer = standin.Builder(root).build()
        link = buffer.root.kids[0]
        self.assertEqual((link.length, lines_of(buffer)[0][1]), (1, standin.EMPTY_TEXT))
        self.assertEqual(link.attrs['IAccessible::state_%d' % standin.CONST['STATE_SYSTEM_LINKED']], '1')

    @needs_emulator
    def test_the_breadcrumb_after_it_stops_repeating_main_landmark_and_the_empty_link_is_listed(self):
        """The links sweep of a page shaped like the evidence's (a nav, then <main> opening with the empty anchor, then a breadcrumb nav) has what the fleet's had and not what the frozen emulator's had."""
        links = SITE.results['sheffield-empty-anchor.html']['structure']['links']; found = evidence_of('links', SHEFFIELD)
        fleet = [s for s in found['onlyInFleet'] if 'Alt plus' not in s]
        self.assertEqual(sorted(fleet), ['You are here, navigation landmark, list, with 5 items, Home, link', 'link'])
        for line in fleet: self.assertIn(line, links)
        for line in found['onlyInEmulator']:
            if 'main landmark' in line: self.assertNotIn(line, links)
        self.assertEqual(missed(SHEFFIELD, 'links'), ['You are here, navigation landmark, list, with 5 items, Home, link'])


class AccessKey(unittest.TestCase):
    """The announcement of an access key: `Alt plus, m` (ax_platform_node_win.cc:1901-1910, ax_object.cc KeyboardShortcut, gecko_ia2.cpp:672-679)."""
    def node(self, **extra): return standin.PN({'depth': 1, 'ix': 1, 'role': 'link', 'name': 'Log in to MUSE', 'state': {'focusable': True, 'linked': True}, **extra}, None)

    def test_the_platform_node_answers_alt_plus_the_access_key(self):
        self.assertEqual(self.node(accessKey='m').keyboard_shortcut(), 'Alt+m')

    def test_a_node_with_no_access_key_answers_none(self):
        self.assertIsNone(self.node().keyboard_shortcut())

    def test_the_buffer_carries_it_as_the_keyboard_shortcut(self):
        root = tree((0, 'rootWebArea', {'name': 'page'}), (1, 'link', {'name': 'Log in to MUSE', 'accessKey': 'm', 'state': {'linked': True}}), (2, 'staticText', {'name': 'Log in to MUSE'}),
                    (1, 'link', {'name': 'Help', 'state': {'linked': True}}), (2, 'staticText', {'name': 'Help'}))
        buffer = standin.Builder(root).build()
        self.assertEqual([c.attrs['keyboardShortcut'] for c in buffer.root.kids], ['Alt+m', ''])

    @needs_emulator
    def test_iaccessible_answers_it(self):
        self.assertEqual(probe('facade'), {'with': 'Alt+m', 'without': None})

    @needs_emulator
    def test_the_link_is_spoken_as_the_fleet_spoke_it(self):
        links = SITE.results['sheffield-empty-anchor.html']['structure']['links']
        spoken = [s for s in evidence_of('links', SHEFFIELD)['onlyInFleet'] if 'Alt plus' in s]
        self.assertEqual(len(spoken), 2); self.assertIn('Log in to MUSE, link, Alt plus, m', spoken)
        for line in spoken: self.assertIn(line, links)
        self.assertIn('Help, link', links)      # a link with no access key is spoken as it was


class ScrollState(unittest.TestCase):
    """Cause 2: on the fleet NVDA scrolls the browser as its caret moves, so the page sits where the read-through left it when the sweeps begin."""
    @needs_emulator
    def test_ico_back_to_top_is_listed(self):
        found = SITE.results['ico-back-to-top.html']['structure']['links']
        self.assertEqual(missed(ICO, 'links'), ['Back to top, same page, link']); self.assertEqual(evidence_of('links', ICO)['onlyInFleet'], missed(ICO, 'links'))
        self.assertEqual(found, missed(ICO, 'links'))

    @needs_emulator
    def test_the_caselaw_document_bar_is_listed(self):
        result = SITE.results['caselaw-document-bar.html']['structure']; found = evidence_of('headings', CASELAW)
        (title,) = missed(CASELAW, 'headings'); self.assertEqual(found['onlyInFleet'], [title])
        self.assertIn(title, result['headings'])
        for line in found['onlyInEmulator']: self.assertNotIn(line, result['headings'])      # the same title as a level 1 heading: the bar's is found first, and the sweep keeps one of the two
        self.assertEqual(missed(CASELAW, 'links'), ['Skip to end, same page, link']); self.assertIn('Skip to end, same page, link', result['links'])

    @needs_emulator
    def test_the_one_scroll_nvda_asked_for_is_delivered_once_and_survives_a_read_of_the_tree_while_its_node_is_there(self):
        done = probe('scroll', SITE.url('ico-back-to-top.html'), free_port())
        self.assertEqual(done['before'], {'scrollY': 0, 'pending': True})      # the keys scrolled nothing, and the last request is waiting
        self.assertTrue(done['delivered']); self.assertGreater(done['after']['scrollY'], 0); self.assertFalse(done['after']['pending'])
        self.assertFalse(done['again'])
        self.assertEqual({k: done['survived'][k] for k in ('asked', 'pending', 'delivered')}, {'asked': True, 'pending': True, 'delivered': True}); self.assertGreater(done['survived']['scrollY'], 0)

    @needs_emulator
    def test_a_request_for_a_node_that_has_left_the_tree_is_not_delivered(self):
        done = probe('scroll', SITE.url('ico-back-to-top.html'), free_port())
        self.assertEqual(done['gone'], {'delivered': False, 'scrollY': 0})      # indexes are renumbered at every read, so the request names the node by its uid, and a node that is gone is not scrolled to by another's index


class CaretAfterTheBufferIsRebuilt(unittest.TestCase):
    """Cause 3: storage.cpp:677-686 records the fields the selection is in, and :742-760 puts it back in the deepest of them that is still there."""
    @staticmethod
    def page(first, second, drop_second=False):
        """root > [first paragraph] [section > [second paragraph] [last paragraph]]; uids are the nodes', ix whatever the position gives."""
        rows = [(0, 'rootWebArea', {'name': 'page', 'uid': 1}), (1, 'paragraph', {'uid': 2}), (2, 'staticText', {'name': first, 'uid': 3}), (1, 'section', {'uid': 4})]
        if not drop_second: rows += [(2, 'paragraph', {'uid': 5}), (3, 'staticText', {'name': second, 'uid': 6})]
        rows += [(2, 'paragraph', {'uid': 7}), (3, 'staticText', {'name': 'tail', 'uid': 8})]
        return standin.Builder(standin.build_platform_tree(nodes_of(rows))).build()

    def test_the_text_of_the_page_is_what_the_offsets_below_are_taken_from(self):
        self.assertEqual(lines_of(self.page('aaaa', 'bbbbbb')), [(0, 'aaaa'), (4, 'bbbbbb'), (10, 'tail')])

    def test_the_fields_are_recorded_from_the_root_down_with_the_selection_relative_to_each(self):
        buffer = self.page('aaaa', 'bbbbbb'); buffer.sel = (7, 7)      # the third letter of the second paragraph
        keys = [c.key for c in (buffer.root, buffer.root.kids[1], buffer.root.kids[1].kids[0])]
        self.assertEqual(buffer.selection_identifiers(), [(keys[0], 7), (keys[1], 3), (keys[2], 3)])

    def test_the_selection_goes_with_its_field_when_the_text_before_it_changes_length(self):
        old = self.page('aaaa', 'bbbbbb'); old.sel = (7, 7)
        new = self.page('aaaaaaaaaa', 'bbbbbb'); new.sel = old.sel
        new.correct_selection(old.selection_identifiers())
        self.assertEqual(new.sel, (13, 13))      # 10 + 3: the third letter of the second paragraph still, and a caret is still a caret (storage.cpp keeps the selection's length)

    def test_a_selection_keeps_its_length(self):
        old = self.page('aaaa', 'bbbbbb'); old.sel = (7, 9)
        new = self.page('aaaaaaaaaa', 'bbbbbb'); new.sel = old.sel
        new.correct_selection(old.selection_identifiers())
        self.assertEqual(new.sel, (13, 15))

    def test_the_selection_stays_where_it_was_when_nothing_before_it_changed(self):
        old = self.page('aaaa', 'bbbbbb'); old.sel = (7, 7)
        new = self.page('aaaa', 'bbbbbb'); new.sel = (0, 0)      # a buffer built anew starts with the selection the caller gives it; the correction is what puts the caret back
        new.correct_selection(old.selection_identifiers())
        self.assertEqual(new.sel, (7, 7))

    def test_a_removed_field_puts_the_selection_in_the_deepest_ancestor_that_is_left_clamped_to_its_last_character(self):
        old = self.page('aaaa', 'bbbbbb'); old.sel = (9, 9)      # the last letter of the second paragraph, which is 6 + 4 characters into the section
        new = self.page('aaaa', 'bbbbbb', drop_second=True); new.sel = old.sel
        new.correct_selection(old.selection_identifiers())
        # the section survives with only 'tail' in it (4 characters), the selection was 5 into it: clamped to 3, on top of the section's start (4)
        self.assertEqual(new.sel[0], 4 + 3)

    def test_a_removed_ancestor_stops_the_walk_at_the_one_before_it(self):
        old = self.page('aaaa', 'bbbbbb'); old.sel = (9, 9)
        identifiers = old.selection_identifiers()
        new = self.page('aaaa', 'bbbbbb'); new.by_key.pop(identifiers[1][0])      # the section is gone, with the paragraph in it still there by its key
        new.sel = (0, 0)
        new.correct_selection(identifiers)
        self.assertEqual(new.sel, (9, 9))      # only the root was found: 9 relative to a root that starts at 0

    def test_a_field_found_under_another_parent_stops_the_walk(self):
        old = self.page('aaaa', 'bbbbbb'); old.sel = (7, 7)
        identifiers = old.selection_identifiers()
        new = self.page('aaaa', 'bbbbbb'); new.sel = (0, 0)
        moved = new.by_key[identifiers[2][0]]; moved.parent.kids.remove(moved); new.root.kids.insert(0, moved); moved.parent = new.root      # the paragraph is now a child of the root
        new.correct_selection(identifiers)
        section = new.root.kids[2]
        self.assertEqual(new.sel[0], section.offset_in_tree() + 3)      # the section is found (the root's child, 3 in), its paragraph is not under it: the walk ends at the section, which now starts after the 6 + 4 characters before it

    def test_a_tree_with_no_uids_finds_nothing_again_whatever_its_indexes_are(self):
        """Without the extension's id the only number a node has is its index, which is renumbered at every read: it is not taken for the node."""
        def page(text):
            rows = [(0, 'rootWebArea', {'name': 'page'}), (1, 'paragraph', {}), (2, 'staticText', {'name': text}), (1, 'paragraph', {}), (2, 'staticText', {'name': 'bbbbbb'})]
            return standin.Builder(standin.build_platform_tree(nodes_of(rows, uids=False))).build()
        old = page('aaaa'); old.sel = (6, 6)
        new = page('aaaaaaaaaa'); new.sel = (6, 6)
        new.correct_selection(old.selection_identifiers())
        self.assertEqual(new.sel, (6, 6))

    def test_a_selection_with_no_field_found_is_left_alone(self):
        new = self.page('aaaa', 'bbbbbb'); new.sel = (5, 5)
        new.correct_selection([((1, 99999), 3)])
        self.assertEqual(new.sel, (5, 5))

    @needs_emulator
    def test_the_extension_numbers_a_node_the_same_way_in_every_read_while_ix_moves(self):
        done = probe('uids', SITE.url('sheffield-empty-anchor.html'), free_port())
        uids = lambda rows: [uid for _, uid, _, _ in rows]
        self.assertEqual(done['first'], done['second'])
        self.assertEqual(len(set(uids(done['first']))), len(done['first']))      # one id for each node
        was = {uid: ix for ix, uid, _, _ in done['first']}; now = {uid: ix for ix, uid, _, _ in done['added']}
        moved = [uid for uid in was if uid in now and now[uid] != was[uid]]
        self.assertGreater(len(moved), 50)      # the paragraph added at the top renumbered the nodes after it ...
        self.assertTrue(set(was) <= set(now))      # ... and every node that was there is there by the same id
        self.assertEqual([row[2] for row in done['added'] if row[1] not in was], ['paragraph', 'staticText', 'inlineTextBox'])

    @needs_emulator
    def test_close_search_is_listed_between_open_search_and_close_notification(self):
        fields = SITE.results['menu-closes.html']['structure']['formFields']; (close_search,) = missed(HISTORIC, 'formFields')
        self.assertEqual(close_search, 'Close search, button, expanded')
        at = fields.index(close_search)      # the evidence: "the fleet lists it between Open search and Close notification"
        self.assertIn('Open search', fields[at - 1]); self.assertEqual(fields[at + 1], 'Close notification, button')


if __name__ == '__main__':
    unittest.main()
