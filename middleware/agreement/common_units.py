"""Two readings of A11-229 over the units both compare (a reading drops a page that is not comparable, so the readings' own totals are over different units). Read after the frozen figure, to put macOS beside this host's DevTools reading on the same units.

    python3 common_units.py <work dir> <reading> <reading> [...]      each reading's agreed units of those that every named reading has

It reads `<work>/<reading>/agreement.json` (what `measure.py --out` wrote) and changes no figure."""
import collections, json, os, sys


def units(path):
    with open(path) as f: rows = json.load(f)['rows']
    return {(r['address'], r['channel'], r['i']): r for r in rows if r['kind'] == 'fleet-vs-passive'}


def common(readings):
    """{reading: [agreed, units]} over the units every reading has, and {address: units} of the common set."""
    shared = set.intersection(*(set(r) for r in readings.values()))
    return {n: [sum(r[k]['ok'] for k in shared), len(shared)] for n, r in readings.items()}, collections.Counter(k[0] for k in shared)


def main(argv):
    work, names = argv[0], argv[1:]
    out, pages = common({n: units(os.path.join(work, n, 'agreement.json')) for n in names})
    for n, (ok, tot) in out.items(): print(f'{n:<20} {ok:>5} of {tot:<5} = {100 * ok / tot:.1f}%')
    for a, n in pages.items(): print(f'  {n:>4} units  {a}')


if __name__ == '__main__': main(sys.argv[1:])
