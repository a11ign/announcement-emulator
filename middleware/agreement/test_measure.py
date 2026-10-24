"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

The measure of question 5, on records made up for the purpose. Needs NVDA's source (shapes.py reads its vocabularies from it); skipped without it."""
import base64, json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'emu'))
from paths import DOWNLOADS
HAVE = (DOWNLOADS / 'nvda-src' / 'source').is_dir()
if HAVE:
    import measure


def fleet_record(stops=('Home, link', 'Search, edit, blank'), echoed='1 2 3', field='Search, edit, blank', headings=('Tabs, heading, level 1',), title='Tabs GOV dot UK', census=(1, 2), status=200):
    return {'status': status, 'capture': {'structure': {**{c: [] for c in measure.LISTS}, 'headings': list(headings), 'links': ['Home, link', 'About, link']}, 'interaction': {'focusOrder': list(stops), 'typedFeedback': {'typed': True, 'focusBefore': field, 'echoed': echoed}},
            'diagnostics': [{'event': 'documentReady', 'title': title}, {'event': 'structureCensus', 'heading': census[0], 'link': census[1]}]}}


def prediction(stops=('Home, link', 'Search, edit, blank'), typed='123', field='Search, edit, blank', headings=('Tabs, heading, level 1',), title='Tabs GOV.UK', census=(1, 2)):
    speech = [{'cause': 'load', 'text': f'{title}, document | x', 'utterances': [f'{title}, document', 'x']}]
    speech += [{'cause': 'focus', 'text': s, 'repeatFocus': s} for s in stops]
    speech += [{'cause': 'focus', 'text': field, 'repeatFocus': field}]
    speech += [{'cause': 'typed', 'text': c} for c in typed]
    return {'predictedSpeech': speech, 'sweeps': [{'trigger': 'load', 'lists': {'headings': list(headings), 'links': ['Home, link', 'About, link']}, 'census': {'heading': census[0], 'link': census[1]}}]}


