"""python3 -m unittest discover -s middleware/agreement -t middleware/agreement   (from the repository root)

run_devtools_build_readings.sh run for real, with a `npx` of the tests' own that stands in for Playwright: what it runs, where it files each reading, what it refuses to keep."""
import json, os, stat, subprocess, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'run_devtools_build_readings.sh')
NEW, OLD = '156.0.8078.4', '153.0.8010.12'

# The stand-in `npx playwright test --project=corpus`: it writes the report and the run summary a run leaves, in the Chromium named by CHROMIUM_OF_<project directory name>, and logs the environment it was started in.
FAKE_NPX = '''#!/bin/sh
echo "$(basename "$PWD") $* TREE=${ANNOUNCEMENT_EMULATOR_TREE-unset} FOCUS=${ANNOUNCEMENT_EMULATOR_REPORT_FOCUS-unset}" >> "$CALLS"
mkdir -p test-results/announcement-emulator playwright-report
echo '{"suites":[]}' > test-results/report.json
chromium=$(cat chromium.txt)
echo "{\\"workers\\":[{\\"startup\\":{\\"chromium\\":\\"$chromium\\"}}]}" > test-results/announcement-emulator/run.json
'''


class RunDevtoolsBuildReadings(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.addCleanup(self.dir.cleanup)
        root = self.dir.name
        os.makedirs(os.path.join(root, 'bin'))
        npx = os.path.join(root, 'bin', 'npx')
        with open(npx, 'w') as f: f.write(FAKE_NPX)
        os.chmod(npx, os.stat(npx).st_mode | stat.S_IXUSR)
        self.calls = os.path.join(root, 'calls.log')
        self.out = os.path.join(root, 'out')
        self.projects = {}

    def project(self, build, chromium):
        path = os.path.join(self.dir.name, 'p' + build.split('.')[0]); os.makedirs(path)
        with open(os.path.join(path, 'chromium.txt'), 'w') as f: f.write(chromium)
        self.projects[build] = path
        return path

    def run_script(self, *specs):
        env = {**os.environ, 'PATH': os.path.join(self.dir.name, 'bin') + os.pathsep + os.environ['PATH'], 'CALLS': self.calls, 'ANNOUNCEMENT_EMULATOR_TREE': 'extension'}
        return subprocess.run(['sh', SCRIPT, self.out, *specs], capture_output=True, text=True, env=env, timeout=120)

    def logged(self):
        with open(self.calls) as f: return f.read().splitlines()

    def test_each_build_is_run_twice_interleaved_by_build_with_the_devtools_source_and_filed_by_run(self):
        a, b = self.project(NEW, NEW), self.project(OLD, OLD)
        done = self.run_script(f'{NEW}={a}', f'{OLD}={b}')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([line.split()[0] for line in self.logged()], ['p156', 'p153', 'p156', 'p153'])      # the builds, one after the other, twice
        for build in (NEW, OLD):
            for n in (1, 2):
                d = os.path.join(self.out, build, f'devtools-{n}')
                self.assertEqual(sorted(os.listdir(d)), ['report.json', 'run.json', 'times.json'])
                times = json.load(open(os.path.join(d, 'times.json')))
                self.assertEqual((times['reading'], times['chromium'], times['run']), ('devtools-linux', build, n))
        self.assertFalse(os.path.exists(os.path.join(self.out, NEW, 'extension-1')))

    def test_the_script_chooses_no_tree_source_and_asks_for_the_focus_the_way_the_fleet_reads_it(self):
        self.run_script(f'{NEW}={self.project(NEW, NEW)}')
        for line in self.logged(): self.assertTrue(line.startswith('p') and ' test --project=corpus ' in line and line.endswith('FOCUS=1'), line)
        # a setting left in the environment is the team's, and the script does not set one of its own
        self.assertEqual({line.split('TREE=')[1].split()[0] for line in self.logged()}, {'extension'})

    def test_a_run_whose_workers_ran_in_another_chromium_is_not_kept_and_the_script_says_so(self):
        done = self.run_script(f'{NEW}={self.project(NEW, OLD)}')
        self.assertEqual(done.returncode, 1)
        self.assertIn(f'devtools-1 of {NEW} ran in another Chromium build', done.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.out, NEW, 'devtools-1', 'report.json')))

    def test_a_reading_that_exists_is_not_run_again(self):
        spec = f'{NEW}={self.project(NEW, NEW)}'
        self.run_script(spec); first = len(self.logged())
        self.run_script(spec)
        self.assertEqual((first, len(self.logged())), (2, 2))

    def test_no_build_is_refused(self):
        done = self.run_script()
        self.assertEqual(done.returncode, 2)
        self.assertIn('at least one <build>=<project>', done.stderr)


if __name__ == '__main__': unittest.main()
