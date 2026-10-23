"""One oracle directory, read as two (A11-166): the run captures batch 2 and the earlier 60 held pages together, and measure.py reads one directory at a time.

    python views.py <oracle dir> <run list.json> <out dir>

`<out dir>/batch2` and `<out dir>/old60` hold a symbolic link to each record of the oracle, by the run list's `set` of the page's address. Nothing is copied or changed."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(Q3, 'remeasure'))
import readback as rb


def make(oracle, run_list, out):
    sets = {e['url']: e['set'] for e in run_list}; counts = {}
    for name in sorted(os.listdir(oracle)):
        if not name.endswith('.json'): continue
        url = (rb.read_json(os.path.join(oracle, name)).get('capture') or {}).get('url')
        if url not in sets: continue      # a record of an address that is not in the run: left out, and `check.py oracle` names it
        os.makedirs(os.path.join(out, sets[url]), exist_ok=True); link = os.path.join(out, sets[url], name)
        if os.path.lexists(link): os.remove(link)
        os.symlink(os.path.abspath(os.path.join(oracle, name)), link); counts[sets[url]] = counts.get(sets[url], 0) + 1
    return counts


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    print(make(sys.argv[1], rb.read_json(sys.argv[2]), sys.argv[3]))
