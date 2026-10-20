import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver
d = LivePage(url='https://design-system.service.gov.uk/components/select/', port=8821)
roles = {}
for ix, pn in d.world.by_ix.items():
    r = pn.raw.get('role'); roles[r] = roles.get(r, 0) + 1
print(sorted(roles.items(), key=lambda x: -x[1])[:60])
for ix, pn in d.world.by_ix.items():
    if pn.raw.get('role') in ('banner', 'contentInfo', 'header', 'footer', 'complementary', 'main', 'navigation'):
        print(ix, pn.raw.get('role'), pn.raw.get('htmlTag'), pn.raw.get('name'), pn.ia2_attrs().get('xml-roles'), pn.role)
d.close()
