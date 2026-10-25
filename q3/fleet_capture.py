"""The one client of the fleet job service in this repository (A11-246). Every capture entry point submits a job through it and reads the job's results through it; none runs a capture in the caller's shell.

    python3 fleet_capture.py capture <box> <address> <out.json> [steps] [--tables] [--typing-dialog] --label <KEY> [--wait <duration>]
    python3 fleet_capture.py collect <out.json> [<job ID>]

`capture` submits a job of one page on the named box (what this script was used for by hand, and by q3/replay/fleet/box.sh) and prints the job ID. The job runs on the control plane and goes on when the caller ends. With `--wait`
it makes one foreground `fleet job wait <id> --timeout <duration>` and, when the job is done, collects. Without it the ID is the result: write it in the outcome, end the turn, and run `collect` when woken (house notes, "Using the fleet").
`--tables` asks for the worker's table probe and `--typing-dialog` for its typing probe and its Escape probe (`fleet capture submit --probe tables` and `--probe typing,dialog`; A11-208 uses the second to capture the same actions as a Playwright test that tabs, presses Escape and types).

The `fleet` command is `$FLEET` when set (it may carry arguments), else `fleet` on PATH. The service finds each box's address itself, so a box is named and never addressed: the records name the box (`a11y-worker-2`) and the machine serving
the page (`capture-host`), never a network address.

An entry point writes a `<out>/.fleet-jobs/<job ID>.json` when it submits (the names its records get, and what it needs when it collects) and `collect` reads it, so the results can be collected by a later command that knows only the output directory.
The subdirectory keeps it, and the job's manifest, out of every `<dir>/*.json` glob that reads records. Standard library only."""
import argparse, collections, contextlib, datetime, glob, json, os, re, shlex, subprocess, sys, tempfile

USAGE = 'usage: fleet_capture.py capture <box> <address> <out.json> [steps] [--tables] [--typing-dialog] --label <KEY> [--wait <duration>]  |  fleet_capture.py collect <out.json> [<job ID>]'
SERVER_NAME = 'capture-host'
PENDING_DIR = '.fleet-jobs'
JOB_ID = re.compile(r'fj-[0-9A-Za-z]+-[0-9a-f]+')
EXIT_TIMEOUT = 124      # `fleet job wait`: the timeout ran out and the job goes on
Result = collections.namedtuple('Result', 'page pass_number box name record')


def run_fleet(*args, capture=True):
    command = shlex.split(os.environ.get('FLEET') or 'fleet')
    try: return subprocess.run([*command, *args], capture_output=capture, text=True)
    except FileNotFoundError: sys.exit(f'`{command[0]}` was not found: set $FLEET to the fleet command. This host cannot submit fleet work, and no capture is run here instead.')


def submit(pages, boxes, label, passes=1, steps=600, probes=(), freeze=None):
    """`fleet capture submit` for the pages, printing and returning the job ID. The label is the ticket key; the service refuses a job without one, and so does this, before `fleet` runs."""
    if not label: sys.exit('--label is required: the ticket key')
    if not pages: sys.exit('no pages to capture')
    with tempfile.TemporaryDirectory() as tmp:
        pages_file = os.path.join(tmp, 'pages.json')
        with open(pages_file, 'w') as f: json.dump(list(pages), f)
        args = ['capture', 'submit', '--pages', pages_file, '--boxes', str(boxes), '--passes', str(passes), '--steps', str(steps)]
        if probes: args += ['--probe', ','.join(probes)]
        if freeze: args += ['--freeze', freeze]
        done = run_fleet(*args, '--label', label)
    lines = done.stdout.strip().splitlines()
    job = lines[-1] if lines else ''
    if done.returncode or not JOB_ID.fullmatch(job): sys.exit(f'fleet capture submit failed ({done.returncode}): {done.stderr.strip() or done.stdout.strip() or "no job ID was printed"}')
    print(job, flush=True)
    return job


def follow(job, wait, collect_command):
    """Without `wait`, say what to do with the job ID and return False. With it, one foreground `fleet job wait <id> --timeout <wait>`: True when the job is done, else exit with its code (124 when the timeout ran out and the job goes on)."""
    if not wait:
        print(f'submitted {job}: write it in the outcome and end the turn. When it is done: {collect_command}', file=sys.stderr)
        return False
    code = run_fleet('job', 'wait', job, '--timeout', wait, capture=False).returncode
    if code == 0: return True
    if code == EXIT_TIMEOUT: print(f'{job} is still running after {wait}. When it is done: {collect_command}', file=sys.stderr)
    sys.exit(code)


def write_pending(out, job, label, names, **extra):
    """What `collect` needs to know about the job: `names` is {page: {pass: file name in `out`}}, `extra` whatever the entry point reads when it collects. No address of ours is kept in it, any more than in a record: a page is under its name as `results` gives it."""
    os.makedirs(os.path.join(out, PENDING_DIR), exist_ok=True)
    text = json.dumps({'job': job, 'label': label, 'submittedAt': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'names': names, **extra}, indent=1)
    with open(os.path.join(out, PENDING_DIR, job + '.json'), 'w') as f: f.write(named(text, re.findall(r'https?://[^\s"\\]+', text)))


def read_pending(out, job=None, name=None):
    """The job's pending file, or the newest in `out` (that names a record `name`, when one is given)."""
    folder = os.path.join(out, PENDING_DIR)
    if job:
        path = os.path.join(folder, job + '.json')
        if not os.path.exists(path): sys.exit(f'{job} was not submitted from {out}: there is no {path}')
        with open(path) as f: return json.load(f)
    found = []
    for path in glob.glob(os.path.join(folder, 'fj-*.json')):
        if path.endswith('.manifest.json'): continue
        with open(path) as f: found.append(json.load(f))
    if name: found = [p for p in found if any(name in passes.values() for passes in p['names'].values())]
    if not found: sys.exit(f'nothing was submitted from {out}{f" for {name}" if name else ""}: there is no pending job in {folder}')
    return max(found, key=lambda p: (p['submittedAt'], p['job']))


