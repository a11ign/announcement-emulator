import sys, time; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
def sort():
    nodes, f = d.s.dump(); return [n.get('sortDirection') for n in nodes if n.get('role')=='columnHeader' and n.get('name')=='Date' and n.get('sortDirection')]
print('start', sort())
print(d.s.eval("(()=>{const w=document.querySelector('iframe').contentWindow; return JSON.stringify({aria: typeof w.aria, grid: typeof (w.aria&&w.aria.Grid), err: w.__err||null, scripts:[...w.document.scripts].map(s=>s.src+':'+(s.src?'':'inline'))})})()"))
print(d.s.eval("(()=>{const w=document.querySelector('iframe').contentWindow; const sp=[...w.document.querySelectorAll('[role=button]')].find(x=>x.textContent.trim()=='Date'); sp.click(); return sp.parentElement.getAttribute('aria-sort')})()"))
time.sleep(1); print('after js click', sort())
d.close()
