import sys; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<button>plain</button><iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
nodes, f = d.s.dump()
for n in nodes:
    if n.get('role') in ('button',) and n.get('name') in ('plain','Date'): print(n['role'], n.get('name'), n.get('defaultActionVerb'), n.get('standardActions'), n.get('state'))
print(d.s.eval("(()=>{const f=document.querySelector('iframe'); const w=f.contentWindow; const bs=[...w.document.querySelectorAll('button')].filter(x=>x.textContent.trim()=='Date'); return JSON.stringify({vp:[innerWidth,innerHeight], fr:f.getBoundingClientRect().toJSON(), btns: bs.map(b=>[b.getBoundingClientRect().toJSON(), getComputedStyle? w.getComputedStyle(b).display : 0])})})()"))
print('--- after scrolling the iframe to its last button')
d.s.eval("(()=>{const f=document.querySelector('iframe'); f.scrollIntoView(); const w=f.contentWindow; const b=[...w.document.querySelectorAll('button')].find(x=>x.textContent.trim()=='Date'); b.scrollIntoView(); return 1})()")
import time; time.sleep(1)
nodes, f = d.s.dump()
for n in nodes:
    if n.get('role') in ('button',) and n.get('name') in ('Date',): print(n['role'], n.get('name'), n.get('defaultActionVerb'), n.get('standardActions'), n.get('state'))
d.close()
