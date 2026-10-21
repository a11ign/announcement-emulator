import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver, re, standin
d = LivePage(url='http://192.168.1.108:8899/table.html', port=8897)
t = driver.L.VBuf_getTextInRange(d.b._h, 0, driver.L.VBuf_getTextLength(d.b._h), True)
for m in re.finditer(r'table-columnnumber="(\d+)"[^>]*?table-rownumber="(\d+)"|table-rownumber="(\d+)"[^>]*?table-columnnumber="(\d+)"', t): print(m.groups())
for ix, pn in sorted(d.world.by_ix.items()):
    if pn.raw.get('role') == 'cell': print(pn.ix, pn.raw.get('tableCellColumnIndex'), 'aria', pn.raw.get('tableCellAriaColumnIndex'), 'row.role', pn.parent.role, type(pn).__name__, type(pn).__module__, 'win', standin.Builder._windows_column(pn), 'span', pn.raw.get('tableCellColumnSpan'))
d.close()
