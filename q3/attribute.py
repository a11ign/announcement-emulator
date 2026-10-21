"""Which misses at the freeze were emulator bugs, shown rather than argued: a miss in the freeze run that is agreed in the run after the fixes, on a page comparable in both.

    python attribute.py <misses-freeze.json> <misses-post.json> [<out.json>]

Prints the freeze misses on the top-10 shapes by cause, with `unexplained` split into `bug-fixed` (agreed after the fixes) and what is left."""
import sys, json, collections
fz, po = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
status_post = {p['url']: p['status'] for p in po['pages']}
still = {(m['url'], m['channel'], m['expected']) for m in po['misses']}
out = []
for m in fz['misses']:
    if m['class'] == 'unexplained' and status_post.get(m['url']) == 'comparable' and (m['url'], m['channel'], m['expected']) not in still:
        toks = [t.strip() for t in m['expected'].split(',')]; ptoks = [t.strip() for t in (m['predicted'] or '').split(',')] if m['predicted'] else []
        m = {**m, 'class': 'bug-fixed', 'fix': 'toggle button state' if 'checked' in ptoks and 'checked' not in toks else 'lazily loaded content'}
    out.append(m)
top = set(fz['top'])
gate = [m for m in out if ' + '.join(m['shape']) in top and m['channel'] != 'frames']      # the shape ranking reads the channels of the fleet's script, not frames
print('misses on the top-10 shapes at the freeze:', len(gate), dict(collections.Counter(m['class'] for m in gate)))
print('all channels:', len(out), dict(collections.Counter(m['class'] for m in out)))
for m in gate:
    if m['class'] == 'unexplained': print('  left:', m['url'][8:60], m['channel'], repr(m['expected'][:80]), '->', repr((m['predicted'] or '')[:80]))
print('fixes:', dict(collections.Counter(m.get('fix') for m in out if m['class'] == 'bug-fixed')))
if len(sys.argv) > 3: json.dump(out, open(sys.argv[3], 'w'), indent=1, ensure_ascii=False)
