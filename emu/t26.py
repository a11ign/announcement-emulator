import sys; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
nodes, f = d.s.dump()
for n in nodes:
    if n.get('role') in ('columnHeader','rowHeader') and (n.get('name') or '') in ('Date','Transactions'): print(n['role'], n.get('name'), {k:v for k,v in n.items() if 'ort' in k})
d.close()
