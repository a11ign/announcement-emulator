import sys; sys.path.insert(0,'.')
import boot, live, driver, textInfos, api, globalVars
html = """<div role="application"><button>focus in app</button><p>this is an application, it contains a button with details</p><button aria-details="button-details">push me</button></div><div id="button-details" role="note"><p>Press to self-destruct</p></div>"""
d = live.LiveDoc(html)
d.place_caret('Test page load complete')
print(repr(d.press('tab'))); print(repr(d.press('tab')))
f = api.getFocusObject(); print(type(f).__mro__[:3], f.name, f.role)
print('ann', f.annotations and True, f.IA2Attributes.get('details-roles'))
try:
    c = api.getCaretPosition(); print('caretcls', type(c), c._startOffset, c._endOffset); c.expand(textInfos.UNIT_CHARACTER); print('char', repr(c.text), c._startOffset, c._endOffset)
    o2 = c.NVDAObjectAtStart; print('obj', type(o2), getattr(o2,'name',None), o2.role, bool(o2.annotations), o2.IA2Attributes.get('details-roles'))
except BaseException: pass
try:
    c = api.getCaretPosition(); print('caret', type(c), c._startOffset)
    c.expand(textInfos.UNIT_CHARACTER); o = c.NVDAObjectAtStart; print('atstart', type(o), o.name, bool(o.annotations))
except BaseException as e:
    import traceback; traceback.print_exc(limit=-4)
o = api.getFocusObject()
print('rels', o.detailsRelations)
t = o.annotations.targets; print('targets', t)
print('summary', t[0].summary if t else None)
print(repr(d.press('NVDA+d')))
d.close()
