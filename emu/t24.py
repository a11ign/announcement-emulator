import sys; sys.path.insert(0,'.')
import boot, live, collections
html = '<iframe src="/aria/content/patterns/treegrid/examples/treegrid-1.html"></iframe>'
d = live.LiveDoc(html)
nodes, f = d.s.dump()
c = collections.Counter((n.get('role'), n.get('defaultActionVerb')) for n in nodes)
for k,v in sorted(c.items(), key=lambda x:-x[1])[:25]: print(v, k)
for n in nodes:
    if n.get('role') in ('treeGrid','row') : print(n['role'], n.get('defaultActionVerb'), n.get('name'), n.get('restriction'), n.get('state',{}).get('expanded'), n.get('hierarchicalLevel'))
d.close()
