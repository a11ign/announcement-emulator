"""What of a figure is committed: its tables, and each miss with the fleet's string, the prediction and the address. Not the units that agreed: the fleet's lists of a third-party page are not committed.

    python3 export_misses.py <agreement.json from measure.py --out> <out dir>
"""
import collections, json, os, sys


def export(agreement, out):
    rows = [r for r in agreement['rows'] if r['kind'] == 'fleet-vs-passive']
    misses = [{k: r[k] for k in ('address', 'channel', 'i', 'expected', 'predicted', 'class', 'shape', 'stable') if k in r} for r in rows if not r['ok']]
    counts = collections.Counter((r['channel'], bool(r['ok'])) for r in rows)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'misses.json'), 'w') as f: json.dump({'status': agreement['status'], 'units': {ch: [counts[(ch, True)], counts[(ch, True)] + counts[(ch, False)]] for ch in sorted({c for c, _ in counts})}, 'misses': misses}, f, indent=1, ensure_ascii=False)
    return len(misses)


if __name__ == '__main__':
    with open(sys.argv[1]) as f: print(export(json.load(f), sys.argv[2]), 'misses')
