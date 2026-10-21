"""Capture a sample of the static synthetic pages on the fleet (the control: no page drift) - python control_capture.py <pages_dir> <host_url> <out_dir> <n> --workers <file>
`--workers` is a file of `name=url` pairs separated by commas (`a11y-worker-2=http://host:8765,...`): the records name the worker and `capture-host`, never an address.
The sample is every k-th file of the sorted list of good/bad pages, so it is fixed by n alone."""
import sys, os, json, glob, subprocess, threading, queue
pages_dir, base, out, n = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3], int(sys.argv[4])
workers = open(sys.argv[sys.argv.index('--workers') + 1]).read().strip().split(',')
if not all('=http' in w for w in workers): sys.exit('--workers: each worker is name=url, e.g. a11y-worker-2=http://host:8765')
files = sorted(glob.glob(os.path.join(pages_dir, '*', '*.html')))
step = max(1, len(files) // n); sample = files[::step][:n]
os.makedirs(out, exist_ok=True)
q = queue.Queue()
for f in sample: q.put(f)
here = os.path.dirname(os.path.abspath(__file__))
def work(w):
    while True:
        try: f = q.get_nowait()
        except queue.Empty: return
        rel = os.path.relpath(f, pages_dir); slug = rel.replace('/', '__')[:-5]
        dest = os.path.join(out, slug + '.json')
        if os.path.exists(dest): continue
        r = subprocess.run(['node', os.path.join(here, 'fleet_capture.mjs'), w, f'{base}/{rel}', dest], capture_output=True, text=True, timeout=700)
        print(slug, r.stdout.strip()[:80], r.stderr.strip()[-100:], flush=True)
ts = [threading.Thread(target=work, args=(w,)) for w in workers]
[t.start() for t in ts]; [t.join() for t in ts]; print('done')
