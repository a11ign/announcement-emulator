import sys, time; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
nodes, f = d.s.dump()
for n in nodes:
    if n.get('role') in ('rootWebArea','iframe') : print(n['ix'], n['role'], n.get('location'), n.get('scrollX'), n.get('scrollY'), n.get('scrollYMax'))
b = next(n for n in nodes if n.get('role')=='button' and n.get('name')=='Date'); print('button', b['location'], b.get('unclippedLocation'))
d.s.scroll(b['ix']); time.sleep(1)
nodes, f = d.s.dump()
for n in nodes:
    if n.get('role') in ('rootWebArea','iframe') : print(n['ix'], n['role'], n.get('location'), n.get('scrollX'), n.get('scrollY'))
b = next(n for n in nodes if n.get('role')=='button' and n.get('name')=='Date'); print('button', b['location'], b.get('unclippedLocation'))
print(d.s.eval("(()=>{const w=document.querySelector('iframe').contentWindow; const sp=[...w.document.querySelectorAll('[role=button]')].find(x=>x.textContent.trim()=='Date'); const r=sp.getBoundingClientRect(); return JSON.stringify({r:r.toJSON(), sy:w.scrollY, ih:w.innerHeight})})()"))
d.close()
