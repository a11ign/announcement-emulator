"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_sources as cs
import round as rnd

TFL = 'https://tfl.gov.uk/plan-a-journey/'
GOV = 'https://design-system.service.gov.uk/components/tabs/'


def row(address, channel, i, expected, predicted, kind='fleet-vs-passive', shape=('NAME', 'ROLE'), klass=None):
    ok = expected == predicted
    return {'address': address, 'kind': kind, 'stable': True, 'channel': channel, 'i': i, 'expected': expected, 'predicted': predicted, 'ok': ok, 'shape': list(shape),
            'class': 'agree' if ok else klass or ('no counterpart' if predicted is None else 'unexplained')}


def agreement(rows, pages=(GOV,)):
    return {'status': {a: {'status': 'comparable', 'unstable': []} for a in pages}, 'rows': rows}


def reading(rows, pages=(GOV,)): return cs.Reading('r', agreement(rows, pages))


def write(root, name, rows, pages=(GOV,)):
    os.makedirs(root + '/' + name, exist_ok=True)
    with open(f'{root}/{name}/agreement.json', 'w') as f: json.dump(agreement(rows, pages), f)
    with open(f'{root}/{name}/agreement.txt', 'w') as f: f.write('all channels: 1 of 2 units agreed = 50.0%\n')


class Interval(unittest.TestCase):
    def test_the_upper_bound_of_the_wilson_interval(self):
        self.assertAlmostEqual(rnd.wilson_upper(50, 100), 0.5962, places=3)
        self.assertAlmostEqual(rnd.wilson_upper(0, 3), 0.5615, places=3)
        self.assertEqual(rnd.wilson_upper(10, 10), 1.0)
        self.assertEqual(rnd.wilson_upper(0, 0), 1.0)

    def test_a_shape_is_low_confidence_when_the_interval_is_below_the_overall_rate_and_a_miss_is_the_middlewares(self):
        self.assertTrue(rnd.low_confidence(40, 80, 0.8, ['emulator'] * 40))

    def test_a_weak_shape_whose_misses_are_all_the_oracles_is_not_low_confidence(self):
        for cause in rnd.ORACLE_CAUSES: self.assertFalse(rnd.low_confidence(40, 80, 0.8, [cause] * 40), cause)

    def test_one_miss_of_the_middlewares_among_the_oracles_is_enough(self):
        self.assertTrue(rnd.low_confidence(40, 80, 0.8, ['page moved'] * 39 + ['unexplained']))

    def test_a_shape_with_few_units_has_a_wide_interval_and_is_not_flagged_on_noise(self):
        self.assertFalse(rnd.low_confidence(3, 4, 0.8, ['emulator']))      # 75%, below 80%, but the interval reaches 99%
        self.assertTrue(rnd.low_confidence(30, 40, 0.9, ['emulator'] * 10))

    def test_a_shape_that_agrees_as_much_as_the_whole_is_not_flagged_even_with_misses(self):
        self.assertFalse(rnd.low_confidence(790, 1000, 0.78, ['emulator'] * 210))

    def test_a_shape_with_no_miss_is_not_flagged(self):
        self.assertFalse(rnd.low_confidence(0, 0, 0.8, []))
        self.assertFalse(rnd.low_confidence(90, 90, 0.99, []))


class Printed(unittest.TestCase):
    def test_the_rate_is_the_one_agreement_txt_prints(self):
        self.assertEqual(rnd.printed(871, 1072), 0.812)      # 81.25% prints 81.2%
        self.assertEqual(rnd.printed(1022, 1072), 0.953)
        self.assertEqual(rnd.printed(1, 1), 1.0)


