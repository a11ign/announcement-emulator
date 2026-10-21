"""The read-back of each fleet box's browser history, kept in q3/results/remeasure/history-readback.json (A11-155).

    python readback.py probe  <readback.json> <worker> <stage> <capture-record.json>
    python readback.py policy <readback.json> <worker> <value> <evidence>
    python readback.py emptied <readback.json> <worker> <what was emptied>
    python readback.py restored <readback.json> <worker> <what the read-back showed>

`probe` reads a fleet_capture.mjs record of q3/remeasure/visited-probe.html and stores what it says about `visited`; the stage is `before` (the positive control:
it must read visited), `after` (the box passes only if nothing reads visited) or `after-run` (read again once the corpus is captured). `policy` stores the value the
Ansible policy task asserted. `emptied` stores that the history store was emptied; `restored` that the policy value was removed again, after which the box can no longer be captured from.
The values `policy`, `emptied` and `restored` store are what the operator read from the Ansible output; they are not parsed from it. `before` is taken after a first capture has visited the probe page (the first capture puts the page in the box's history, a later one reads it); it is recorded as read, whatever it read. Workers are named (`a11y-worker-2`), never addressed."""
import sys, os, json, datetime

POLICY = 'SavingBrowserHistoryDisabled'
STAGES = ('before', 'after', 'after-run')
PROBE_PAGE = 'visited-probe.html'
PROBE_LINKS = 2     # the probe page holds two links; a record that announces fewer did not read the page


def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def read_json(path):
    with open(path) as f: return json.load(f)


def write_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=1, sort_keys=True); f.write('\n')


def tokens(announcement): return [t.strip().lower() for t in str(announcement).split(',')]


def announced_visited(capture):
    """Whether any announcement of a capture, swept or spoken, carries the `visited` token."""
    swept = [a for channel in (capture.get('structure') or {}).values() for a in channel or []]
    return any('visited' in tokens(a) for a in swept + [str(x) for x in capture.get('transcript') or []])


def probe_outcome(record):
    """What a capture of the probe page says: whether it read the probe page (its address, both links), and whether it announced `visited`."""
    cap = record.get('capture') or {}
    links = list((cap.get('structure') or {}).get('links') or [])
    ok = record.get('status') == 200 and not cap.get('error') and str(cap.get('url', '')).endswith(PROBE_PAGE) and len(links) >= PROBE_LINKS
    return {'capturedAt': record.get('capturedAt'), 'links': len(links), 'read': ok, 'visited': announced_visited(cap)}


def stage_passes(stage, outcome):
    """`before` proves the probe can see history, so it must read visited; the other two prove the box keeps none."""
    if not outcome or not outcome.get('read'): return False
    return outcome['visited'] if stage == 'before' else not outcome['visited']


def at(stamp): return datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00')) if stamp else None


def in_order(box):
    """The readings were taken in the order the steps run: the probe that shows `visited` first, then the policy and the emptying, then the probe that must not."""
    before = [at((box.get('before') or {}).get('capturedAt'))] if box.get('before') else []
    times = before + [at((box.get('policy') or {}).get('readAt')), at((box.get('emptied') or {}).get('at')), at((box.get('after') or {}).get('capturedAt'))]
    return None not in times and times == sorted(times)


def box_passes(box):
    """May this box be captured from: the policy value read back is 1, the store was emptied, and the `after` probe read both links without `visited`, in that order
    (after the `before` probe, when one was taken), and the box has not been restored. Whether the `before` probe saw history is the positive control of the METHOD, which
    one box must show (`has_control`); it is not asked of every box, because Edge writes its history in batches and a box's second capture can come before the first is on disk."""
    pol = box.get('policy') or {}
    return (pol.get('name') == POLICY and pol.get('value') == 1 and bool(box.get('emptied')) and stage_passes('after', box.get('after'))
            and in_order(box) and not box.get('restored'))


def box_cleared(box):
    """The box's readings, as they stood before the fleet was put back: `restored` does not undo them."""
    return box_passes({**box, 'restored': None})


def has_control(box): return stage_passes('before', box.get('before'))


def box_held(box):
    """Did the box stay clean for the whole run: it passed, and the probe read again once the corpus was captured (`after-run`) still shows no history. Restoring the fleet afterwards does not undo it."""
    after_run, after = box.get('after-run') or {}, box.get('after') or {}
    put_back = at((box.get('restored') or {}).get('at'))
    return (box_cleared(box) and stage_passes('after-run', box.get('after-run')) and at(after_run.get('capturedAt')) > at(after.get('capturedAt'))
            and (put_back is None or put_back > at(after_run.get('capturedAt'))))


def load(path):
    return read_json(path) if os.path.exists(path) else {'policy': POLICY, 'workers': {}}


def save(path, data):
    for box in data['workers'].values(): box['passed'] = box_passes(box)
    write_json(path, data)


def cleared_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_cleared(box))
def passed_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_passes(box))
def control_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if has_control(box))
def held_workers(data): return sorted(w for w, box in data.get('workers', {}).items() if box_held(box))


def record_probe(box, worker, stage, record_path):
    if stage not in STAGES: sys.exit(f'stage is one of {STAGES}')
    record = read_json(record_path)
    if record.get('worker') != worker: sys.exit(f'{record_path} was captured by another worker than {worker}')
    box[stage] = probe_outcome(record)
    print(worker, stage, box[stage], 'as expected' if stage_passes(stage, box[stage]) else 'NOT AS REQUIRED')


def record_policy(box, value, evidence): box['policy'] = {'name': POLICY, 'value': int(value), 'readAt': now(), 'evidence': evidence}


def record_emptied(box, what): box['emptied'] = {'at': now(), 'what': what}


def record_restored(box, evidence): box['restored'] = {'at': now(), 'evidence': evidence}


def main(argv):
    if len(argv) < 4 or argv[0] not in ('probe', 'policy', 'emptied', 'restored'): sys.exit(__doc__)
    verb, path, worker, *rest = argv
    data = load(path); box = data['workers'].setdefault(worker, {})
    {'probe': record_probe, 'policy': record_policy, 'emptied': record_emptied, 'restored': record_restored}[verb](*(([box, worker] if verb == 'probe' else [box]) + rest))
    save(path, data)
    print(worker, 'passes' if data['workers'][worker]['passed'] else 'does not pass yet')


if __name__ == '__main__': main(sys.argv[1:])
