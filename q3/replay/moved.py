"""What moved between two readings of the held-out half (A11-165): the pages whose comparability changed, the Gate figure and the misses by class, and for each page that stopped being comparable what the fleet's capture of it holds.

    python moved.py <before misses-*.json> <after misses-*.json> <after oracle dir> <out.json>

`before` and `after` are measure.py --json outputs (the drift-free reading at the freeze and the scripted replay at the freeze). For a page whose status changed the entry gives both statuses and, from the after oracle's record, the
number of announcements the fleet swept in each channel and the first lines it read: a page whose fleet capture holds a handful of lines and no links is a page whose quick navigation a dialog sealed."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'remeasure'))
import corpus_capture as cc
import readback as rb


def status_class(status): return status.split(':')[0]


def moved_pages(before, after):
    """The pages (by address) whose status differs: {url: (before, after)}. A page in one reading only counts as moved."""
    b = {p['url']: p['status'] for p in before['pages']}; a = {p['url']: p['status'] for p in after['pages']}
    return {u: (b.get(u), a.get(u)) for u in sorted(set(a) | set(b)) if b.get(u) != a.get(u)}


def fleet_view(oracle_dir, url):
    path = os.path.join(oracle_dir, cc.slug_of(url) + '.json')
    if not os.path.exists(path): return None
    cap = rb.read_json(path)['capture']
    return {'swept': {k: len(v) for k, v in (cap.get('structure') or {}).items()}, 'transcriptLines': len(cap.get('transcript') or []), 'firstLines': list(cap.get('transcript') or [])[:3]}


def summary(measure):
    return {'gate': measure['gate'], 'pages': dict(collections.Counter(status_class(p['status']) for p in measure['pages']))}


def build(before, after, oracle_dir):
    moves = moved_pages(before, after)
    return {'before': summary(before), 'after': summary(after),
            'moved': [{'url': u, 'before': b, 'after': a, **({'fleet': fleet_view(oracle_dir, u)} if a and status_class(a) != 'comparable' else {})} for u, (b, a) in moves.items()]}


if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    rb.write_json(sys.argv[4], build(rb.read_json(sys.argv[1]), rb.read_json(sys.argv[2]), sys.argv[3]))