class Blocked(unittest.TestCase):
    def report(self, *statuses):
        return {'suites': [{'suites': [], 'specs': [{'title': f'keyboard walk of {a}', 'tests': [{'results': [{'status': s}]}]} for a, s in statuses]}]}

    def test_a_corpus_test_that_did_not_finish_is_listed_and_one_that_passed_is_not(self):
        r = self.report((GOV, 'passed'), (TFL, 'timedOut'))
        self.assertEqual(rnd.unfinished(r), [TFL])
        self.assertEqual(rnd.unfinished(self.report((GOV, 'passed'))), [])
        self.assertEqual(rnd.unfinished(self.report((GOV, 'failed'))), [GOV])

    def test_the_last_attempt_of_a_test_decides(self):
        r = {'suites': [{'specs': [{'title': f'keyboard walk of {TFL}', 'tests': [{'results': [{'status': 'timedOut'}, {'status': 'passed'}]}]}]}]}
        self.assertEqual(rnd.unfinished(r), [])

    def test_a_test_that_never_started_did_not_finish(self):
        r = {'suites': [{'specs': [{'title': f'keyboard walk of {TFL}', 'tests': [{'results': []}]}]}]}
        self.assertEqual(rnd.unfinished(r), [TFL])

    def test_other_tests_are_not_the_corpus(self):
        r = {'suites': [{'specs': [{'title': 'a fixture', 'tests': [{'results': [{'status': 'failed'}]}]}]}]}
        self.assertEqual(rnd.unfinished(r), [])


class Retag(unittest.TestCase):
    def miss(self, **kw): return {'address': TFL, 'channel': 'typed', 'i': 0, 'expected': '1', 'predicted': None, 'cause': 'no counterpart', 'reason': '', 'shape': ['NAME'], **kw}

    def test_nothing_typed_by_a_test_that_did_not_finish_is_test_blocked(self):
        m = rnd.retag(self.miss(), 'devtools-linux', {TFL})
        self.assertEqual(m['cause'], 'test blocked')
        self.assertIn('did not finish', m['reason'])

    def test_it_applies_to_the_field_channel_too(self):
        self.assertEqual(rnd.retag(self.miss(channel='field'), 'ext-linux', {TFL})['cause'], 'test blocked')

    def test_a_page_whose_test_finished_keeps_its_cause(self):
        self.assertEqual(rnd.retag(self.miss(), 'devtools-linux', set())['cause'], 'no counterpart')
        self.assertEqual(rnd.retag(self.miss(address=GOV), 'devtools-linux', {TFL})['cause'], 'no counterpart')

    def test_a_stop_of_a_page_whose_test_did_not_finish_keeps_its_cause(self):
        self.assertEqual(rnd.retag(self.miss(channel='stops'), 'devtools-linux', {TFL})['cause'], 'no counterpart')

    def test_a_typed_unit_with_a_prediction_keeps_its_cause(self):
        self.assertEqual(rnd.retag(self.miss(predicted='2', cause='unexplained'), 'devtools-linux', {TFL})['cause'], 'unexplained')

    def test_the_extensions_frame_that_only_devtools_has_is_an_offscreen_frame(self):
        m = self.miss(channel='frames', address=GOV, predicted='x', cause='tree: node', reason='DevTools agrees')
        self.assertEqual(rnd.retag(m, 'ext-linux', set())['cause'], 'offscreen frame')
        self.assertEqual(rnd.retag(m, 'devtools-linux', set())['cause'], 'tree: node')
        self.assertEqual(rnd.retag({**m, 'channel': 'links'}, 'ext-linux', set())['cause'], 'tree: node')

    def test_both_new_causes_are_in_the_closed_list_and_an_invented_one_is_not(self):
        for c in ('test blocked', 'offscreen frame', 'chromium build', 'page moved', 'conversion: name', 'macos: state'): self.assertTrue(rnd.is_closed(c), c)
        for c in ('bad luck', 'conversion', 'oracle'): self.assertFalse(rnd.is_closed(c), c)


