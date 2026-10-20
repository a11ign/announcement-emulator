import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver
d = LivePage(url='https://design-system.service.gov.uk/components/select/', port=8841)
print('documentURL', repr(d.b.documentURL))
n = 0
for ix, pn in d.world.by_ix.items():
    if pn.raw.get('role') == 'link':
        print(ix, repr(pn.raw.get('name')), repr(pn.value()), pn.state.get('linked'), pn.state.get('visited')); n += 1
        if n > 4: break
import urlUtils
print(urlUtils.getLinkType('https://design-system.service.gov.uk/components/select/#main-content', d.b.documentURL) if hasattr(urlUtils,'getLinkType') else 'no urlUtils')
d.close()
