"""The addresses the fleet's browsers have visited, as far as the worker's own behaviour says: every page of the corpus (each box has captured them) and the
first link of each page (the route-change probe follows it, `probeNavigation` is on for real pages). Written for emulate.py --history.

    python make_history.py <oracle_dir> <firstlinks.json> <out.json>"""
import sys, json, glob, os
oracle, fl, out = sys.argv[1:4]
first = json.load(open(fl)); urls = set()
for f in glob.glob(os.path.join(oracle, '*.json')):
    try: u = json.load(open(f))['capture']['url']
    except Exception: continue
    urls.add(u)
    if first.get(u, '') and first[u].startswith('http'): urls.add(first[u].split('#')[0])
json.dump(sorted(urls), open(out, 'w'), indent=0)
print(len(urls), 'addresses')
