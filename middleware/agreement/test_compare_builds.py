"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

The rule of middleware/results/playwright-versions/rule.md applied to readings made up for the purpose: the cause that is a difference between the builds, that every miss still ends with one cause, and the list the
measurement fills."""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_builds as cb
import compare_sources as cs
from test_compare_sources import reading

NEW, OLD = '156.0.8078.4', '153.0.8010.12'


def pair(units_new, units_old, second_new=None, second_old=None):
    """builds and second readings for ext-linux and devtools-linux, the same units in both sources, so that no other cause can apply."""
    mk = lambda name, units: reading(name, units)      # noqa: E731
    builds = {NEW: {'ext-linux': mk('ext-linux', units_new), 'devtools-linux': mk('devtools-linux', units_new)}, OLD: {'ext-linux': mk('ext-linux', units_old), 'devtools-linux': mk('devtools-linux', units_old)}}
    second = {NEW: {n: mk(n, second_new or units_new) for n in builds[NEW]}, OLD: {n: mk(n, second_old or units_old) for n in builds[OLD]}}
    return builds, second


def causes(attributed, build, name): return [m['cause'] for m in attributed[build][name]]


class ChromiumBuild(unittest.TestCase):
    def test_a_unit_the_builds_predict_differently_and_each_predicts_steadily_is_the_builds(self):
        builds, second = pair([('links', 0, 'a, link', 'a, link')], [('links', 0, 'a, link', 'x, link')])
        attributed = cb.attribute_builds(builds, second)
        self.assertEqual(causes(attributed, OLD, 'ext-linux'), ['chromium build'])
        self.assertIn("Chromium 153.0.8010.12 predicted 'x, link'", attributed[OLD]['ext-linux'][0]['reason'])
        self.assertIn('Chromium 156.0.8078.4 predicted', attributed[OLD]['ext-linux'][0]['reason'])
        self.assertEqual(causes(attributed, NEW, 'ext-linux'), [])      # the build that agrees has no miss

    def test_a_build_that_changed_its_own_prediction_between_its_runs_is_noise_and_not_the_build(self):
        builds, second = pair([('links', 0, 'a, link', 'a, link')], [('links', 0, 'a, link', 'x, link')], second_old=[('links', 0, 'a, link', 'y, link')])
        self.assertNotIn('chromium build', causes(cb.attribute_builds(builds, second), OLD, 'ext-linux'))

    def test_a_unit_both_builds_predict_the_same_way_is_not_the_builds(self):
        builds, second = pair([('links', 0, 'a, link', 'b, link')], [('links', 0, 'a, link', 'b, link')])
        attributed = cb.attribute_builds(builds, second)
        self.assertEqual(causes(attributed, NEW, 'ext-linux'), ['emulator'])
        self.assertEqual(causes(attributed, OLD, 'ext-linux'), ['emulator'])

    def test_a_unit_only_one_build_compares_is_not_the_builds(self):
        builds, second = pair([('links', 0, 'a, link', 'a, link')], [('links', 1, 'a, link', 'x, link')])
        self.assertNotIn('chromium build', causes(cb.attribute_builds(builds, second), OLD, 'ext-linux'))

    def test_the_causes_before_it_in_the_rule_still_come_first(self):
        # 'a, link' against 'a, visited, link' is a history difference (measure.py's own class): that cause is named before the builds are looked at
        builds, second = pair([('links', 0, 'a, link', 'a, link')], [('links', 0, 'a, link', 'a, visited, link')])
        attributed = cb.attribute_builds(builds, second)
        self.assertEqual(causes(attributed, OLD, 'ext-linux'), ['history'])

    def test_every_miss_ends_with_one_cause_of_the_closed_list(self):
        builds, second = pair([('links', 0, 'a, link', 'b, link'), ('links', 1, 'c, link', 'c, link')], [('links', 0, 'a, link', 'z, link'), ('links', 1, 'c, link', None)])
        attributed = cb.attribute_builds(builds, second)
        for build in attributed.values():
            for ms in build.values():
                for m in ms: self.assertTrue(cs.is_cause(m['cause']) or m['cause'] == 'chromium build', m['cause'])
        self.assertEqual(sum(len(ms) for b in attributed.values() for ms in b.values()), 2 * 1 + 2 * 2)      # NEW: one miss each source; OLD: two misses each source


class Between(unittest.TestCase):
    def test_how_far_the_builds_differ_whatever_the_oracle_says(self):
        builds, _ = pair([('links', 0, 'a', 'a'), ('links', 1, 'b', 'b')], [('links', 0, 'a', 'x'), ('links', 1, 'b', 'b')])
        d = cb.differ_between_builds(builds)['ext-linux']
        self.assertEqual((d['units'], d['predictionsDiffer'], d['agreeInOneOnly']), (2, 1, 1))


class FillList(unittest.TestCase):
    def test_each_build_gets_its_figures_the_newest_first_and_the_control_is_never_listed(self):
        figures = {OLD: {'extension-linux': (80, 100, f'middleware/results/playwright-versions/{OLD}/extension-linux/')},
                   NEW: {'extension-linux': (86, 100, 'p/ext/'), 'devtools-linux': (84, 100, 'p/dev/'), 'devtools-macos': (1, 3, 'p/mac/'), 'devtools-ubuntu-ci': (99, 100, 'p/ci/')}}
        listing = cb.fill_list({'builds': []}, figures, {NEW: '2026-10-25', OLD: '2026-10-25'}, {NEW: ['1.64.0', '1.64.1'], OLD: ['1.63.0']})
        self.assertEqual([b['chromium'] for b in listing['builds']], [NEW, OLD])
        self.assertEqual(listing['builds'][0]['playwright'], ['1.64.0', '1.64.1'])
        self.assertEqual(sorted(listing['builds'][0]['measured']), ['devtools-linux', 'devtools-macos', 'extension-linux'])
        self.assertEqual(listing['builds'][0]['measured']['extension-linux'], {'agreement': 0.86, 'units': 100, 'date': '2026-10-25', 'figure': 'p/ext/'})
        self.assertEqual(listing['builds'][0]['measured']['devtools-macos']['agreement'], 0.333)
        self.assertEqual(cb.fill_list({'builds': []}, {NEW: {'extension-linux': (871, 1072, 'p/')}}, {NEW: 'd'}, {NEW: ['1']})['builds'][0]['measured']['extension-linux']['agreement'], 0.812)      # 81.25%: agreement.txt prints 81.2

    def test_a_build_already_listed_is_replaced_and_one_not_measured_now_is_kept(self):
        before = {'builds': [{'chromium': NEW, 'playwright': ['1.64.1'], 'measured': {}}, {'chromium': '150.0.1.1', 'playwright': ['1.60.0'], 'measured': {}}]}
        listing = cb.fill_list(before, {NEW: {'extension-linux': (1, 2, 'p/')}}, {NEW: '2026-10-25'}, {NEW: ['1.64.1']})
        self.assertEqual([b['chromium'] for b in listing['builds']], [NEW, '150.0.1.1'])
        self.assertEqual(listing['builds'][0]['measured']['extension-linux']['agreement'], 0.5)


class Main(unittest.TestCase):
    def test_the_figures_the_list_and_the_comparison_are_written(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as out:
            builds, second = pair([('links', 0, 'a', 'a'), ('links', 1, 'b', 'x')], [('links', 0, 'a', 'a'), ('links', 1, 'b', 'b')])
            rows = lambda r: {'status': r.status, 'rows': [dict(x) for x in [*r.main.values(), *r.fleet.values()]]}      # noqa: E731
            for build in builds:
                for group in (builds, second):
                    for name, r in group[build].items():
                        d = os.path.join(work, build, name + ('-second' if group is second else '')); os.makedirs(d)
                        with open(os.path.join(d, 'agreement.json'), 'w') as f: json.dump(rows(r), f)
                        with open(os.path.join(d, 'agreement.txt'), 'w') as f: f.write('all channels: made up\n')
            listing = os.path.join(out, 'supported-versions.json')
            with open(listing, 'w') as f: json.dump({'builds': []}, f)
            self.assertEqual(cb.main(['--work', work, '--out', out, '--list', listing, '--dates', f'{NEW}=2026-10-25', f'{OLD}=2026-10-25', '--playwright', f'{NEW}=1.64.1', f'{OLD}=1.63.0']), 0)
            for build in (NEW, OLD):
                for key in ('extension-linux', 'devtools-linux'):
                    self.assertTrue(os.path.exists(os.path.join(out, build, key, 'misses.json')))
                    self.assertTrue(os.path.exists(os.path.join(out, build, key, 'agreement.txt')))
            with open(listing) as f: got = json.load(f)
            self.assertEqual(got['builds'][0]['measured']['extension-linux']['agreement'], 0.5)
            self.assertEqual(got['builds'][1]['measured']['extension-linux']['agreement'], 1.0)
            self.assertTrue(os.path.exists(os.path.join(out, 'comparison.txt')) and os.path.exists(os.path.join(out, 'comparison.json')))


if __name__ == '__main__': unittest.main()