@unittest.skipUnless(HAVE, "needs NVDA's source (setup.sh)")
class Measure(unittest.TestCase):
    def test_one_missing_element_costs_one_miss_and_not_every_one_after_it(self):
        rows = measure.compare('links', ['a, link', 'b, link', 'c, link'], ['a, link', 'c, link'])
        self.assertEqual([r['ok'] for r in rows], [True, False, True])

    def test_a_replaced_element_shows_what_stood_in_its_place(self):
        rows = measure.compare('links', ['a, link', 'b, visited, link'], ['a, link', 'b, link'])
        self.assertEqual((rows[1]['ok'], rows[1]['predicted']), (False, 'b, link'))
        self.assertEqual(measure.classify(rows[1]), 'history')

    def test_the_shape_is_the_fleets_shape_of_the_oracles_unit(self):
        self.assertEqual(measure.compare('stops', ['Save, button'], ['Save, button'])[0]['shape'], ['NAME', 'ROLE'])

    def test_the_spoken_title_and_the_pages_are_one_title(self):
        self.assertEqual(measure.norm('GOV dot UK Design System'), measure.norm('GOV.UK Design System'))

    def test_the_causes_of_a_miss(self):
        row = lambda e, p: {'expected': e, 'predicted': p}      # noqa: E731
        self.assertEqual(measure.classify(row('x, link', None)), 'no counterpart')
        self.assertEqual(measure.classify(row('To get missing image descriptions, graphic', 'y')), 'prompt')
        self.assertEqual(measure.classify(row('English, x, link', 'x, link')), 'language')
        self.assertEqual(measure.classify(row('x, link', 'z, link')), 'unexplained')

    def test_a_capture_that_failed_gives_no_oracle(self):
        self.assertIsNone(measure.fleet_channels(fleet_record(status=500)))
        self.assertIsNone(measure.fleet_channels({'status': 200, 'capture': {'error': 'x'}}))

    def test_the_fleets_lists_and_the_predictions_are_read_into_the_same_channels(self):
        f = measure.fleet_channels(fleet_record())
        p, census = measure.passive_channels(prediction())
        self.assertEqual(f['typed'], ['1', '2', '3']); self.assertEqual(p['typed'], ['1', '2', '3'])
        self.assertEqual(p['stops'], ['Home, link', 'Search, edit, blank']); self.assertEqual(p['field'], ['Search, edit, blank'])
        self.assertEqual(p['title'], ['Tabs GOV.UK']); self.assertEqual(census, {'heading': 1, 'link': 2})

    def test_a_walk_with_no_typing_has_no_field_and_all_its_focus_moves_are_stops(self):
        p, _ = measure.passive_channels({'predictedSpeech': [{'cause': 'focus', 'text': 'a', 'repeatFocus': 'a'}, {'cause': 'focus', 'text': 'b', 'repeatFocus': 'b'}], 'sweeps': []})
        self.assertEqual((p['stops'], p['field']), (['a', 'b'], []))

    def test_a_page_both_sides_read_alike_agrees_in_every_unit(self):
        a = 'https://x.test/p'
        rows, status = measure.measure([a], {measure.slug(a): [fleet_record(), fleet_record()]}, [{a: prediction()}, {a: prediction()}])
        self.assertEqual(status[a]['status'], 'comparable')
        main = [r for r in rows if r['kind'] == 'fleet-vs-passive']
        self.assertTrue(main and all(r['ok'] for r in main), [r for r in main if not r['ok']])

    def test_a_stop_the_prediction_has_not_got_is_a_miss_and_is_attributed(self):
        a = 'https://x.test/p'
        rows, _ = measure.measure([a], {measure.slug(a): [fleet_record(), fleet_record()]}, [{a: prediction(stops=('Home, link',))}, {a: prediction(stops=('Home, link',))}])
        misses = [r for r in rows if r['kind'] == 'fleet-vs-passive' and not r['ok']]
        self.assertEqual([(r['channel'], r['expected']) for r in misses], [('stops', 'Search, edit, blank')])
        self.assertEqual(misses[0]['class'], 'no counterpart')

    def test_a_page_whose_fleet_readings_differ_is_not_compared_in_that_channel(self):
        a = 'https://x.test/p'
        rows, status = measure.measure([a], {measure.slug(a): [fleet_record(), fleet_record(stops=('Other, link',))]}, [{a: prediction()}, {a: prediction()}])
        self.assertEqual([u['channel'] for u in status[a]['unstable']], ['stops'])
        self.assertFalse([r for r in rows if r['channel'] == 'stops'])

    def test_with_the_flag_a_channel_that_was_not_stable_is_compared_and_marked(self):
        a = 'https://x.test/p'
        args = ([a], {measure.slug(a): [fleet_record(), fleet_record(stops=('Other, link',))]}, [{a: prediction()}, {a: prediction()}])
        rows, _ = measure.measure(*args, include_unstable=True)
        stops = [r for r in rows if r['channel'] == 'stops' and r['kind'] == 'fleet-vs-passive']
        self.assertTrue(stops and not any(r['stable'] for r in stops))
        self.assertNotIn('stops', ' '.join(l for l in measure.report(rows, {a: {'status': 'comparable', 'unstable': []}}).splitlines() if 'stops' in l and ' / ' in l))

    def test_a_page_that_was_not_the_same_page_is_not_compared_at_all(self):
        a = 'https://x.test/p'
        rows, status = measure.measure([a], {measure.slug(a): [fleet_record(census=(9, 2)), fleet_record(census=(9, 2))]}, [{a: prediction()}, {a: prediction()}])
        self.assertEqual(status[a]['status'], 'not comparable'); self.assertEqual(rows, [])
        _, status = measure.measure([a], {measure.slug(a): [fleet_record(title='Something else entirely'), None]}, [{a: prediction()}])
        self.assertEqual(status[a]['status'], 'not comparable')

    def test_a_page_the_middleware_predicted_nothing_for_is_listed_and_not_counted_as_a_miss(self):
        a = 'https://x.test/p'
        rows, status = measure.measure([a], {measure.slug(a): [fleet_record(), fleet_record()]}, [{a: {'predictedSpeech': [], 'sweeps': []}}])
        self.assertEqual(status[a]['status'], 'no passive reading'); self.assertEqual(rows, [])

    def test_with_the_flag_a_page_whose_counts_differ_but_whose_title_is_the_same_is_compared(self):
        a = 'https://x.test/p'
        args = ([a], {measure.slug(a): [fleet_record(census=(9, 2)), fleet_record(census=(9, 2))]}, [{a: prediction()}, {a: prediction()}])
        self.assertEqual(measure.measure(*args)[1][a]['status'], 'not comparable')
        rows, status = measure.measure(*args, tolerate_census=True)
        self.assertEqual(status[a]['status'], 'comparable'); self.assertTrue(rows)

    def test_a_page_with_no_fleet_reading_is_listed(self):
        a = 'https://x.test/p'
        self.assertEqual(measure.measure([a], {}, [{a: prediction()}])[1][a]['status'], 'no fleet reading')

    def test_the_predictions_are_read_from_the_attachments_of_a_playwright_report(self):
        a = 'https://x.test/p'
        report = {'suites': [{'suites': [{'specs': [{'title': f'keyboard walk of {a}', 'tests': [{'results': [{'attachments': [
            {'name': 'predicted-nvda-speech.json', 'contentType': 'application/json', 'body': base64.b64encode(json.dumps(prediction()).encode()).decode()}]}]}]}]}]}]}
        self.assertEqual(list(measure.passive_predictions(report)), [a])

    def test_the_report_has_the_tables_and_nothing_named_for_evidence(self):
        a = 'https://x.test/p'
        rows, status = measure.measure([a], {measure.slug(a): [fleet_record(), fleet_record()]}, [{a: prediction()}, {a: prediction()}])
        text = measure.report(rows, status)
        for needle in ('agreement by channel', 'agreement by shape', 'all channels: ', 'misses by cause'): self.assertIn(needle, text)

    def test_runs_that_mix_tree_sources_are_refused_and_one_source_is_named(self):
        ext, dev = {'a': {**prediction(), 'treeSource': 'extension'}}, {'a': {**prediction(), 'treeSource': 'devtools'}}
        self.assertEqual(measure.tree_source_of([ext, ext]), 'extension')
        self.assertIsNone(measure.tree_source_of([{}, {}]))
        with self.assertRaisesRegex(ValueError, 'mix tree sources'): measure.tree_source_of([ext, dev])
        with self.assertRaisesRegex(ValueError, 'mix tree sources'): measure.tree_source_of([{'a': {**prediction(), 'treeSource': 'extension'}, 'b': {**prediction(), 'treeSource': 'devtools'}}])

    def test_the_second_reading_puts_the_second_capture_against_the_second_run(self):
        a = 'https://x.test/p'
        good, other = fleet_record(), fleet_record(stops=('Home, link', 'Search, edit, blank', 'Extra, link'))
        fleet, runs = measure.second_reading({measure.slug(a): [good, other]}, [{a: prediction()}, {a: prediction(stops=('Home, link', 'Search, edit, blank', 'Extra, link'))}])
        self.assertEqual(fleet[measure.slug(a)], [other, good])
        rows, _ = measure.measure([a], fleet, runs)
        self.assertTrue(all(r['ok'] for r in rows if r['kind'] == 'fleet-vs-passive' and r['channel'] == 'stops'))


if __name__ == '__main__': unittest.main()
