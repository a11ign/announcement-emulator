"""The read-back of each fleet box's browser history, kept in q3/results/remeasure/history-readback.json (A11-155).

    python readback.py probe  <readback.json> <worker> <stage> <capture-record.json>
    python readback.py policy <readback.json> <worker> <value> <evidence>
    python readback.py emptied <readback.json> <worker> <what was emptied>

`probe` reads a fleet_capture.mjs record of q3/remeasure/visited-probe.html and stores what it says about `visited`; the stage is `before` (the positive control:
it must read visited), `after` (the box passes only if nothing reads visited) or `after-run` (read again once the corpus is captured). `policy` stores the value the
Ansible policy task asserted. `emptied` stores that the history store was emptied. Workers are named (`a11y-worker-2`), never addressed."""
import sys, os, json, datetime

POLICY = 'SavingBrowserHistoryDisabled'
STAGES = ('before', 'after', 'after-run')
PROBE_LINKS = 2     # visited-probe.html holds two links; a record that announces fewer did not read the page


def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def read_json(path):
    with open(path) as f: return json.load(f)


def write_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=1, sort_keys=True); f.write('\n')


def tokens(announcement): return [t.strip().lower() for t in str(announcement).split(',')]


def probe_outcome(record):
    """What a probe capture says: how many link announcements it holds, and whether any of the page's announcements, swept or spoken, carries the word `visited`."""
    cap = record.get('capture') or {}
    links = list((cap.get('structure') or {}).get('links') or [])
    spoken = [str(x) for x in cap.get('transcript') or []]
    ok = record.get('status') == 200 and not cap.get('error') and len(links) >= PROBE_LINKS
    return {'capturedAt': record.get('capturedAt'), 'links': len(links), 'read': ok, 'visited': any('visited' in tokens(x) for x in links + spoken)}


def stage_passes(stage, outcome):
    """`before` proves the probe can see history, so it must read visited; the other two prove the box keeps none."""
    if not outcome or not outcome.get('read'): return False
    return outcome['visited'] if stage == 'before' else not outcome['visited']


def box_passes(box):
    """A box passes when the policy value read back is 1, its store was emptied, and its `after` probe read the page without visited. `after-run`, when taken, must agree."""
    pol = box.get('policy') or {}
    after_run = box.get('after-run')
    return (pol.get('name') == POLICY and pol.get('value') == 1 and bool(box.get('emptied')) and stage_passes('after', box.get('after'))
            and (after_run is None or stage_passes('after-run', after_run)))


def load(path):
    return read_json(path) if os.path.exists(path) else {'policy': POLICY, 'workers': {}}


def save(path, data):
    for box in data['workers'].values(): box['passed'] = box_passes(box)
    write_json(path, data)


def passed_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_passes(box))


def main(argv):
    if len(argv) < 4 or argv[0] not in ('probe', 'policy', 'emptied'): sys.exit(__doc__)
    verb, path, worker = argv[:3]
    data = load(path); box = data['workers'].setdefault(worker, {})
    if verb == 'probe':
        stage, rec = argv[3], argv[4]
        if stage not in STAGES: sys.exit(f'stage is one of {STAGES}')
        record = read_json(rec)
        if record.get('worker') != worker: sys.exit(f'{rec} was captured by another worker than {worker}')
        outcome = probe_outcome(record)
        box[stage] = outcome
        print(worker, stage, outcome, 'as expected' if stage_passes(stage, outcome) else 'NOT AS REQUIRED')
    elif verb == 'policy':
        box['policy'] = {'name': POLICY, 'value': int(argv[3]), 'readAt': now(), 'evidence': argv[4]}
    else:
        box['emptied'] = {'at': now(), 'what': argv[3]}
    save(path, data)
    print(worker, 'passes' if data['workers'][worker]['passed'] else 'does not pass yet')


if __name__ == '__main__': main(sys.argv[1:])
