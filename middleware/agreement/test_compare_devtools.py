"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

The rule of middleware/results/devtools-source/rule.md applied to readings made up for the purpose: the order of the causes, that every miss ends with one, the work list's items, and the tables."""
import contextlib, io, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_devtools as cd
import compare_sources as cs

A = 'https://x.test/p'
B = 'https://x.test/q'


def row(i, expected, predicted, channel='links', kind='fleet-vs-passive', klass=None, address=A):
    ok = expected == predicted
    if klass is None and predicted is not None and [t for t in expected.split(', ') if t != 'visited'] == [t for t in predicted.split(', ') if t != 'visited']: klass = 'history'      # measure.py's rule, which needs NVDA's source to import
    return {'address': address, 'kind': kind, 'stable': True, 'channel': channel, 'i': i, 'expected': expected, 'predicted': predicted, 'ok': ok, 'shape': ['NAME', 'ROLE'],
            'class': 'agree' if ok else (klass or ('no counterpart' if predicted is None else 'unexplained'))}


def reading(name, units, fleet=(), runs=(), address=A):
    """units: [(channel, i, expected, predicted)], fleet: [(channel, i, expected, the second capture's)], runs: channels where the two passive runs differ."""
    rows = [row(i, e, p, c, address=address) for c, i, e, p in units]
    rows += [row(i, e, p, c, kind='fleet-vs-fleet', address=address) for c, i, e, p in fleet]
    rows += [{**row(0, 'a', 'b', c, kind='passive-vs-passive', address=address)} for c in runs]
    return cs.Reading(name, {'status': {address: {'status': 'comparable'}}, 'rows': rows})


def cause(readings, name, k, old=frozenset()): return cd.attribute(readings, name, k, old)[0]


