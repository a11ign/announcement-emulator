"""The runtime process, as the middleware starts it (main.py), with the DevTools port as its one tree source (A11-229, step 3): the records it writes for a browser that was reached, and that removing the extension changed
nothing it writes for the sequences recorded through the DevTools port.

The second needs the emulator's virtualenv and NVDA's source (`setup.sh`, or the bundle) in $EMU_DOWNLOADS; skipped without them."""
import glob, gzip, json, os, pathlib, socket, subprocess, sys, unittest, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'emu'))
import main
from paths import DOWNLOADS

PYTHON = next((p for p in (DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python', DOWNLOADS / 'python' / 'bin' / 'python3') if p.exists()), None)
HAVE = PYTHON is not None and (DOWNLOADS / 'nvda-src' / 'source').is_dir()
FIXTURES = HERE / 'fixtures'
GOLDEN = FIXTURES / 'devtools-main-records.json.gz'


class StartRecords(unittest.TestCase):
    def test_the_record_for_a_browser_that_was_reached_carries_its_build(self):
        self.assertEqual(main.start_record('attached', {'target': 't', 'browser': '156.0.8078.4'}, 12.5),
                         {'kind': 'start', 'what': 'devtools', 't': 12500, 'browser': '156.0.8078.4'})

    def test_a_browser_that_named_no_build_has_none_in_its_record(self):
        self.assertIsNone(main.start_record('attached', {'target': 't', 'browser': None}, 1.0)['browser'])

    def test_the_port_says_when_it_came_up_and_nothing_else_is_said_of_an_extension(self):
        self.assertEqual(main.start_record('ready', {'t': 5}, 0), {'kind': 'start', 'what': 'tree-source', 't': 5})
        self.assertEqual(main.start_record('ready', {'t': 5, 'source': 'devtools'}, 0), {'kind': 'start', 'what': 'tree-source', 't': 5})
        self.assertIsNone(main.start_record('hello', {'t': 5, 'automation': 'chrome.automation'}, 0))

    def test_what_is_no_start_has_no_record(self):
        self.assertIsNone(main.start_record('page', {}, 0))


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def without_timings(x):
    """What a run makes of a recording, without how long it took (`ms`), which differs from one run to the next."""
    if isinstance(x, dict): return {k: without_timings(v) for k, v in x.items() if k != 'ms'}
    if isinstance(x, list): return [without_timings(v) for v in x]
    return x


def run_through_the_runtime(name):
    """The records `main.py` writes when it is told, over its collector, what a recording holds: the way the browser's side tells it, with no browser. The records are those of the whole process: its boot, the drain, the sweeps."""
    port = free_port()
    child = subprocess.Popen([str(PYTHON), '-I', str(HERE / 'main.py'), '--port', str(port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env={**os.environ, 'EMU_DOWNLOADS': str(DOWNLOADS)})
    try:
        while json.loads(child.stdout.readline())['type'] != 'ready': pass
        with gzip.open(FIXTURES / f'{name}.jsonl.gz', 'rt') as f:
            for row in map(json.loads, f):
                urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/{row["k"]}', data=json.dumps(row['body']).encode(), method='POST'), timeout=10).read()
        child.stdin.write(json.dumps({'cmd': 'drain', 'id': 1}) + '\n'); child.stdin.flush()
        records = []
        while True:
            message = json.loads(child.stdout.readline())
            if message['type'] == 'record': records.append(message['rec'])
            if message['type'] == 'drained': break
        child.stdin.write(json.dumps({'cmd': 'quit'}) + '\n'); child.stdin.flush()
        return without_timings(records)
    finally:
        child.kill(); child.wait(); child.stdin.close(); child.stdout.close()


def devtools_recordings():
    return sorted(os.path.relpath(p, FIXTURES)[:-len('.jsonl.gz')] for p in glob.glob(str(FIXTURES / '**' / 'devtools-*.jsonl.gz'), recursive=True))


@unittest.skipUnless(HAVE, "needs the emulator's virtualenv and NVDA's source (setup.sh)")
class RecordedDevtoolsSequences(unittest.TestCase):
    """`fixtures/devtools-main-records.json.gz` is what `main.py` wrote for each recording through the DevTools port (`fixtures/**/devtools-*.jsonl.gz`) when the extension was still a tree source, the commit
    before it was removed (A11-229, step 3: e127a08, the merge of step 2, was the base). The extension's tree source, its fallback and the switch between them are gone, and the DevTools path writes the same records."""
    @classmethod
    def setUpClass(cls):
        with gzip.open(GOLDEN, 'rt') as f: cls.golden = json.load(f)
        cls.emptied = []
        for records in cls.golden.values():
            for r in records:
                if r['kind'] == 'start' and r['what'] == 'tree-source': cls.emptied.append((r.pop('desktopChildren'), r.pop('documents')))      # see test_the_one_difference...

    def test_the_one_difference_is_two_empty_fields_of_the_start_record_that_only_the_extension_filled(self):
        """The record that says the port came up carried `desktopChildren` and `documents`, which the extension's `ready` filled and which were `null` for the port. They are not written now, and nothing read them for the port:
        the golden is compared without them, and these were all empty."""
        self.assertTrue(self.emptied)
        self.assertEqual(set(self.emptied), {(None, None)})

    def test_every_recording_has_its_records_and_no_record_is_for_a_recording_that_is_gone(self):
        self.assertEqual(sorted(self.golden), devtools_recordings())

    def test_the_records_are_those_written_before_the_extension_was_removed(self):
        for name in devtools_recordings():
            with self.subTest(name): self.assertEqual(run_through_the_runtime(name), self.golden[name])

    def test_there_is_speech_to_compare(self):
        self.assertTrue(all(any(r['kind'] == 'speech' for r in records) for records in self.golden.values()))
        self.assertTrue(all(any(r['kind'] == 'start' and r['what'] == 'tree-source' for r in records) for records in self.golden.values()))


if __name__ == '__main__': unittest.main()
