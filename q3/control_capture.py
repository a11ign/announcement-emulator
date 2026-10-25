"""Capture a sample of the static synthetic pages on the fleet (the control: no page drift), as one fleet job (A11-246).

    python control_capture.py <pages_dir> <host_url> <out_dir> <n> --boxes <n|ready|name,name,...> --label <KEY> [--wait <duration>]
    python control_capture.py collect <out_dir> [<job ID>]

The sample is every k-th file of the sorted list of good/bad pages, so it is fixed by n alone; a page with a record in <out_dir> is left out of the job. The job ID is printed. With `--wait` this makes one foreground
`fleet job wait` and collects; without it, write the ID in the outcome, end the turn, and run `collect` when woken. `collect` writes `<rel with / as __, less .html>.json` for each page, naming the box and `capture-host`, never an address (fleet_capture.py)."""
import argparse, glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet_capture as fc


def sample(pages_dir, n):
    files = sorted(glob.glob(os.path.join(pages_dir, '*', '*.html')))
    step = max(1, len(files) // n)
    return [os.path.relpath(f, pages_dir) for f in files[::step][:n]]


def slug_of(rel): return rel.replace('/', '__')[:-len('.html')]


def collect(out, job=None):
    _, _, found = fc.results(out, job)
    for r in found:
        fc.write_record(out, r.name, r.record)
        print(r.name[:-len('.json')], r.record['status'], r.box, flush=True)
    print('done')


def submit(a):
    base = a.host_url.rstrip('/')
    todo = [(rel, f'{base}/{rel}') for rel in sample(a.pages_dir, a.n) if not os.path.exists(os.path.join(a.out_dir, slug_of(rel) + '.json'))]
    if not todo: sys.exit('every page of the sample has a record in the output directory: nothing to capture')
    job = fc.submit([address for _, address in todo], a.boxes, a.label)
    fc.write_pending(a.out_dir, job, a.label, {address: {'1': slug_of(rel) + '.json'} for rel, address in todo})
    if fc.follow(job, a.wait, f'python3 {os.path.abspath(__file__)} collect {a.out_dir} {job}'): collect(a.out_dir, job)


def main(argv):
    if argv[:1] == ['collect'] and 2 <= len(argv) <= 3: return collect(*argv[1:])
    if '--workers' in argv: sys.exit('--workers is gone: the fleet job service finds each box\'s address itself. Give --boxes <n|ready|name,name,...> and --label <the ticket key>.')
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0]); ap.add_argument('pages_dir'); ap.add_argument('host_url'); ap.add_argument('out_dir'); ap.add_argument('n', type=int)
    ap.add_argument('--boxes', required=True); ap.add_argument('--label', required=True); ap.add_argument('--wait', metavar='DURATION')
    submit(ap.parse_args(argv))


if __name__ == '__main__': main(sys.argv[1:])