class Causes(unittest.TestCase):
    def test_every_cause_the_script_assigns_is_in_the_closed_list(self):
        for c in ('prompt', 'emulator', 'conversion: clickable', 'conversion: name+role', 'events: focus', 'macos: state', 'unexplained'): self.assertTrue(cd.is_cause(c), c)
        for c in ('tree: name', 'conversion', 'events', 'because'): self.assertFalse(cd.is_cause(c), c)       # the extension's `tree:` cause does not occur: there is no extension reading

    def test_a_different_string_is_a_conversion_miss_named_by_its_field(self):
        r = {'devtools-linux': reading('devtools-linux', [('links', 0, 'a, clickable, link', 'a, link')])}
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0)), 'conversion: clickable')

    def test_nothing_predicted_for_a_list_unit_is_a_conversion_node_and_for_an_event_channel_is_events(self):
        r = {'devtools-linux': reading('devtools-linux', [('links', 0, 'a, link', None), ('stops', 0, 'b, link', None), ('stops', 1, 'c, link', 'c, link'), ('typed', 0, '1', None)], runs=())}
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0)), 'conversion: node')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'stops', 0)), 'events: focus')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'typed', 0)), 'events: typed')

    def test_a_unit_the_extension_missed_with_the_same_string_in_an_earlier_window_is_the_emulators(self):
        r = {'devtools-linux': reading('devtools-linux', [('links', 0, 'a, link', 'a, button')])}
        old = {(A, 'links', 'a, link', 'a, button')}
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0), old), 'emulator')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0), {(A, 'links', 'a, link', 'a, graphic')}), 'conversion: role')       # another string: the extension did not miss it this way

    def test_the_measure_py_classes_come_first_then_a_moved_page_then_a_quick_test(self):
        r = {'devtools-linux': reading('devtools-linux', [('links', 0, 'Unlabelled graphic, link', 'x'), ('links', 1, 'a, link', 'b, link')], fleet=[('links', 1, 'a, link', 'z, link')])}
        r['devtools-linux'].main[(A, 'links', 0)]['class'] = 'prompt'
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0)), 'prompt')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 1)), 'page moved')
        q = {'devtools-linux': reading('devtools-linux', [('stops', 0, 'a', 'a'), ('stops', 1, 'b', None)], runs=('stops',))}
        self.assertEqual(cause(q, 'devtools-linux', (A, 'stops', 1)), 'quick test')

    def test_the_control_and_macos_are_attributed_against_this_host(self):
        linux = reading('devtools-linux', [('links', 0, 'a, link', 'a, button'), ('links', 1, 'b, link', 'b, link'), ('links', 2, 'c, link', 'c, link')])
        mac = reading('devtools-macos', [('links', 0, 'a, link', 'a, button'), ('links', 1, 'b, link', 'b, checked, link'), ('links', 2, 'c, link', 'x, link')])
        ci = reading('devtools-ubuntu-ci', [('links', 0, 'a, link', 'a, button'), ('links', 1, 'b, link', 'b, link'), ('links', 2, 'c, link', 'c, link')])
        r = {'devtools-linux': linux, 'devtools-macos': mac, 'devtools-ubuntu-ci': ci}
        self.assertEqual(cause(r, 'devtools-macos', (A, 'links', 0)), 'conversion: role')      # all predict the same string: what is wrong on this host is wrong here
        self.assertEqual(cause(r, 'devtools-macos', (A, 'links', 1)), 'macos: state')
        self.assertEqual(cause(r, 'devtools-macos', (A, 'links', 2)), 'macos: name')
        ci2 = reading('devtools-ubuntu-ci', [('links', 0, 'a, link', 'q, link')])
        self.assertEqual(cause({'devtools-linux': linux, 'devtools-ubuntu-ci': ci2}, 'devtools-ubuntu-ci', (A, 'links', 0)), 'network/runner')

    def test_macos_that_agrees_with_the_control_where_this_host_differs_is_the_runner(self):
        linux = reading('devtools-linux', [('links', 0, 'a, link', 'a, link')])
        mac = reading('devtools-macos', [('links', 0, 'a, link', 'b, link')]); ci = reading('devtools-ubuntu-ci', [('links', 0, 'a, link', 'b, link')])
        self.assertEqual(cause({'devtools-linux': linux, 'devtools-macos': mac, 'devtools-ubuntu-ci': ci}, 'devtools-macos', (A, 'links', 0)), 'network/runner')

    def test_every_miss_ends_with_one_cause_of_the_list_and_an_unexplained_one_has_its_reason(self):
        r = {'devtools-linux': reading('devtools-linux', [('links', 0, 'a, link', 'b, link'), ('stops', 0, 'x', None), ('links', 1, 'ok, link', 'ok, link')])}
        out = cd.attribute_all(r, set())
        self.assertEqual(len(out['devtools-linux']), 2)
        for m in out['devtools-linux']:
            self.assertTrue(cd.is_cause(m['cause']), m['cause'])
            self.assertTrue(m['cause'] != 'unexplained' or m['reason'])


class WorkList(unittest.TestCase):
    def test_each_item_is_read_from_the_tokens(self):
        self.assertEqual(cd.work_item('stops', 'x, clickable, link', 'x, link'), 'clickable')
        self.assertEqual(cd.work_item('stops', 'cell, row 2, column 1, Name, 4', 'cell, row 2, column 1'), 'header words')
        self.assertEqual(cd.work_item('field', 'Name, edit, 123456', 'Name, edit'), 'typed value')
        self.assertEqual(cd.work_item('links', 'Home, link, opens the front page', 'Home, link'), 'description words')
        self.assertIsNone(cd.work_item('links', 'a, link', 'b, link'))
        self.assertIsNone(cd.work_item('links', 'a, link', None))

    def test_the_units_recovered_are_the_misses_of_steps_1_and_2_less_the_misses_now_on_those_pages_only(self):
        groups = {A: 'step 2', B: 'large'}
        old = [{'address': A, 'channel': 'stops', 'expected': 'x, clickable, link', 'predicted': 'x, link'}, {'address': A, 'channel': 'stops', 'expected': 'y, clickable, link', 'predicted': 'y, link'}]
        new = [{'address': A, 'channel': 'stops', 'expected': 'x, clickable, link', 'predicted': 'x, link'}, {'address': B, 'channel': 'stops', 'expected': 'z, clickable, link', 'predicted': 'z, link'}]
        self.assertEqual(cd.work_counts(old, groups, cd.OLD_GROUPS)['clickable'], 2)
        self.assertEqual(cd.work_counts(new, groups, cd.OLD_GROUPS)['clickable'], 1)      # the large page is not one of the 14


