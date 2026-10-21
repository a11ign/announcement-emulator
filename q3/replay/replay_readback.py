"""The read-back of each fleet box's replay set-up, kept in q3/results/replay/replay-readback.json (A11-165).

    python replay_readback.py init <file> <run id> <thumbprint> <marker>
    python replay_readback.py proxy <file> <worker> <proxy server> <evidence>
    python replay_readback.py certificate <file> <worker> <evidence>
    python replay_readback.py probe <file> <worker> <stage> <capture-record.json>        stage: on | after-run | off
    python replay_readback.py removed <file> <worker> <evidence>
    python replay_readback.py status <file> <worker> <state> <evidence>

The three readings of the set-up (`proxy`, `certificate`, `removed`, `status`) are what the operator read from the play's own assertion and from `fleet:status`; they are stored, not parsed. `probe` reads a fleet_capture.mjs record of the
archive-only page (make_probe.py) and stores whether its heading is the run's marker. Before the corpus a box must read the marker (`on`: it is behind the replay server), and again after the corpus (`after-run`: it stayed);
after the restore it must not (`off`: the page is nowhere else), with the proxy values and the certificate gone and `fleet:status` `ready`. Workers are named, never addressed."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'remeasure'))
import readback as rb

STAGES = ('on', 'after-run', 'off')


def words(text):
    """What a screen reader says, to compare by: lower-case words, punctuation and hyphens as spaces (NVDA says `6613d43c` as `6613d 43c`, so a marker is made of plain words)."""
    return ' '.join(re.findall(r'[a-z0-9]+', str(text).lower()))


def read_marker(record, marker):
    """Whether a capture of the probe page read the run's marker as its heading, and what it read otherwise (status, error)."""
    cap = record.get('capture') or {}
    headings = list((cap.get('structure') or {}).get('headings') or [])
    ok = record.get('status') == 200 and not cap.get('error')
    return {'capturedAt': record.get('capturedAt'), 'read': ok and any(f' {words(marker)} ' in f' {words(h)} ' for h in headings), 'headings': len(headings)}


def stage_passes(stage, outcome):
    """`on` and `after-run` must have read the marker; `off` must not have."""
    if not outcome: return False
    return outcome['read'] if stage in ('on', 'after-run') else not outcome['read']


def in_order(box):
    """The proxy values were read, then the certificate, then the probe that read the marker."""
    times = [rb.at((box.get('proxy') or {}).get('readAt')), rb.at((box.get('certificate') or {}).get('readAt')), rb.at((box.get('on') or {}).get('capturedAt'))]
    return None not in times and times == sorted(times)


def box_passes(box):
    """May this box be captured from behind the replay server: the proxy and the certificate read back, and the probe read the marker, in that order, and the box is not restored."""
    return bool((box.get('proxy') or {}).get('server')) and bool(box.get('certificate')) and stage_passes('on', box.get('on')) and in_order(box) and not box.get('restored')


def box_held(box):
    """The box stayed behind the server for the whole run: it passed, and the probe read after the corpus still read the marker (later than the first), before any restore."""
    again, first, put_back = box.get('after-run') or {}, box.get('on') or {}, rb.at((box.get('restored') or {}).get('at'))
    return (box_passes({**box, 'restored': None}) and stage_passes('after-run', box.get('after-run')) and rb.at(again.get('capturedAt')) > rb.at(first.get('capturedAt'))
            and (put_back is None or put_back > rb.at(again.get('capturedAt'))))


def box_restored(box):
    """After the run: the values and the certificate are gone, the probe no longer reaches the archive, and the box reads `ready`, in that order, after the run's last probe."""
    gone, off, status = box.get('removed') or {}, box.get('off'), box.get('status') or {}
    times = [rb.at((box.get('after-run') or {}).get('capturedAt')), rb.at(gone.get('at')), rb.at((off or {}).get('capturedAt')), rb.at(status.get('at'))]
    return bool(gone) and stage_passes('off', off) and status.get('state') == 'ready' and None not in times and times == sorted(times)


def load(path):
    return rb.read_json(path) if os.path.exists(path) else {'workers': {}}


def save(path, data):
    for box in data['workers'].values(): box['passed'] = box_passes(box); box['heldRun'] = box_held(box); box['restoredOk'] = box_restored(box)
    rb.write_json(path, data)


def passed_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_passes(box))
def held_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_held(box))
def restored_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_restored(box))


def main(argv):
    if len(argv) < 3 or argv[0] not in ('init', 'proxy', 'certificate', 'probe', 'removed', 'status'): sys.exit(__doc__)
    verb, path, *rest = argv
    data = load(path)
    if verb == 'init':
        run_id, thumbprint, marker = rest
        data.update({'runId': run_id, 'thumbprint': thumbprint, 'marker': marker, 'probeAddress': 'https://replay-probe.test/'}); save(path, data); return
    worker, *rest = rest; box = data['workers'].setdefault(worker, {})
    if verb == 'proxy': box['proxy'] = {'server': rest[0], 'readAt': rb.now(), 'evidence': rest[1]}
    elif verb == 'certificate': box['certificate'] = {'thumbprint': data['thumbprint'], 'readAt': rb.now(), 'evidence': rest[0]}
    elif verb == 'removed': box['removed'] = {'at': rb.now(), 'evidence': rest[0]}
    elif verb == 'status': box['status'] = {'state': rest[0], 'at': rb.now(), 'evidence': rest[1]}
    else:
        stage, record_path = rest
        if stage not in STAGES: sys.exit(f'stage is one of {STAGES}')
        record = rb.read_json(record_path)
        if record.get('worker') != worker: sys.exit(f'{record_path} was captured by another worker than {worker}')
        box[stage] = read_marker(record, data['marker'])
        print(worker, stage, box[stage], 'as expected' if stage_passes(stage, box[stage]) else 'NOT AS REQUIRED')
    if verb == 'removed': box['restored'] = {'at': box['removed']['at']}
    save(path, data)
    print(worker, 'passes' if data['workers'][worker]['passed'] else 'does not pass yet', '| restored' if data['workers'][worker]['restoredOk'] else '')


if __name__ == '__main__': main(sys.argv[1:])
