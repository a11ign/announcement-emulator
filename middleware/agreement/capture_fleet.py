"""Capture each sample page twice on the fleet, through the route A11-166 used (q3/fleet_capture.mjs), on boxes that agree on every version (A11-208, question 5).

    python3 capture_fleet.py <pages.json> <out dir> --workers a11y-worker-13=http://host:8765,a11y-worker-14=http://host:8765,a11y-worker-16=http://host:8765

The two captures of a page go to two different boxes (the first to box i mod n, the second to box i+1 mod n), one capture at a time on each box. Nothing on a box is changed: the request is the
worker's own /capture, and the records name the worker and never its address. A record that exists is not captured again.
"""
import json, os, queue, subprocess, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
FLEET_CAPTURE = os.path.join(HERE, '..', '..', 'q3', 'fleet_capture.mjs')
sys.path.insert(0, HERE)


def plan(addresses, workers):
    """[(address, k, worker)] with the two captures of an address on two boxes."""
    n = len(workers)
    return [(a, k, workers[(i + k - 1) % n]) for i, a in enumerate(addresses) for k in (1, 2)]


def main(argv):
    pages_file, out = argv[0], argv[1]
    workers = argv[argv.index('--workers') + 1].split(',')
    if not all('=http' in w for w in workers): sys.exit('--workers: each is name=url, e.g. a11y-worker-13=http://host:8765')
    with open(pages_file) as f: addresses = [p['url'] for p in json.load(f)['sample']]
    from measure import slug
    os.makedirs(out, exist_ok=True)
    queues = {w: queue.Queue() for w in workers}
    for address, k, w in plan(addresses, workers): queues[w].put((address, k))

    def work(w):
        while True:
            try: address, k = queues[w].get_nowait()
            except queue.Empty: return
            dest = os.path.join(out, f'{slug(address)}.f{k}.json')
            if os.path.exists(dest): continue
            r = subprocess.run(['node', FLEET_CAPTURE, w, address, dest, '600', '--typing-dialog'], capture_output=True, text=True, timeout=1500)
            print(w.split('=')[0], k, address, r.stdout.strip()[:100], r.stderr.strip()[-100:], flush=True)

    threads = [threading.Thread(target=work, args=(w,)) for w in workers]
    for t in threads: t.start()
    for t in threads: t.join()
    print('done')


if __name__ == '__main__': main(sys.argv[1:])