class Rates(unittest.TestCase):
    def rows(self):
        main = [row(GOV, 'stops', 0, 'a', 'a'), row(GOV, 'stops', 1, 'b', 'b'), row(GOV, 'headings', 0, 'h 1', 'h 2', shape=('NAME', 'ROLE', 'LEVEL')), row(GOV, 'headings', 1, 'h 3', 'h 3', shape=('NAME', 'ROLE', 'LEVEL'))]
        fleet = [row(GOV, 'stops', 0, 'a', 'a', 'fleet-vs-fleet'), row(GOV, 'stops', 1, 'b', 'x', 'fleet-vs-fleet'), row(GOV, 'headings', 0, 'h 1', 'h 1', 'fleet-vs-fleet', ('NAME', 'ROLE', 'LEVEL')),
                 row(GOV, 'headings', 1, 'h 3', 'h 3', 'fleet-vs-fleet', ('NAME', 'ROLE', 'LEVEL'))]
        return main + fleet

    def test_the_figure_the_ceiling_and_each_shape_are_counted_from_the_same_units(self):
        rd = reading(self.rows())
        misses = [{'shape': ['NAME', 'ROLE', 'LEVEL'], 'cause': 'emulator'}]
        r = rnd.rates_of(rd, misses, True)
        self.assertEqual((r['headline'], r['ceiling'], r['pages'], r['heldOut']), ({'agreed': 3, 'units': 4}, {'agreed': 3, 'units': 4}, 1, True))
        self.assertEqual(r['shapes']['NAME + ROLE'], {'agreed': 2, 'units': 2, 'ceiling': {'agreed': 1, 'units': 2}, 'misses': {}, 'lowConfidence': False})
        self.assertEqual(r['shapes']['NAME + ROLE + LEVEL']['misses'], {'emulator': 1})
        self.assertEqual(sum(s['units'] for s in r['shapes'].values()), r['headline']['units'])
        self.assertEqual(sum(s['agreed'] for s in r['shapes'].values()), r['headline']['agreed'])
        self.assertEqual(r['byChannel']['stops'], {'agreed': 2, 'units': 2, 'ceiling': {'agreed': 1, 'units': 2}})
        self.assertEqual(r['causes'], {'emulator': 1})

    def test_the_shapes_are_in_the_order_of_their_units(self):
        r = rnd.rates_of(reading(self.rows() + [row(GOV, 'links', i, 'l', 'l', shape=('NAME', 'ROLE', 'STATE')) for i in range(5)]), [], False)
        self.assertEqual(next(iter(r['shapes'])), 'NAME + ROLE + STATE')
        self.assertFalse(r['heldOut'])

    def test_the_list_entry_is_what_the_report_reads(self):
        r = rnd.rates_of(reading(self.rows()), [{'shape': ['NAME', 'ROLE', 'LEVEL'], 'cause': 'emulator'}], True)
        e = rnd.list_entry(r, '2026-10-26', 'middleware/results/agreement-round-1/held-out/156.0.8078.4/extension-linux/')
        self.assertEqual((e['agreement'], e['units'], e['date']), (0.75, 4, '2026-10-26'))
        self.assertEqual(e['population'], {'pages': 1, 'heldOut': True, 'units': 4})
        self.assertEqual(e['ceiling'], {'agreement': 0.75, 'units': 4})
        self.assertEqual(e['shapes']['NAME + ROLE'], {'agreement': 1.0, 'units': 2, 'lowConfidence': False})
        self.assertEqual(set(e['shapes']), {'NAME + ROLE', 'NAME + ROLE + LEVEL'})


class List(unittest.TestCase):
    def listing(self):
        return {'builds': [{'chromium': '156.0.8078.4', 'playwright': ['1.64.1'], 'measured': {'extension-linux': {'agreement': 0.8, 'units': 10, 'date': 'd', 'figure': 'old'}, 'devtools-macos': {'agreement': 0.7, 'units': 5, 'date': 'd', 'figure': 'm'}}},
                           {'chromium': '153.0.8010.12', 'playwright': ['1.63.0'], 'measured': {'extension-linux': {'agreement': 0.6, 'units': 10, 'date': 'd', 'figure': 'o153'}}}]}

    def test_a_measured_reading_is_replaced_and_every_other_is_left(self):
        out = rnd.fill_list(self.listing(), {'156.0.8078.4': {'extension-linux': {'agreement': 0.9, 'units': 20, 'date': 'n', 'figure': 'new'}}})
        b156, b153 = out['builds']
        self.assertEqual(b156['measured']['extension-linux']['figure'], 'new')
        self.assertEqual(b156['measured']['devtools-macos']['figure'], 'm')
        self.assertEqual(b153, self.listing()['builds'][1])
        self.assertEqual(b156['playwright'], ['1.64.1'])

    def test_a_build_the_list_does_not_name_is_refused(self):
        with self.assertRaises(ValueError): rnd.fill_list(self.listing(), {'150.0.0.1': {}})

    def test_the_input_is_not_changed(self):
        before = self.listing()
        rnd.fill_list(before, {'156.0.8078.4': {'extension-linux': {}}})
        self.assertEqual(before, self.listing())


