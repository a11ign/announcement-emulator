import sys, os, json
os.environ.setdefault('EMU_NVDA_INI', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvda-fleet.ini'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver
d = LivePage(url=sys.argv[1], port=8895)
needle = sys.argv[2]
for ix, pn in sorted(d.world.by_ix.items()):
    r = pn.raw
    if needle in (r.get('name') or '') and r.get('role') != 'staticText':
        def show(p, dep=0):
            q = p.raw; print('  ' * dep, p.ix, q.get('role'), q.get('htmlTag'), repr((q.get('name') or '')[:40]), 'display=', q.get('display'), 'cls=', (q.get('className') or '')[:40], 'inv' if q.get('state', {}).get('invisible') else '')
            for k in p.kids: show(k, dep + 1)
        show(pn); break
d.close()
