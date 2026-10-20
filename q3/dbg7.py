import sys, os, json
os.environ.setdefault('EMU_NVDA_INI', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvda-fleet.ini'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver
url, needle = sys.argv[1], sys.argv[2]
d = LivePage(url=url, port=8871)
for ix, pn in sorted(d.world.by_ix.items()):
    r = pn.raw
    if needle.lower() in (r.get('name') or '').lower():
        p = pn
        chain = []
        while p is not None and len(chain) < 5:
            chain.append((p.ix, p.raw.get('role'), p.raw.get('htmlTag'), (p.raw.get('name') or '')[:40], p.ia2_role())); p = p.parent
        print(chain)
        print({k: v for k, v in r.items() if k in ('role', 'htmlTag', 'nameFrom', 'display', 'className', 'isImage', 'state', 'children')}.keys(), r.get('state'))
        print('kids', [(k.ix, k.raw.get('role'), k.raw.get('htmlTag')) for k in pn.kids])
        for k in pn.kids:
            print(' kid', k.ia2_role(), {kk: vv for kk, vv in k.raw.items() if kk in ('name','nameFrom','state','display','url','description','role','isImage')}, 'pkids', k.pkids, 'hyper', repr(k.hypertext()))
        import standin
        print('buffer lines near:')
        t = driver.L.VBuf_getTextInRange(d.b._h, 0, driver.L.VBuf_getTextLength(d.b._h), True)
        i = t.find('Transport Scotland on youtube'); print(t[max(0,i-100):i+900])
        break
d.close()
