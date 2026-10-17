import sys; sys.path.insert(0,'.')
import boot, live, driver, textInfos, globalVars
d = live.LiveDoc('<iframe src="/aria/content/patterns/treegrid/examples/treegrid-1.html"></iframe>')
b = d.b
d.place_caret('Test page load complete')
for k in ('h','tab','t','downArrow'): print(k, repr(d.press(k)))
info = b.makeTextInfo(textInfos.POSITION_CARET); info.expand(textInfos.UNIT_LINE)
fs = info.getTextWithFields({})
for f in fs:
    if isinstance(f, textInfos.FieldCommand) and f.command == 'controlStart':
        fld = f.field; print({k: fld.get(k) for k in ('role','states','level','_startOfNode','table-rownumber')})
print(repr(d.press('control+alt+downArrow')))
import traceback
oc = d._focus_cb
def fc(ix): print('  FOCUS CB', ix, d.world.by_ix[ix].role); return oc(ix)
d._focus_cb = fc; d.world.focus_cb = fc
co = b.currentNVDAObject; print('currentNVDAObject', co.role, co.name, co.states, co.isFocusable, 'shouldPT', b.shouldPassThrough(co), 'focusable obj', b.currentFocusableNVDAObject.role)
try:
    print(repr(d.press('enter')))
    print('passThrough', b.passThrough, 'focus', globalVars.focusObject.role, globalVars.focusObject.name)
except BaseException: traceback.print_exc()
info = b.makeTextInfo(textInfos.POSITION_CARET); info.expand(textInfos.UNIT_LINE)
for f in info.getTextWithFields({}):
    if isinstance(f, textInfos.FieldCommand) and f.command == 'controlStart':
        fld = f.field; print('ROW?', {k: fld.get(k) for k in ('role','states','level','table-rownumber','IAccessible::state_512','IAccessible2::attribute_level','IAccessible::role','tableRow')}) if False else print('ROW?', {k: fld.get(k) for k in fld if 'role' in k.lower() or k in ('level','states')})
d.close()
