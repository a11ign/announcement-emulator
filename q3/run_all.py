"""Run the emulator over every page of an oracle directory, twice per page, several pages at once.

    python run_all.py <oracle_dir> <out_dir> [--split dev|held|all] [--jobs 8] [--runs 2] [--only substring]

Each page is `<out_dir>/<slug>.run<k>.json` (emulate.py's output). A page already done is skipped, so an interrupted batch resumes."""
import sys, os, json, glob, subprocess, argparse, time, queue, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split import split_of

ap = argparse.ArgumentParser(); ap.add_argument('oracle'); ap.add_argument('out'); ap.add_argument('--split', default='dev', choices=['dev', 'held', 'all'])
ap.add_argument('--jobs', type=int, default=8); ap.add_argument('--runs', type=int, default=2); ap.add_argument('--only', default=''); ap.add_argument('--port-base', type=int, default=9100)
ap.add_argument('--timeout', type=int, default=900); ap.add_argument('--history'); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
pages = []
for f in sorted(glob.glob(os.path.join(a.oracle, '*.json'))):
    try: rec = json.load(open(f))
    except Exception: continue
    url = (rec.get('capture') or {}).get('url')
    if not url or a.only not in url: continue
    if a.split != 'all' and split_of(url) != a.split: continue
    pages.append((os.path.basename(f)[:-5], url))
print(f'{len(pages)} pages, split={a.split}, {a.runs} runs each, {a.jobs} at a time', flush=True)

def one(slot, slug, url):
    for k in range(1, a.runs + 1):
        out = os.path.join(a.out, f'{slug}.run{k}.json')
        if os.path.exists(out): continue
        t = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join(here, 'emulate.py'), url, out + '.part', '--port', str(a.port_base + 2 * slot)] + (['--history', a.history] if a.history else []), timeout=a.timeout,
                               capture_output=True, text=True)
            if os.path.exists(out + '.part'): os.replace(out + '.part', out)
            fault = json.load(open(out)).get('fault') if os.path.exists(out) else 'no output'
        except subprocess.TimeoutExpired:
            fault = f'timeout {a.timeout}s'; json.dump({'url': url, 'fault': fault}, open(out, 'w'))
        print(f'  slot {slot} {slug} run{k} {round(time.time() - t)}s {fault or "ok"}', flush=True)

free = queue.Queue()
for s in range(a.jobs): free.put(s)
def job(p):
    s = free.get()
    try: one(s, *p)
    finally: free.put(s)
with cf.ThreadPoolExecutor(a.jobs) as ex: list(ex.map(job, pages))
print('done', flush=True)