class Refusals(unittest.TestCase):
    """A round that is missing something it needs is refused, and the list is left as it was."""

    def test_a_figure_with_no_ceiling_is_refused_and_does_not_divide_by_zero(self):
        r = rnd.rates_of(reading([row(GOV, 'stops', 0, 'a', 'a')]), [], True)
        self.assertEqual(r['ceiling']['units'], 0)
        with self.assertRaises(ValueError): rnd.list_entry(r, '2026-10-26', 'x')

    def test_a_unit_whose_words_have_no_shape_is_not_a_shape_of_the_list(self):
        rows = [row(GOV, 'stops', 0, 'a', 'a'), row(GOV, 'stops', 0, 'a', 'a', 'fleet-vs-fleet'), row(GOV, 'stops', 1, ',', ',', shape=()), row(GOV, 'stops', 1, ',', ',', 'fleet-vs-fleet', shape=())]
        e = rnd.list_entry(rnd.rates_of(reading(rows), [], True), '2026-10-26', 'x')
        self.assertEqual(list(e['shapes']), ['NAME + ROLE'])

    def test_a_refused_list_is_not_truncated(self):
        with tempfile.TemporaryDirectory() as root:
            listing = root + '/list.json'
            text = json.dumps({'builds': [{'chromium': '156.0.8078.4', 'playwright': ['1.64.1'], 'measured': {}}]})
            with open(listing, 'w') as f: f.write(text)
            rates = rnd.rates_of(reading([row(GOV, 'stops', 0, 'a', 'a'), row(GOV, 'stops', 0, 'a', 'a', 'fleet-vs-fleet')]), [], True)
            with self.assertRaises(ValueError): rnd.update_list(listing, {'held-out': {'150.0.0.1': {'extension-linux': rates}}}, {'150.0.0.1': '2026-10-26'})
            with open(listing) as f: self.assertEqual(f.read(), text)

    def test_a_reading_without_its_blocked_file_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(root + '/b/ext-linux')
            with self.assertRaises(FileNotFoundError): rnd.read_blocked(root, 'b', 'ext-linux')

    def test_a_reading_without_its_second_reading_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ('ext-linux', 'devtools-linux'): write(root + '/held-out/156.0.8078.4', name, [row(GOV, 'stops', 0, 'a', 'a')])
            with self.assertRaises(ValueError): rnd.attribute_set(root + '/held-out')

    def test_a_ceiling_over_other_units_than_the_figure_is_said_in_the_text(self):
        r = rnd.rates_of(reading([row(GOV, 'stops', 0, 'a', 'a'), row(GOV, 'stops', 1, 'b', 'b'), row(GOV, 'stops', 0, 'a', 'a', 'fleet-vs-fleet')]), [], True)
        self.assertIn('NOTE the ceiling is over 1 units and the figure over 2', rnd.render_reading('extension-linux', r, None))


class Previous(unittest.TestCase):
    def test_the_headline_and_the_shapes_are_read_from_a_committed_figure(self):
        path = os.path.join(HERE, '..', 'results', 'playwright-versions', '156.0.8078.4', 'extension-linux', 'agreement.txt')
        with open(path) as f: agreed, units, shapes = rnd.parse_figure(f.read())
        self.assertEqual((agreed, units), (871, 1072))
        self.assertEqual(shapes['NAME + ROLE'], (265, 275))
        self.assertEqual(shapes['NAME + ROLE + STATE + STATE + POSITION'], (3, 35))
        self.assertEqual(len(shapes), 10)

    def test_the_movement_is_up_down_or_within_the_run_to_run_band(self):
        self.assertEqual(rnd.movement((800, 1000), (810, 1000)), 'up')
        self.assertEqual(rnd.movement((800, 1000), (790, 1000)), 'down')
        self.assertEqual(rnd.movement((800, 1000), (806, 1000)), 'within')      # exactly 0.6 points
        self.assertEqual(rnd.movement((800, 1000), (807, 1000)), 'up')
        self.assertEqual(rnd.movement((0, 0), (1, 1)), 'not compared')


