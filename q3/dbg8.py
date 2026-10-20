import sys, os, json
os.environ.setdefault('EMU_NVDA_INI', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvda-fleet.ini'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
d = LivePage(url=sys.argv[1], port=8881)
n = 0
for ix, pn in sorted(d.world.by_ix.items()):
    r = pn.raw
    if r.get('role') == 'image' and n < 4:
        n += 1; print(ix, repr(r.get('name')), r.get('nameFrom'), 'url=', r.get('url'), 'htmlTag', r.get('htmlTag'), 'value=', repr(r.get('value')), pn.parent.raw.get('role'), pn.parent.raw.get('url'))
d.close()
