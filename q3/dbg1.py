import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver
d = LivePage(url='https://design-system.service.gov.uk/components/select/', port=8811)
ixs = sorted(d.world.by_ix); print('web ixs', ixs[0], ixs[-1], 'focus_ix', d.focus_ix)
for k in ['control+home', 'f', 'f', 'f']:
    d.quick_press(k); print(k, 'focus_ix', d.focus_ix, driver.SPY.text_since(len(driver.SPY.sequences)-1))
nodes, fi = d.s.dump(); print('after focus: focusIx', fi, 'in web', fi in d.world.by_ix)
d.quick_press('shift+f'); 
print('--- enter')
try: d.quick_press('enter')
except Exception as e: print('ERR', e)
nodes, fi = d.s.dump(); print('focusIx', fi, ixs[0], d.s.eval('document.activeElement && document.activeElement.outerHTML.slice(0,200)'))
d.close()