@contextlib.contextmanager
def fetched(job):
    """`fleet job fetch`, into a directory that is removed afterwards: the job's manifest and the directory its record files are in."""
    with tempfile.TemporaryDirectory() as tmp:
        done = run_fleet('job', 'fetch', job, '--to', tmp)
        if done.returncode: sys.exit(f'fleet job fetch {job} failed ({done.returncode}): {done.stderr.strip() or done.stdout.strip()}')
        folder = os.path.join(tmp, job)
        try:
            with open(os.path.join(folder, 'manifest.json')) as f: manifest = json.load(f)
        except (OSError, ValueError) as e: sys.exit(f'{job} has no readable manifest.json in its results: {e}')
        yield manifest, folder


def named(text, pages):
    """A page server given as an IP literal is written by name, so that no record or manifest holds one of our addresses."""
    hosts = {m.group(1) for m in (re.match(r'https?://([^/:?#]+)', page) for page in pages) if m}
    for host in sorted(h for h in hosts if re.fullmatch(r'[\d.]+', h)): text = text.replace(host, SERVER_NAME)
    return text


def record_of(entry, folder):
    """The record a capture left, or, for one that left none (a box that left the fleet before it was sent the page), a record in the shape a failed capture always had, naming the box and the error."""
    path = os.path.join(folder, entry['file']) if entry.get('file') else ''
    if path and os.path.exists(path):
        with open(path) as f: return json.load(f)
    return {'capturedAt': entry.get('finishedAt') or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'), 'worker': entry['box'], 'status': 0,
            'capture': {'error': entry.get('error') or f'{entry["box"]}: no record was written for this capture ({entry.get("status")})'}}


def results(out, job=None, name=None):
    """Fetch the job and read its manifest: (pending file, manifest, [Result]). Only a job that is done has results to collect; the manifest, with no address of ours in it, is kept as `<out>/.fleet-jobs/<job>.manifest.json`."""
    pending = read_pending(out, job, name)
    with fetched(pending['job']) as (manifest, folder):
        if manifest.get('state') != 'done': sys.exit(f'{pending["job"]} is {manifest.get("state")}{": " + manifest["reason"] if manifest.get("reason") else ""}: only a job that is done has results to collect')
        found = []
        for entry in manifest['captures']:
            page = named(entry['page'], [entry['page']])
            try: file_name = pending['names'][page][str(entry['pass'])]
            except KeyError: sys.exit(f'{pending["job"]} captured {page} (pass {entry["pass"]}), which this entry point did not submit')
            found.append(Result(page, entry['pass'], entry['box'], file_name, json.loads(named(json.dumps(record_of(entry, folder)), manifest['pages']))))
    with open(os.path.join(out, PENDING_DIR, pending['job'] + '.manifest.json'), 'w') as f: f.write(named(json.dumps(manifest, indent=1), manifest['pages']))
    return pending, manifest, found


def write_record(out, name, record, overwrite=False):
    """Write one record under its name; an existing record is kept unless `overwrite`, so that a stale file is never mistaken for this job's and a record collected before is not written twice. True when written."""
    path = os.path.join(out, name)
    if os.path.exists(path) and not overwrite: return False
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: json.dump(record, f, indent=1, ensure_ascii=False)
    return True


def collect_one(out_file, job=None):
    """The record of a `capture`, written to the file it was named for (overwritten: a probe is captured again under the same name)."""
    out, name = os.path.dirname(out_file) or '.', os.path.basename(out_file)
    _, _, found = results(out, job, name)
    for r in found: write_record(out, r.name, r.record, overwrite=True)
    record = found[0].record
    error = (record.get('capture') or {}).get('error')
    print(record['status'], error if error else f'{len((record["capture"] or {}).get("transcript") or [])} lines')


def capture(argv):
    ap = argparse.ArgumentParser(prog='fleet_capture.py capture', description='submit one page on one named box as a fleet job')
    ap.add_argument('box'); ap.add_argument('address'); ap.add_argument('out'); ap.add_argument('steps', nargs='?', type=int, default=600)
    ap.add_argument('--tables', action='store_true'); ap.add_argument('--typing-dialog', action='store_true'); ap.add_argument('--label', required=True); ap.add_argument('--wait', metavar='DURATION')
    a = ap.parse_intermixed_args(argv)
    if not re.fullmatch(r'[\w-]+', a.box): sys.exit(f'the first argument is a box name, e.g. a11y-worker-2 ({a.box!r} is not one): the fleet job service finds the box\'s address itself, so a name=address pair is not given any more')
    probes = [*(['tables'] if a.tables else []), *(['typing', 'dialog'] if a.typing_dialog else [])]
    job = submit([a.address], a.box, a.label, steps=a.steps, probes=probes)
    out = os.path.dirname(a.out) or '.'
    write_pending(out, job, a.label, {a.address: {'1': os.path.basename(a.out)}})
    if follow(job, a.wait, f'python3 {os.path.abspath(__file__)} collect {a.out} {job}'): collect_one(a.out, job)


def main(argv):
    if argv[:1] == ['capture']: capture(argv[1:])
    elif argv[:1] == ['collect'] and 2 <= len(argv) <= 3: collect_one(*argv[1:])
    else: sys.exit(USAGE)


if __name__ == '__main__': main(sys.argv[1:])
