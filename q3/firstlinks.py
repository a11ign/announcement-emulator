"""The first link of each page of the corpus, in document order, for make_history.py: python firstlinks.py <oracle_dir> <out.json> [--jobs 8]
Only addresses come out; no announcement of any page is produced or read."""
import sys, os, json, glob, concurrent.futures as cf, queue
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
oracle, out = sys.argv[1:3]; jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 8
urls = []
for f in sorted(glob.glob(os.path.join(oracle, '*.json'))):
    try: urls.append(json.load(open(f))['capture']['url'])
    except Exception: pass
def one(args):
    port, url = args
    from livepage import LivePage
    try:
        d = LivePage(url=url, port=port)
        fl = next((pn.raw.get('url') for ix, pn in sorted(d.world.by_ix.items()) if pn.raw.get('role') == 'link' and pn.raw.get('url')), None); d.close(); return url, fl
    except BaseException as e: return url, None
# one process per page: LivePage owns NVDA's global state, so each page gets its own interpreter
if len(sys.argv) > 3 and sys.argv[3] == '--child':
    print(json.dumps(one((int(sys.argv[4]), sys.argv[5])))); sys.exit(0)
import subprocess
q = queue.Queue(); [q.put(9400 + 2 * i) for i in range(jobs)]
def run(url):
    port = q.get()
    try:
        r = subprocess.run([sys.executable, __file__, oracle, out, '--child', str(port), url], capture_output=True, text=True, timeout=300)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return [url, None]
    finally: q.put(port)
with cf.ThreadPoolExecutor(jobs) as ex: res = list(ex.map(run, urls))
json.dump({u: fl for u, fl in res}, open(out, 'w'), indent=1); print(sum(1 for _, fl in res if fl), 'of', len(res), 'first links')
