import sys, time; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
def show(tag):
    nodes, f = d.s.dump()
    for n in nodes:
        if n.get('role') == 'button' and n.get('name') == 'Date': print(tag, n['ix'], n.get('defaultActionVerb'), n.get('standardActions'), n.get('state'), n.get('location')); return n['ix']
ix = show('before')
d.s.scroll(ix); time.sleep(1.5)
ix2 = show('after scroll')
d.s.focus(ix2); time.sleep(1)
show('after focus')
d.close()