class Tables(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.addCleanup(self.dir.cleanup)
        self.pages = [{'url': A, 'group': 'step 1', 'class': 'corpus'}, {'url': B, 'group': 'large', 'class': 'large'}]

    def write(self, path, data):
        path = os.path.join(self.dir.name, path); os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f: json.dump(data, f)
        return path

    def test_the_headline_is_given_for_all_pages_for_the_old_fourteen_and_by_group_and_class(self):
        dev = cs.Reading('devtools-linux', {'status': {}, 'rows': [row(0, 'a', 'a'), row(1, 'b', 'c'), row(0, 'd', 'd', address=B), row(1, 'e', 'e', address=B)]})
        text = '\n'.join(cd.figure_lines({'devtools-linux': dev}, {}, self.pages))
        self.assertIn('all 19 pages\n    devtools-linux           3 of 4      75.0%', text)
        self.assertIn('the 14 pages of steps 1 and 2\n    devtools-linux           1 of 2      50.0%', text)
        self.assertIn('group large\n    devtools-linux           2 of 2     100.0%', text)
        self.assertIn('class corpus\n    devtools-linux           1 of 2      50.0%', text)

    def test_the_old_figures_are_read_from_the_two_earlier_steps_and_added(self):
        d1, d2 = os.path.join(self.dir.name, 's1'), os.path.join(self.dir.name, 's2')
        self.write('s1/comparison.json', {'readings': {'devtools-linux': {'agreed': 10, 'units': 20}}, 'extensionBuys': {}})
        self.write('s2/comparison.json', {'readings': {'devtools-linux': {'agreed': 30, 'units': 40}}, 'extensionBuys': {'byClass': [{'label': 'table', 'extension': 9, 'devtools': 8, 'units': 10}]}})
        self.assertEqual(cd.old_headline([d1, d2]), (40, 60))
        self.assertEqual(cd.old_extension_table([d1, d2]), (9, 8, 10))

    def test_the_agreed_units_are_counted_by_the_group_or_class_of_their_page(self):
        dev = cs.Reading('devtools-linux', {'status': {}, 'rows': [row(0, 'a', 'a'), row(1, 'b', 'c'), row(0, 'd', 'd', address=B)]})
        self.assertEqual(cd.agreed_by(dev, {A: 'step 1', B: 'large'}), {'step 1': {'agreed': 1, 'units': 2}, 'large': {'agreed': 1, 'units': 1}})

    def test_end_to_end_writes_the_comparison_and_a_figure_with_every_miss_attributed(self):
        agreement = {'status': {A: {'status': 'comparable'}}, 'rows': [row(0, 'a, link', 'a, link'), row(1, 'b, link', 'b, button'), row(0, 'a, link', 'a, link', kind='fleet-vs-fleet')]}
        self.write('work/devtools-linux/agreement.json', agreement); self.write('work/devtools-linux-second/agreement.json', agreement)
        with open(os.path.join(self.dir.name, 'work', 'devtools-linux', 'agreement.txt'), 'w') as f: f.write('all channels: 1 of 2')
        pages = self.write('pages.json', {'sample': self.pages})
        self.write('s1/comparison.json', {'readings': {'devtools-linux': {'agreed': 1, 'units': 2}}, 'extensionBuys': {}})
        self.write('s2/comparison.json', {'readings': {'devtools-linux': {'agreed': 1, 'units': 2}}, 'extensionBuys': {}})
        out = os.path.join(self.dir.name, 'out')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cd.main(['--work', os.path.join(self.dir.name, 'work'), '--pages', pages, '--out', out, '--old', os.path.join(self.dir.name, 's1'), os.path.join(self.dir.name, 's2')]), 0)
        with open(os.path.join(out, 'figure-devtools-linux', 'misses.json')) as f: misses = json.load(f)['misses']
        self.assertEqual([m['cause'] for m in misses], ['conversion: role'])
        with open(os.path.join(out, 'comparison.json')) as f: c = json.load(f)
        self.assertEqual(c['readings']['devtools-linux'], {'agreed': 1, 'units': 2})
        self.assertTrue(os.path.exists(os.path.join(out, 'figure-devtools-linux', 'agreement.txt')))
        self.assertTrue(os.path.exists(os.path.join(out, 'comparison.txt')))


if __name__ == '__main__': unittest.main()
