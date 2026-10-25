"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

The rule of middleware/results/tree-source/rule.md applied to readings made up for the purpose: the margin, the order of the causes, and that every miss ends with one."""
import contextlib, io, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_sources as cs

A = 'https://x.test/p'


def row(i, expected, predicted, channel='links', kind='fleet-vs-passive', klass=None, address=A):
    ok = expected == predicted
    if klass is None and predicted is not None and [t for t in expected.split(', ') if t != 'visited'] == [t for t in predicted.split(', ') if t != 'visited']: klass = 'history'      # measure.py's rule, which needs NVDA's source to import
    return {'address': address, 'kind': kind, 'stable': True, 'channel': channel, 'i': i, 'expected': expected, 'predicted': predicted, 'ok': ok, 'shape': ['NAME', 'ROLE'],
            'class': 'agree' if ok else (klass or ('no counterpart' if predicted is None else 'unexplained'))}


def reading(name, units, fleet=(), runs=()):
    """units: [(channel, i, expected, predicted)], fleet: [(channel, i, expected, the second capture's)], runs: channels where the two passive runs differ."""
    rows = [row(i, e, p, c) for c, i, e, p in units]
    rows += [row(i, e, p, c, kind='fleet-vs-fleet') for c, i, e, p in fleet]
    rows += [{**row(0, 'a', 'b', c, kind='passive-vs-passive'), 'address': A} for c in runs]
    return cs.Reading(name, {'status': {A: {'status': 'comparable'}}, 'rows': rows})


def cause(readings, name, k): return cs.attribute(readings, name, k)[0]


class Fields(unittest.TestCase):
    def test_the_field_is_what_the_differing_tokens_are(self):
        self.assertEqual(cs.fields_differing('a, link', 'a, clickable, link'), 'clickable')
        self.assertEqual(cs.fields_differing('item, 1 of 3, link', 'item, link'), 'position in set')
        self.assertEqual(cs.fields_differing('list, with 3 items, x', 'list, with 4 items, x'), 'set size')
        self.assertEqual(cs.fields_differing('x, row 2, column 1', 'x'), 'table index')
        self.assertEqual(cs.fields_differing('x, checked, button', 'x, button'), 'state')
        self.assertEqual(cs.fields_differing('x, graphic, link', 'x, link'), 'role')
        self.assertEqual(cs.fields_differing('x, link', 'y, link'), 'name')
        self.assertEqual(cs.fields_differing('a, b', 'b, a'), 'order')
        self.assertEqual(cs.fields_differing('x, clickable, link', 'y, link'), 'clickable+name')


class Margin(unittest.TestCase):
    def pair(self, ext_ok, dev_ok, n=100):
        mk = lambda k: [('links', i, f'u{i}', f'u{i}' if i < k else None) for i in range(n)]      # noqa: E731
        return reading('ext-linux', mk(ext_ok)), reading('devtools-linux', mk(dev_ok))

    def test_a_lead_of_exactly_the_margin_is_inside_it_and_a_tenth_more_is_not(self):
        ext, dev = self.pair(81, 80)
        self.assertEqual((cs.buys(ext, dev)['leadPoints'], cs.buys(ext, dev)['recommendation']), (1.0, 'drop the extension'))
        ext, dev = self.pair(82, 80)
        self.assertEqual(cs.buys(ext, dev)['recommendation'], 'keep both')
        ext, dev = self.pair(80, 83)       # DevTools ahead
        self.assertEqual((cs.buys(ext, dev)['leadPoints'], cs.buys(ext, dev)['recommendation']), (-3.0, 'drop the extension'))

    def test_only_the_units_both_readings_compare_count(self):
        ext = reading('ext-linux', [('links', 0, 'a', 'a'), ('links', 1, 'b', 'b'), ('links', 2, 'c', 'c')])
        dev = reading('devtools-linux', [('links', 0, 'a', 'a'), ('links', 1, 'b', None)])      # the third unit is not in this reading
        b = cs.buys(ext, dev)
        self.assertEqual((b['units'], b['extension'], b['devtools'], b['extensionOnly'], b['devtoolsOnly']), (2, 2, 1, 1, 0))

    def test_the_margin_is_an_argument_of_the_rule_and_the_line_says_which_it_applied(self):
        ext, dev = self.pair(85, 80)
        self.assertEqual(cs.buys(ext, dev, margin=5.0)['recommendation'], 'drop the extension')
        self.assertIn('KEEP BOTH', cs.recommendation_line(cs.buys(ext, dev)))
        self.assertIn('above the 1.0-point margin', cs.recommendation_line(cs.buys(ext, dev)))


class Causes(unittest.TestCase):
    def rs(self, ext_units, dev_units, **more):
        return {'ext-linux': reading('ext-linux', ext_units, **more.get('ext', {})), 'devtools-linux': reading('devtools-linux', dev_units, **more.get('dev', {})), **more.get('others', {})}

    def test_a_visited_prompt_or_language_miss_keeps_the_measures_class(self):
        r = self.rs([('links', 0, 'x, visited, link', 'x, link')], [('links', 0, 'x, visited, link', 'x, link')])
        self.assertEqual(cause(r, 'ext-linux', (A, 'links', 0)), 'history')

    def test_a_unit_the_second_capture_does_not_have_is_the_page_moving_and_comes_before_the_tree(self):
        r = self.rs([('links', 0, 'a', 'b')], [('links', 0, 'a', 'a')], ext={'fleet': [('links', 0, 'a', 'z')]})
        self.assertEqual(cause(r, 'ext-linux', (A, 'links', 0)), 'page moved')

    def test_the_last_stop_lost_where_the_runs_differ_is_a_quick_test(self):
        units = [('stops', 0, 'a', 'a'), ('stops', 1, 'b', None)]
        r = self.rs(units, units, dev={'runs': ['stops']})
        self.assertEqual(cause(r, 'devtools-linux', (A, 'stops', 1)), 'quick test')
        r = self.rs(units, units)      # the runs agree: nothing says the page closed
        self.assertNotEqual(cause(r, 'devtools-linux', (A, 'stops', 1)), 'quick test')

    def test_both_sources_missing_is_the_emulator_whatever_each_predicted(self):
        r = self.rs([('links', 0, 'a, link', 'b, link')], [('links', 0, 'a, link', 'c, link')])
        self.assertEqual(cause(r, 'ext-linux', (A, 'links', 0)), 'emulator')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0)), 'emulator')

    def test_devtools_missing_what_the_extension_has_is_conversion_by_field_or_events_by_kind(self):
        r = self.rs([('links', 0, 'a, 2 of 3, link', 'a, 2 of 3, link'), ('links', 1, 'b', 'b'), ('stops', 0, 's', 's'), ('typed', 0, '1', '1')],
                    [('links', 0, 'a, 2 of 3, link', 'a, link'), ('links', 1, 'b', None), ('stops', 0, 's', None), ('typed', 0, '1', None)])
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 0)), 'conversion: position in set')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'links', 1)), 'conversion: node')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'stops', 0)), 'events: focus')
        self.assertEqual(cause(r, 'devtools-linux', (A, 'typed', 0)), 'events: typed')

    def test_the_extension_missing_what_devtools_has_is_a_tree_cause(self):
        r = self.rs([('links', 0, 'a, link', 'a, graphic, link'), ('links', 1, 'b', None)], [('links', 0, 'a, link', 'a, link'), ('links', 1, 'b', 'b')])
        self.assertEqual(cause(r, 'ext-linux', (A, 'links', 0)), 'tree: role')
        self.assertEqual(cause(r, 'ext-linux', (A, 'links', 1)), 'tree: node')

    def test_a_unit_the_other_source_has_no_reading_of_is_not_blamed_on_either(self):
        r = {'ext-linux': reading('ext-linux', [('links', 0, 'a', 'b')]), 'devtools-linux': reading('devtools-linux', [])}
        c, why = cs.attribute(r, 'ext-linux', (A, 'links', 0))
        self.assertEqual(c, 'unexplained'); self.assertIn("'a' -> 'b'", why)
        r = {'ext-linux': reading('ext-linux', [('links', 0, 'a', None)]), 'devtools-linux': reading('devtools-linux', [])}
        self.assertEqual(cause(r, 'ext-linux', (A, 'links', 0)), 'no counterpart')

    def test_macos_differs_from_the_control_by_the_os_and_from_this_host_by_the_runner(self):
        def u(predicted): return [('links', 0, 'a, link', predicted), ('links', 1, 'b', 'b')]
        base = self.rs([('links', 0, 'a, link', 'x, link'), ('links', 1, 'b', 'b')], [('links', 0, 'a, link', 'y, link'), ('links', 1, 'b', 'b')])      # this host: the extension says x, DevTools y, both wrong
        def mac(macos_predicts, control_predicts): return {**base, 'devtools-macos': reading('devtools-macos', u(macos_predicts)), 'devtools-ubuntu-ci': reading('devtools-ubuntu-ci', u(control_predicts))}
        self.assertEqual(cause(mac('m, link', 'y, link'), 'devtools-macos', (A, 'links', 0)), 'macos: name')       # macOS and the control disagree
        self.assertEqual(cause(mac('z, link', 'z, link'), 'devtools-macos', (A, 'links', 0)), 'network/runner')   # they agree, and this host says another thing
        self.assertEqual(cause(mac('z, link', 'z, link'), 'devtools-ubuntu-ci', (A, 'links', 0)), 'network/runner')
        self.assertEqual(cause(mac('y, link', 'y, link'), 'devtools-macos', (A, 'links', 0)), 'emulator')          # the same as this host's DevTools reading: this host's cause, both sources missing it

    def test_a_note_names_a_cause_for_what_the_rules_left_and_only_from_the_list(self):
        r = {'ext-linux': reading('ext-linux', [('links', 0, 'a', 'b')]), 'devtools-linux': reading('devtools-linux', [])}      # nothing from the other source: no rule gives a cause
        notes = [{'reading': '*', 'address': A, 'channel': 'links', 'cause': 'oracle milestone', 'reason': 'Edge 156 names it'}]
        attributed = cs.attribute_all(r, notes)
        self.assertEqual((attributed['ext-linux'][0]['cause'], attributed['ext-linux'][0]['read']), ('oracle milestone', True))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'n.json')
            for bad in ([{'address': A, 'channel': 'links', 'cause': 'a hunch', 'reason': 'x'}], [{'address': A, 'channel': 'links', 'cause': 'emulator', 'reason': ''}]):
                with open(path, 'w') as f: json.dump(bad, f)
                with self.assertRaises(ValueError): cs.load_notes(path)

    def test_a_note_does_not_change_a_cause_a_rule_gave(self):
        r = self.rs([('links', 0, 'a', 'b')], [('links', 0, 'a', 'c')])
        notes = [{'address': A, 'channel': 'links', 'cause': 'oracle milestone', 'reason': 'x'}]
        self.assertEqual(cs.attribute_all(r, notes)['ext-linux'][0]['cause'], 'emulator')

    def test_the_closed_list(self):
        for c in ('emulator', 'conversion: table index', 'events: focus', 'tree: node', 'macos: state', 'unexplained', 'page moved'): self.assertTrue(cs.is_cause(c), c)
        for c in ('conversion', 'conversion table', 'guess', 'extension: name'): self.assertFalse(cs.is_cause(c), c)


