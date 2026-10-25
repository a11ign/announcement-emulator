"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)"""
import datetime, json, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_freeze


def repo_with(files):
    d = tempfile.mkdtemp()
    run = lambda *a: subprocess.run(['git', '-C', d, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)      # noqa: E731
    run('init', '-q')
    for path, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, path)) or d, exist_ok=True)
        with open(os.path.join(d, path), 'w') as f: f.write(text)
    run('add', '-A'); run('commit', '-q', '-m', 'freeze')
    return d, run


class Freeze(unittest.TestCase):
    FILES = {p: p for p in make_freeze.OBJECTS}

    def test_the_freeze_names_every_object_the_figure_is_made_by(self):
        d, _ = repo_with({**{p + ('/x' if '.' not in os.path.basename(p) else ''): p for p in make_freeze.OBJECTS}})
        freeze = make_freeze.name(d, 'HEAD', now=datetime.datetime(2026, 10, 24, 20, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(sorted(freeze['objects']), sorted(make_freeze.OBJECTS))
        self.assertEqual(freeze['namedAt'], '2026-10-24T20:00:00Z')
        self.assertEqual(make_freeze.moved(freeze, d), [])

    def test_a_change_to_a_named_thing_is_found_and_a_change_to_any_other_is_not(self):
        files = {p + ('/x' if '.' not in os.path.basename(p) else ''): p for p in make_freeze.OBJECTS}
        d, run = repo_with({**files, 'docs/other.md': 'a'})
        freeze = make_freeze.name(d, 'HEAD')
        with open(os.path.join(d, 'docs/other.md'), 'w') as f: f.write('b')
        run('commit', '-qam', 'docs')
        self.assertEqual(make_freeze.moved(freeze, d), [])
        with open(os.path.join(d, 'middleware/runtime/x'), 'w') as f: f.write('changed')
        run('commit', '-qam', 'runtime')
        self.assertEqual(make_freeze.moved(freeze, d), ['middleware/runtime'])

    def test_a_later_measurement_names_what_it_adds_and_a_change_to_it_is_found(self):
        files = {p + ('/x' if '.' not in os.path.basename(p) else ''): p for p in make_freeze.OBJECTS}
        d, run = repo_with({**files, 'rule.md': 'a', 'compare.py': 'a'})
        freeze = make_freeze.name(d, 'HEAD', extra=['rule.md', 'compare.py', 'middleware/runtime'])      # a path the standard list has is named once
        self.assertEqual(sorted(freeze['objects']), sorted([*make_freeze.OBJECTS, 'rule.md', 'compare.py']))
        self.assertEqual(make_freeze.moved(freeze, d), [])
        with open(os.path.join(d, 'compare.py'), 'w') as f: f.write('b')
        run('commit', '-qam', 'compare')
        self.assertEqual(make_freeze.moved(freeze, d), ['compare.py'])

    def test_also_is_for_naming_only(self):
        with self.assertRaises(SystemExit): make_freeze.main(['check', 'f.json', '--also', 'x'])

    def test_a_capture_older_than_the_freeze_is_found(self):
        freeze = {'namedAt': '2026-10-24T20:00:00Z'}
        with tempfile.TemporaryDirectory() as d:
            for name, at in (('a.json', '2026-10-24T19:59:59.999Z'), ('b.json', '2026-10-24T20:00:01.000Z'), ('c.json', None)):
                with open(os.path.join(d, name), 'w') as f: json.dump({'capturedAt': at}, f)
            self.assertEqual(make_freeze.early(freeze, d), ['a.json', 'c.json'])


if __name__ == '__main__': unittest.main()
