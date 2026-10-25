"""Capture the corpus again on boxes whose browser keeps no history (A11-155), as one fleet job (A11-246), and stamp every record with the read-back that allowed it.

    python corpus_capture.py <corpus.json> <out_dir> --boxes name,name,... --label <KEY> --readback <history-readback.json> [--summary <capture-run.json>] [--static-base http://host:port] [--wait <duration>]
    python corpus_capture.py collect <out_dir> [<job ID>]

`corpus.json` is q3/results/corpus.json (or a list of addresses): the same addresses as the spike, so the split rule (split.py, a function of the address) and the comparison with the spike's figures hold. A box with no passing
read-back in the read-back file is refused, and so is a run with fewer than three; this is checked before anything is submitted, and the job is submitted with exactly the boxes that pass, so it queues for those and no others (booking).
The job ID is printed. With `--wait` this makes one foreground `fleet job wait` and collects; without it, write the ID in the outcome, end the turn, and run `collect` when woken (q3/remeasure/RUNBOOK.md).

`collect` writes one record per page, `<out_dir>/<slug>.json`, in the shape the spike's oracle has (`capture`, `worker`, `role`) plus a `history` block; a record that is not a good capture is not written, its page is named in `failed`, and the exit code is 1.
A page with a kept record (stamped, by a box that still passes) is left out of the job, so running the same command again submits only the pages that have none: that is the retry, the job service never re-captures a failed page.
The records name the box and `capture-host`, never an address (fleet_capture.py). `--summary` is written at collect.

`--static-base` captures the static copy of each address (`<base>/<slug>/index.html`, q3/remeasure/snapshot_all.py) instead of the address itself; the record is still named by the original address
(its file, its `staticOf`), so the split rule, a function of the address, is unchanged."""
import sys, os, json, re, hashlib, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'remeasure'))
import readback as rb
import fleet_capture as fc

MIN_BOXES = 3
REFUSED = {'--workers': 'the fleet job service finds each box\'s address itself: give the boxes by name, --boxes name,name,... (each with a passing read-back), and --label <the ticket key>',
           '--attempts': 'the job service never re-captures a failed page; run the same command again, and it submits only the pages that have no kept record',
           '--capture-script': 'there is no capture script: the entry point submits a fleet job (tests stub the `fleet` command instead)',
           **{flag: 'a replay capture loads the page\'s archive into the box\'s own replay server before the capture and keeps the server\'s log after it (q3/replay/capture_hooks.py): a hook between captures on one box, which a submitted job has no place for, '
                    'and running it in the caller\'s shell is what A11-246 removed. A replay server that serves every archive of a run at once is the follow-up that makes this a job'
              for flag in ('--replay-run', '--replay-ports', '--replay-readback')}}


def slug_of(url): return re.sub(r'[^a-z0-9]+', '-', url.lower().split('://', 1)[-1]).strip('-')[:70] + '-' + hashlib.sha256(url.encode()).hexdigest()[:8]


def history_block(box):
    """What the capture records about its set-up: the policy value read back, when, the probe that proved no history after it, and that the store was emptied."""
    return {'policy': {'name': rb.POLICY, 'value': box['policy']['value']}, 'policyReadAt': box['policy']['readAt'], 'storeEmptied': True, 'storeEmptiedAt': box['emptied']['at'],
            'probeAfter': {'capturedAt': box['after']['capturedAt'], 'visited': box['after']['visited']}}


def entries_of(corpus, static_base=None):
    entries = [{'url': e, 'role': None} if isinstance(e, str) else {'url': e['url'], 'role': e.get('role')} for e in corpus]
    for e in entries: e['address'] = f"{static_base.rstrip('/')}/{slug_of(e['url'])}/index.html" if static_base else e['url']
    return entries


def parse_boxes(arg):
    boxes = [b.strip() for b in arg.split(',') if b.strip()]
    bad = [b for b in boxes if b == 'ready' or not re.fullmatch(r'[A-Za-z][\w-]*', b)]
    if not boxes or bad: sys.exit(f'--boxes: box names separated by commas, e.g. a11y-worker-2,a11y-worker-3,a11y-worker-4 ({", ".join(bad) or "none given"}): each must have a passing read-back, so a count or `ready` is not given')
    return boxes


