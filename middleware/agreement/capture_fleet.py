"""Capture each sample page twice on the fleet, as one fleet job (A11-246), on boxes that agree on every version (A11-208, question 5).

    python3 capture_fleet.py <pages.json> <out dir> --boxes <n|ready|name,name,...> --label <KEY> [--freeze <freeze.json>] [--wait <duration>]
    python3 capture_fleet.py collect <out dir> [<job ID>]

The job ID is printed. It runs on the control plane and goes on when the caller ends: write the ID in the outcome and end the turn, or give `--wait` for one foreground `fleet job wait` that collects when the job is done.
The two captures of a page go to two different boxes (the service plans pass k of page i on box (i+k-1) mod n, `plan` below), so `--boxes` is at least 2, one capture at a time on each box, and the job takes its boxes by booking.
Nothing on a box is changed: the request is the worker's own capture, with the typing and Escape probes, and the records name the worker and never its address. A page whose two records exist is not captured again.

`collect` writes pass k of each page to `<slug>.f<k>.json` (measure.py's `slug`), the files measure.py reads. It writes nothing when the job's boxes did not agree on every version: the manifest says so, and the check that
`--workers` once made by choosing the boxes is made here by reading it."""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.append(os.path.join(HERE, '..', '..', 'q3'))      # q3 last: it has a measure.py of its own
import fleet_capture as fc

PASSES = 2
STEPS = 600
PROBES = ('typing', 'dialog')


def plan(addresses, workers):
    """[(address, k, worker)] with the two captures of an address on two boxes. This is the rule the job service applies (control: planCaptures); it is kept here for test_select.py."""
    n = len(workers)
    return [(a, k, workers[(i + k - 1) % n]) for i, a in enumerate(addresses) for k in (1, 2)]


def file_name(address, k):
    from measure import slug
    return f'{slug(address)}.f{k}.json'


def collect(out, job=None):
    _, manifest, found = fc.results(out, job)
    agreement = manifest['agreement']
    if not agreement['consistent']:
        sys.exit(f'{manifest["job"]}: the boxes do not agree on every version, so no record is written (A11-208, question 5):\n  ' + '\n  '.join(agreement['mismatches'] or ['(no mismatch was named)']))
    for r in found:
        fc.write_record(out, r.name, r.record)
        print(r.box, r.pass_number, r.page, r.record['status'], flush=True)
    print('done')


def submit(a):
    with open(a.pages) as f: addresses = [p['url'] for p in json.load(f)['sample']]
    os.makedirs(a.out, exist_ok=True)
    todo = [address for address in addresses if not all(os.path.exists(os.path.join(a.out, file_name(address, k))) for k in range(1, PASSES + 1))]
    if not todo: sys.exit('every page has both records in the output directory: nothing to capture')
    job = fc.submit(todo, a.boxes, a.label, passes=PASSES, steps=STEPS, probes=PROBES, freeze=a.freeze)
    fc.write_pending(a.out, job, a.label, {address: {str(k): file_name(address, k) for k in range(1, PASSES + 1)} for address in todo})
    if fc.follow(job, a.wait, f'python3 {os.path.abspath(__file__)} collect {a.out} {job}'): collect(a.out, job)


def main(argv):
    if argv[:1] == ['collect'] and 2 <= len(argv) <= 3: return collect(*argv[1:])
    if '--workers' in argv: sys.exit('--workers is gone: the fleet job service finds each box\'s address itself. Give --boxes <n|ready|name,name,...> (at least 2: the two captures of a page go to two boxes) and --label <the ticket key>.')
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0]); ap.add_argument('pages'); ap.add_argument('out')
    ap.add_argument('--boxes', required=True); ap.add_argument('--label', required=True); ap.add_argument('--freeze'); ap.add_argument('--wait', metavar='DURATION')
    submit(ap.parse_args(argv))


if __name__ == '__main__': main(sys.argv[1:])