class Run(unittest.TestCase):
    def test_every_miss_of_every_reading_is_written_with_a_cause_and_the_recommendation_is_printed(self):
        ext = [('links', i, f'u{i}', f'u{i}') for i in range(6)] + [('links', 6, 'u6', 'x'), ('links', 7, 'u7', None)]
        dev = [('links', i, f'u{i}', f'u{i}') for i in range(4)] + [('links', 4, 'u4', None), ('links', 5, 'u5', 'q'), ('links', 6, 'u6', 'y'), ('links', 7, 'u7', 'u7')]
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as out:
            for name, units in (('ext-linux', ext), ('devtools-linux', dev), ('ext-linux-second', ext), ('devtools-linux-second', dev)):
                rd = reading(name, units)
                os.makedirs(os.path.join(work, name))
                with open(os.path.join(work, name, 'agreement.json'), 'w') as f: json.dump({'status': rd.status, 'rows': [r for r in list(rd.main.values())]}, f)
                with open(os.path.join(work, name, 'agreement.txt'), 'w') as f: f.write('table\n')
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(cs.main(['--work', work, '--out', out]), 0)
            for name in ('ext-linux', 'devtools-linux'):
                with open(os.path.join(out, f'figure-{name}', 'misses.json')) as f: misses = json.load(f)['misses']
                self.assertTrue(misses); self.assertTrue(all(cs.is_cause(m['cause']) for m in misses))
                self.assertTrue(all(m['reason'] for m in misses if m['cause'] == 'unexplained'))
                self.assertTrue(os.path.exists(os.path.join(out, f'figure-{name}', 'agreement.txt')))
            with open(os.path.join(out, 'comparison.txt')) as f: text = f.read()
            self.assertIn('recommendation by the frozen rule (the chairman reads it): KEEP BOTH', text)
            with open(os.path.join(out, 'comparison.json')) as f: self.assertEqual(json.load(f)['extensionBuys']['second']['units'], 8)

    def test_without_both_linux_readings_it_refuses(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as out:
            with self.assertRaises(SystemExit): cs.main(['--work', work, '--out', out])


if __name__ == '__main__': unittest.main()
