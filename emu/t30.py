import sys, time; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
def show(tag):
    nodes, f = d.s.dump()
    byix = {n['ix']: n for n in nodes}
    fn = byix.get(f)
    print(tag, 'focus', f, fn and (fn.get('role'), fn.get('name')))
    for n in nodes:
        if n.get('role') == 'columnHeader' and n.get('name') == 'Date' and n.get('sortDirection'): print('  header', n['ix'], n.get('sortDirection'))
    return nodes
nodes = show('before')
b = next(n for n in nodes if n.get('role')=='button' and n.get('name')=='Date')
d.s.scroll(b['ix']); time.sleep(1)
nodes = show('after scroll'); b = next(n for n in nodes if n.get('role')=='button' and n.get('name')=='Date')
loc = b['location']; x, y = loc['left']+loc['width']//2, loc['top']+loc['height']//2; print('click at', x, y)
off = next(n for n in nodes if n.get('role')=='rootWebArea')['location']; d.s.click(x-off['left'], y-off['top']); time.sleep(1.5)
show('after click')
d.close()
