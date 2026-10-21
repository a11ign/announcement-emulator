"""Capture the corpus again on boxes whose browser keeps no history (A11-155), and stamp every record with the read-back that allowed it.

    python corpus_capture.py <corpus.json> <out_dir> --workers name=url,name=url,... --readback <history-readback.json> [--summary <capture-run.json>] [--attempts 2]

`corpus.json` is q3/results/corpus.json (or a list of addresses): the same addresses as the spike, so the split rule (split.py, a function of the address) and the
comparison with the spike's figures hold. A worker with no passing read-back in the read-back file is refused, and so is a run with fewer than three. One record per page,
`<out_dir>/<slug>.json`, in the shape the spike's oracle has (`capture`, `worker`, `role`) plus a `history` block; a page already captured is skipped, so an interrupted run resumes.
The records name the worker and `capture-host`, never an address (fleet_capture.mjs)."""
import sys, os, json, re, hashlib, subprocess, threading, queue, argparse, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'remeasure'))
import readback as rb

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_WORKERS = 3


def slug_of(url): return re.sub(r'[^a-z0-9]+', '-', url.lower().split('://', 1)[-1]).strip('-')[:70] + '-' + hashlib.sha256(url.encode()).hexdigest()[:8]


def parse_workers(arg):
    out = {}
    for w in arg.strip().split(','):
        m = re.fullmatch(r'([\w-]+)=(https?://\S+)', w.strip())
        if not m: sys.exit('--workers: each worker is name=url, e.g. a11y-worker-2=http://host:8765')
        out[m.group(1)] = m.group(2)
    return out


def usable_workers(workers, readback):
    """The workers asked for that have a passing read-back; the run stops unless at least MIN_WORKERS of them do, and says which were refused."""
    passed = set(rb.passed_workers(readback))
    refused = sorted(set(workers) - passed)
    if refused: print('refused (no passing read-back):', ', '.join(refused), file=sys.stderr)
    use = {n: u for n, u in workers.items() if n in passed}
    if len(use) < MIN_WORKERS: sys.exit(f'{len(use)} workers have a passing read-back; the run needs at least {MIN_WORKERS}')
    return use


def history_block(box):
    """What the capture records about its set-up: the policy value read back, when, the probe that proved no history after it, and that the store was emptied."""
    return {'policy': {'name': rb.POLICY, 'value': box['policy']['value']}, 'policyReadAt': box['policy']['readAt'], 'storeEmptied': True, 'storeEmptiedAt': box['emptied']['at'],
            'probeAfter': {'capturedAt': box['after']['capturedAt'], 'visited': box['after']['visited']}}


def entries_of(corpus):
    return [{'url': e, 'role': None} if isinstance(e, str) else {'url': e['url'], 'role': e.get('role')} for e in corpus]


def stamp(path, entry, box):
    rec = rb.read_json(path)
    rec['role'] = entry['role']; rec['history'] = history_block(box)
    rb.write_json(path, rec)
    return rec


def captured_ok(rec): return rec.get('status') == 200 and not (rec.get('capture') or {}).get('error') and bool((rec.get('capture') or {}).get('structure'))


def capture_one(entry, name, url, box, dest, capture_script):
    """One page on one worker: True when a stamped record is at `dest`, else False with a reason."""
    tmp = dest + '.part'
    if os.path.exists(tmp): os.remove(tmp)
    try:
        done = subprocess.run(['node', capture_script, f'{name}={url}', entry['url'], tmp], capture_output=True, text=True, timeout=700)
        if os.path.exists(tmp) and captured_ok(rb.read_json(tmp)):
            stamp(tmp, entry, box); os.replace(tmp, dest)
            return True, 'ok'
        return False, 'failed ' + (done.stderr.strip()[-100:] or done.stdout.strip()[:80])
    except Exception as e:      # a timeout, an unreadable record, no node: this page fails and the worker goes on, rather than the thread dying with the page taken off the queue
        return False, f'failed {type(e).__name__}: {e}'
    finally:
        if os.path.exists(tmp): os.remove(tmp)


def already_captured(dest, readback):
    """A record on disk is kept only if it is stamped and its worker still has a passing read-back; any other (an earlier, unclean run in the same directory) is captured again."""
    if not os.path.exists(dest): return False
    rec = rb.read_json(dest)
    return bool(rec.get('history')) and rec.get('worker') in rb.passed_workers(readback)


def run(entries, workers, readback, out, capture_script, attempts=2, log=print):
    """Each worker takes pages off one queue until it is empty; a page that fails goes back for another attempt, up to `attempts`, and is then named in `failed`."""
    os.makedirs(out, exist_ok=True)
    todo = queue.Queue(); failed = []; done = []; lock = threading.Lock()
    for e in entries: todo.put((e, 1))

    def work(name, url):
        while True:
            try: entry, attempt = todo.get_nowait()
            except queue.Empty: return
            dest = os.path.join(out, slug_of(entry['url']) + '.json')
            ok, why = (True, 'already captured') if already_captured(dest, readback) else capture_one(entry, name, url, readback['workers'][name], dest, capture_script)
            with lock:
                if ok: done.append(entry['url'])
                elif attempt < attempts: todo.put((entry, attempt + 1))
                else: failed.append(entry['url'])
                log(slug_of(entry['url']), name, why, flush=True)

    started = datetime.datetime.now(datetime.timezone.utc)
    threads = [threading.Thread(target=work, args=(n, u)) for n, u in workers.items()]
    [t.start() for t in threads]; [t.join() for t in threads]
    return {'startedAt': started.strftime('%Y-%m-%dT%H:%M:%SZ'), 'endedAt': rb.now(), 'workers': sorted(workers), 'pages': len(entries), 'captured': len(done), 'failed': sorted(failed)}


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('corpus'); ap.add_argument('out'); ap.add_argument('--workers', required=True); ap.add_argument('--readback', required=True)
    ap.add_argument('--summary'); ap.add_argument('--attempts', type=int, default=2); ap.add_argument('--capture-script', default=os.path.join(HERE, 'fleet_capture.mjs'))
    a = ap.parse_args(argv)
    readback = rb.load(a.readback)
    workers = usable_workers(parse_workers(a.workers), readback)
    summary = run(entries_of(rb.read_json(a.corpus)), workers, readback, a.out, a.capture_script, a.attempts)
    if a.summary: rb.write_json(a.summary, summary)
    print(summary)
    sys.exit(0 if summary['captured'] == summary['pages'] and not summary['failed'] else 1)


if __name__ == '__main__': main(sys.argv[1:])
