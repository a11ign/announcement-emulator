import sys, os, json
os.environ.setdefault('EMU_NVDA_INI', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvda-fleet.ini'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver
d = LivePage(url='https://design-system.service.gov.uk/components/select/', port=8851)
for ix, pn in d.world.by_ix.items():
    if pn.raw.get('role') == 'image':
        p = pn
        while p is not None:
            r = p.raw; print(p.ix, r.get('role'), r.get('htmlTag'), repr(r.get('name')), r.get('nameFrom'), {k: v for k, v in r.items() if k in ('description','url','roleDescription','display','state')}.keys()); p = p.parent
        print(json.dumps({k: v for k, v in pn.raw.items() if k not in ('location',)}, default=str)[:900])
        print('kids', [(k.raw.get('role'), k.raw.get('name')) for k in pn.kids])
        break

import standin
for ix, pn in d.world.by_ix.items():
    if pn.raw.get('role') == 'image':
        print('name', repr(pn.name()), 'hypertext', repr(pn.hypertext()), 'pkids', pn.pkids, 'attrs', {k: v for k, v in pn.ia2_attrs().items() if k in ('name-from','explicit-name')}, 'role', pn.ia2_role())
        print('msaa_state', bin(pn.msaa_state()), 'state raw', pn.raw.get('state'))
        break
d.close()
