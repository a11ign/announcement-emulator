import sys; sys.path.insert(0,'.')
import boot, live, driver, globalVars, config
config.conf["documentFormatting"]["reportClickable"] = False
d = live.LiveDoc('<iframe src="/aria/content/patterns/grid/examples/data-grids.html"></iframe>')
d.place_caret('Test page load complete')
osc = d._scroll_cb
def sc(ix): print('  SCROLL CB', ix, d.world.by_ix[ix].role, d.world.by_ix[ix].raw.get('name')); return osc(ix)
d._scroll_cb = sc; d.world.scroll_cb = sc
for k in ('3','3','t'): print(k, repr(d.press(k)))
print('focus', globalVars.focusObject.role, globalVars.focusObject.name, [ (a.role, a.name) for a in globalVars.focusAncestors][-4:])
import NVDAObjects
orig = NVDAObjects.NVDAObject.event_stateChange
def spy(self): print('  stateChange on', self.role, self.name, 'states', self.states); return orig(self)
NVDAObjects.NVDAObject.event_stateChange = spy
import textInfos
co = d.b.currentNVDAObject; r_ = co.IAccessibleObject.pn.raw; print('RAW', r_.get('state'), r_.get('location'), r_.get('defaultActionVerb'), r_.get('name'))
co = d.b.currentNVDAObject; print('CURRENT', co.role, co.name, co.IAccessibleObject.pn.raw.get('defaultActionVerb'), 'focusable', d.b.currentFocusableNVDAObject.role, d.b.currentFocusableNVDAObject.name)
try: print('nActions', co.actionCount, co.getActionName(0) if co.actionCount else None)
except BaseException as e: print('action err', repr(e))
import boot as _b
ocl = d._click_cb
def cl(x, y): print('  CLICK', x, y); return ocl(x, y)
_b.click_hook = cl
oa = d._action_cb
def ac(ix): print('  ACTION CB', ix, d.world.by_ix[ix].role, d.world.by_ix[ix].raw.get('defaultActionVerb')); return oa(ix)
d._action_cb = ac; d.world.action_cb = ac
os_ = d.settle
def st(*a, **k): print('  SETTLE', a, k); return os_(*a, **k)
d.settle = st
print('space', repr(d.press('space')))
print('focus', globalVars.focusObject.role, globalVars.focusObject.name, [ (a.role, a.name) for a in globalVars.focusAncestors][-4:])
d.close()