def usable_boxes(boxes, readback):
    """The boxes asked for that have a passing read-back; the run stops unless at least MIN_BOXES of them do, and says which were refused."""
    passed = set(rb.passed_workers(readback))
    refused = sorted(set(boxes) - passed)
    if refused: print('refused (no passing read-back):', ', '.join(refused), file=sys.stderr)
    use = sorted(set(boxes) & passed)
    if len(use) < MIN_BOXES: sys.exit(f'{len(use)} boxes have a passing read-back; the run needs at least {MIN_BOXES}')
    return use


def stamp(rec, entry, box):
    """The record with its role, the history block of the box that captured it and, for a static copy, the address it is a copy of."""
    rec['role'] = entry['role']; rec['history'] = history_block(box)
    if entry.get('address', entry['url']) != entry['url']: rec['staticOf'] = entry['url']
    return rec


def captured_ok(rec): return rec.get('status') == 200 and not (rec.get('capture') or {}).get('error') and bool((rec.get('capture') or {}).get('structure'))


def already_captured(dest, readback):
    """A record on disk is kept only if it is stamped and its worker still has a passing read-back; any other (an earlier, unclean run in the same directory) is captured again."""
    if not os.path.exists(dest): return False
    rec = rb.read_json(dest)
    return bool(rec.get('history')) and rec.get('worker') in rb.passed_workers(readback)


def summary_of(pending, started, ended, failed):
    return {'startedAt': started, 'endedAt': ended, 'workers': sorted(pending['boxes']), 'pages': len(pending['entries']), 'captured': len(pending['entries']) - len(failed), 'failed': sorted(failed)}


def finish(pending, summary):
    if pending.get('summary'): rb.write_json(pending['summary'], summary)
    print(summary)
    return 0 if not summary['failed'] else 1


def collect(out, job=None):
    """Write the job's records, stamped. A page whose capture is not a good one has no record, and is named in `failed`."""
    pending, manifest, found = fc.results(out, job)
    readback = rb.load(pending['readback']); by_address = {e['address']: e for e in pending['entries']}; kept = set()
    for r in found:
        entry, box = by_address[r.page], readback['workers'].get(r.record.get('worker'))
        ok = box is not None and captured_ok(r.record)
        if ok: fc.write_record(out, r.name, stamp(r.record, entry, box), overwrite=True); kept.add(entry['url'])
        print(slug_of(entry['url']), r.box, 'ok' if ok else f'failed: {(r.record.get("capture") or {}).get("error") or "no good capture"}', flush=True)
    failed = [e['url'] for e in pending['entries'] if e['url'] not in kept and not already_captured(os.path.join(out, slug_of(e['url']) + '.json'), readback)]
    return finish(pending, summary_of(pending, manifest['startedAt'], manifest['finishedAt'], failed))


def submit(a):
    readback = rb.load(a.readback)
    boxes = usable_boxes(parse_boxes(a.boxes), readback)
    entries = entries_of(rb.read_json(a.corpus), a.static_base)
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    todo = [e for e in entries if not already_captured(os.path.join(out, slug_of(e['url']) + '.json'), readback)]
    pending = {'readback': os.path.abspath(a.readback), 'summary': os.path.abspath(a.summary) if a.summary else None, 'boxes': boxes, 'entries': entries}
    if not todo:
        print('every page has a kept record: nothing to capture')
        now = rb.now(); sys.exit(finish(pending, summary_of(pending, now, now, [])))
    job = fc.submit([e['address'] for e in todo], ','.join(boxes), a.label)
    fc.write_pending(out, job, a.label, {e['address']: {'1': slug_of(e['url']) + '.json'} for e in todo}, **pending)
    if fc.follow(job, a.wait, f'python3 {os.path.abspath(__file__)} collect {out} {job}'): sys.exit(collect(out, job))


def main(argv):
    if argv[:1] == ['collect'] and 2 <= len(argv) <= 3: sys.exit(collect(*argv[1:]))
    for arg in argv:
        if arg.split('=')[0] in REFUSED: sys.exit(f'{arg.split("=")[0]}: {REFUSED[arg.split("=")[0]]}')
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0]); ap.add_argument('corpus'); ap.add_argument('out'); ap.add_argument('--boxes', required=True); ap.add_argument('--label', required=True); ap.add_argument('--readback', required=True)
    ap.add_argument('--summary'); ap.add_argument('--static-base'); ap.add_argument('--wait', metavar='DURATION')
    submit(ap.parse_args(argv))


if __name__ == '__main__': main(sys.argv[1:])
