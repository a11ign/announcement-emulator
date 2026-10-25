"""A stand-in for the `fleet` command, for the tests of every capture entry point (A11-246). Nothing here reaches a fleet.

    stub = FleetStub(self)                                  # points $FLEET at it for the length of the test
    stub.results(pages, boxes, passes=1, ...)               # what `fleet job fetch` copies: a manifest in the service's shape (control: src/fleet-jobs/manifest.ts) and its records
    ... run an entry point ...
    stub.calls()                                            # every call, as its argument list; stub.submits() the `capture submit` calls with their options and the pages file's content

`capture submit` prints the job ID, `job wait` exits with `wait_exit`, `job fetch --to D` writes `D/<job>/manifest.json` and the records. Standard library only."""
import contextlib, hashlib, io, json, os, re, stat, sys, tempfile, unittest.mock

SCRIPT = '''#!{python}
import json, os, shutil, sys
config = json.load(open(os.environ['FLEET_STUB']))
args = sys.argv[1:]
entry = {{'argv': args}}
if args[:2] == ['capture', 'submit']: entry['pages'] = json.load(open(args[args.index('--pages') + 1]))
with open(config['log'], 'a') as f: f.write(json.dumps(entry) + '\\n')
if args[:2] == ['capture', 'submit']:
    if config['submit_exit']: sys.stderr.write(config['submit_error'] + '\\n'); sys.exit(config['submit_exit'])
    print(config['job']); sys.stderr.write('submitted; follow it with: fleet job wait ' + config['job'] + ' --timeout 30m\\n')
elif args[:2] == ['job', 'wait']: sys.exit(config['wait_exit'])
elif args[:2] == ['job', 'fetch']:
    folder = os.path.join(args[args.index('--to') + 1], args[2]); os.makedirs(folder)
    json.dump(config['manifest'], open(os.path.join(folder, 'manifest.json'), 'w'))
    for name, record in config['files'].items(): json.dump(record, open(os.path.join(folder, name), 'w'))
else: sys.exit(2)
'''


def run_main(main, argv):
    """(exit code, stdout, stderr) of an entry point's `main(argv)`; the text of a `sys.exit(message)` is in stderr."""
    out, err, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try: main(argv)
        except SystemExit as e: code = e.code if isinstance(e.code, int) else (1 if e.code else 0); err.write(e.code if isinstance(e.code, str) else '')
    return code, out.getvalue(), err.getvalue()


def record_file(page, pass_number):
    """The service's name for a page's record (control: src/fleet-jobs/pages.ts `recordFile`)."""
    readable = re.sub(r'^_+|_+$', '', re.sub(r'[^A-Za-z0-9._-]+', '_', re.sub(r'^https?://', '', page)))[:80]
    return f'{readable or "page"}-{hashlib.sha1(page.encode()).hexdigest()[:8]}.p{pass_number}.json'


def ok_record(box, page):
    return {'capturedAt': '2026-10-25T10:00:00.000Z', 'worker': box, 'status': 200, 'capture': {'url': page, 'transcript': ['a', 'b'], 'structure': {'links': ['a, link'], 'headings': []}}}


class FleetStub:
    JOB = 'fj-20261025T100000Z-a1b2c3'

    def __init__(self, test, job=JOB, wait_exit=0, submit_exit=0):
        self.dir = tempfile.TemporaryDirectory(); test.addCleanup(self.dir.cleanup)
        self.script, self.config_path, self.log = (os.path.join(self.dir.name, n) for n in ('fleet', 'config.json', 'calls.jsonl'))
        with open(self.script, 'w') as f: f.write(SCRIPT.format(python=sys.executable))
        os.chmod(self.script, os.stat(self.script).st_mode | stat.S_IXUSR)
        self.config = {'log': self.log, 'job': job, 'wait_exit': wait_exit, 'submit_exit': submit_exit, 'submit_error': 'the control plane could not be reached', 'manifest': {}, 'files': {}}
        self.job = job; self.save()
        patcher = unittest.mock.patch.dict(os.environ, {'FLEET': self.script, 'FLEET_STUB': self.config_path}); patcher.start(); test.addCleanup(patcher.stop)

    def save(self):
        with open(self.config_path, 'w') as f: json.dump(self.config, f)

    def set(self, **config): self.config.update(config); self.save()

    def results(self, pages, boxes, passes=1, label='A11-246', missing=(), failed=(), unreached=(), state='done', consistent=True, mismatches=(), reason=None, records=None):
        """The results of a job of `pages` x `passes` on `boxes`, planned as the service plans them (pass k of page i on box (i+k-1) mod n). `missing`: (page, pass) pairs with no record file (a box that left the fleet before the
        page was sent); `failed`: (page, pass) pairs whose record is a failed capture; `unreached`: (page, pass) pairs a job that failed or was cancelled never sent (status `pending`, no file); `records`: {(page, pass): record} to put in place of the default."""
        captures, files = [], {}
        for i, page in enumerate(pages):
            for k in range(1, passes + 1):
                box, name = boxes[(i + k - 1) % len(boxes)], record_file(page, k)
                capture = {'page': page, 'pass': k, 'file': name, 'box': box, 'status': 'done', 'startedAt': '2026-10-25T10:00:00.000Z', 'finishedAt': '2026-10-25T10:01:00.000Z', 'httpStatus': 200, 'error': None, 'note': None}
                if (page, k) in unreached: capture.update(status='pending', startedAt=None, finishedAt=None, httpStatus=None); captures.append(capture); continue
                if (page, k) in missing: capture.update(status='failed', httpStatus=None, error=f'{box} left the fleet: three captures in a row failed on it'); captures.append(capture); continue
                record = (records or {}).get((page, k)) or (ok_record(box, page) if (page, k) not in failed else {'capturedAt': '2026-10-25T10:01:00.000Z', 'worker': box, 'status': 429, 'capture': {'error': 'a capture is already in progress'}})
                if (page, k) in failed: capture.update(status='failed', httpStatus=429, error='a capture is already in progress')
                files[name] = record; captures.append(capture)
        manifest = {'version': 1, 'job': self.job, 'label': label, 'state': state, 'reason': reason, 'submittedAt': '2026-10-25T09:59:00.000Z', 'startedAt': '2026-10-25T10:00:00.000Z', 'finishedAt': '2026-10-25T10:05:00.000Z',
                    'pages': list(pages), 'passes': passes, 'body': {'steps': 600}, 'freeze': None, 'pins': {'pins': {}},
                    'boxes': [{'name': b, 'workerCode': 'abc', 'windowsBuild': '26200.1', 'edge': '141.0', 'nvda': '2026.1', 'read': True} for b in boxes], 'dropped': [],
                    'agreement': {'consistent': consistent, 'mismatches': list(mismatches), 'reportedOnly': [], 'compared': ['windowsBuild', 'edge', 'nvda']}, 'notes': [], 'captures': captures}
        self.set(manifest=manifest, files=files)
        return manifest

    def calls(self):
        if not os.path.exists(self.log): return []
        with open(self.log) as f: return [json.loads(line) for line in f]

    def submits(self):
        """Each `capture submit`: its options as {flag: value} and the pages in the file it was given."""
        out = []
        for call in self.calls():
            if call['argv'][:2] != ['capture', 'submit']: continue
            rest = call['argv'][2:]
            out.append({'options': dict(zip(rest[::2], rest[1::2])), 'pages': call['pages']})
        return out

    def others(self): return [c['argv'] for c in self.calls() if c['argv'][:2] != ['capture', 'submit']]