class Whole(unittest.TestCase):
    """The held-out set and the fitted set of one build, two readings each, through `report`."""

    def build(self, root, set_name, blocked=()):
        d = f'{root}/{set_name}/156.0.8078.4'
        typed = [row(TFL, 'typed', 0, '1', None, shape=('NAME',)), row(TFL, 'typed', 1, '2', None, shape=('NAME',))]
        stops = [row(GOV, 'stops', 0, 'a', 'a'), row(GOV, 'stops', 1, 'b', 'c', klass='unexplained')]
        fleet = [row(a, c, i, e, e, 'fleet-vs-fleet') for a, c, i, e in [(TFL, 'typed', 0, '1'), (TFL, 'typed', 1, '2'), (GOV, 'stops', 0, 'a'), (GOV, 'stops', 1, 'b')]]
        for name in ('ext-linux', 'devtools-linux'):
            write(d, name, typed + stops + fleet, pages=(TFL, GOV))
            write(d, name + '-second', typed + stops + fleet, pages=(TFL, GOV))
            with open(f'{d}/{name}/blocked.json', 'w') as f: json.dump(list(blocked), f)

    def test_every_miss_has_one_cause_of_the_closed_list_and_the_typed_units_of_a_blocked_page_are_test_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root + '/work', 'held-out', blocked=[TFL])
            text, all_rates = rnd.report(root + '/work', root + '/out')
            r = all_rates['held-out']['156.0.8078.4']['extension-linux']
            self.assertEqual(r['causes'].get('test blocked'), 2)
            with open(f'{root}/out/held-out/156.0.8078.4/extension-linux/misses.json') as f: misses = json.load(f)['misses']
            self.assertEqual(len(misses), 3)
            self.assertTrue(all(rnd.is_closed(m['cause']) for m in misses))
            self.assertEqual({m['cause'] for m in misses if m['channel'] == 'typed'}, {'test blocked'})
            self.assertIn('held-out pages (chosen and frozen before they were read)', text)

    def test_the_directory_of_a_figure_has_the_agreement_the_misses_and_the_rates(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root + '/work', 'held-out')
            rnd.report(root + '/work', root + '/out')
            self.assertEqual(sorted(os.listdir(f'{root}/out/held-out/156.0.8078.4/devtools-linux')), ['agreement.txt', 'misses.json', 'rates.json'])

    def test_the_fitted_set_is_labelled_not_held_out_and_its_rates_say_so(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root + '/work', 'fitted')
            text, all_rates = rnd.report(root + '/work', root + '/out')
            self.assertFalse(all_rates['fitted']['156.0.8078.4']['devtools-linux']['heldOut'])
            self.assertIn('NOT held out', text)
            self.assertNotIn('held-out', all_rates)

    def test_only_the_held_out_figures_fill_the_list(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root + '/work', 'held-out')
            self.build(root + '/work', 'fitted')
            _, all_rates = rnd.report(root + '/work', root + '/out')
            listing = root + '/list.json'
            with open(listing, 'w') as f: json.dump({'builds': [{'chromium': '156.0.8078.4', 'playwright': ['1.64.1'], 'measured': {}}]}, f)
            rnd.update_list(listing, all_rates, {'156.0.8078.4': '2026-10-26'})
            with open(listing) as f: got = json.load(f)['builds'][0]['measured']
            self.assertEqual(sorted(got), ['devtools-linux'])      # the control and macOS (no reading here) are not listed, and neither is the extension's reading, which A11-229 removed: the list's schema has no key for it
            e = got['devtools-linux']
            self.assertEqual(e['figure'], 'middleware/results/agreement-round-1/held-out/156.0.8078.4/devtools-linux/')
            self.assertTrue(e['population']['heldOut'])
            self.assertEqual(e['date'], '2026-10-26')

    def test_the_comparison_with_the_previous_figures_says_up_down_or_within(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root + '/work', 'fitted')
            prev = root + '/prev/156.0.8078.4/extension-linux'
            os.makedirs(prev)
            with open(prev + '/agreement.txt', 'w') as f:
                f.write('all channels: 1 of 5 units agreed = 20.0%\nagreement by shape (the 10 commonest)\n    1 / 5    20.0% |    5 / 5   100.0% |    5 / 5   100.0%  NAME + ROLE\n')
            text, _ = rnd.report(root + '/work', root + '/out', previous=root + '/prev')
            self.assertIn('against the previous figure (1 of 5 = 20.0%)', text)
            self.assertIn('up', text)


if __name__ == '__main__': unittest.main()
