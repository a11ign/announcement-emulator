"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

run_devtools_readings.sh run for real, with a `npx` of the tests' own that stands in for Playwright: what it runs, in which order, where it files each project's run, and what it will not keep."""
import json, os, stat, subprocess, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'run_devtools_readings.sh')

# The stand-in `npx playwright test --project=<p>`: it logs the project and the environment it was started in, and leaves the report and run summary a run leaves unless the project is named in LEAVES_NOTHING.
FAKE_NPX = '''#!/bin/sh
echo "$* TREE=${ANNOUNCEMENT_EMULATOR_TREE-unset} FOCUS=${ANNOUNCEMENT_EMULATOR_REPORT_FOCUS-unset}" >> "$CALLS"
case " $* " in *" --project=${LEAVES_NOTHING:-none} "*) exit 1 ;; esac
mkdir -p test-results/announcement-emulator playwright-report
echo '{"suites":[]}' > test-results/report.json
echo '{"workers":[]}' > test-results/announcement-emulator/run.json
'''


class RunDevtoolsReadings(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.addCleanup(self.dir.cleanup)
        root = self.dir.name
        os.makedirs(os.path.join(root, 'bin')); os.makedirs(os.path.join(root, 'project'))
        npx = os.path.join(root, 'bin', 'npx')
        with open(npx, 'w') as f: f.write(FAKE_NPX)
        os.chmod(npx, os.stat(npx).st_mode | stat.S_IXUSR)
        self.calls, self.out, self.project = os.path.join(root, 'calls.log'), os.path.join(root, 'out'), os.path.join(root, 'project')

    def run_script(self, **env):
        env = {**os.environ, 'PATH': os.path.join(self.dir.name, 'bin') + os.pathsep + os.environ['PATH'], 'CALLS': self.calls, **env}
        return subprocess.run(['sh', SCRIPT, self.project, self.out], capture_output=True, text=True, env=env, timeout=120)

    def logged(self):
        with open(self.calls) as f: return f.read().splitlines()

    def test_three_projects_are_run_twice_in_order_and_filed_by_run_and_project(self):
        done = self.run_script()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([line.split()[2] for line in self.logged()], ['--project=corpus', '--project=structure', '--project=large'] * 2)
        for n in (1, 2):
            for project in ('corpus', 'structure', 'large'):
                d = os.path.join(self.out, f'devtools-{n}', project)
                self.assertEqual(sorted(os.listdir(d)), ['report.json', 'run.json', 'times.json'])
                times = json.load(open(os.path.join(d, 'times.json')))
                self.assertEqual((times['reading'], times['project'], times['run']), ('devtools-linux', project, n))

    def test_the_script_chooses_no_tree_source_and_asks_for_the_focus_the_way_the_fleet_reads_it(self):
        self.run_script(ANNOUNCEMENT_EMULATOR_TREE='devtools')
        for line in self.logged(): self.assertTrue(line.endswith('FOCUS=1'), line)
        # a setting left in the environment is the team's, and the script does not set one of its own
        self.assertEqual({line.split('TREE=')[1].split()[0] for line in self.logged()}, {'devtools'})

    def test_a_project_that_exists_is_not_run_again(self):
        self.run_script(); first = len(self.logged())
        self.run_script()
        self.assertEqual((first, len(self.logged())), (6, 6))

    def test_a_run_that_leaves_no_report_is_not_kept_and_the_script_says_so(self):
        done = self.run_script(LEAVES_NOTHING='large')
        self.assertEqual(done.returncode, 1)
        self.assertIn('devtools-1 large left no report: not kept', done.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.out, 'devtools-1', 'large', 'report.json')))
        self.assertTrue(os.path.exists(os.path.join(self.out, 'devtools-1', 'corpus', 'report.json')))


if __name__ == '__main__': unittest.main()
