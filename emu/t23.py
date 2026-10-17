import sys; sys.path.insert(0,'.')
import boot, live, driver, textInfos, api, globalVars
html = """<div role="application"><button>focus in app</button><p>this is an application, it contains a button with details</p><button aria-details="button-details">push me</button></div><div id="button-details" role="note"><p>Press to self-destruct</p></div>"""
d = live.LiveDoc(html)
d.place_caret('Test page load complete')
b = d.b
print('before', b.makeTextInfo(textInfos.POSITION_CARET)._startOffset, b._focusEventMustUpdateCaretPosition)
orig = b._set_selection
def spy(info, **kw): print('  _set_selection', info._startOffset, info._endOffset, kw); return orig(info, **kw)
b._set_selection = spy
orig_m = b.makeTextInfo
def mk(*a, **k):
    try: r = orig_m(*a, **k); print('  makeTextInfo ok', a[0] if a and not hasattr(a[0],'name') else getattr(a[0],'name',a), r._startOffset); return r
    except BaseException as e: print('  makeTextInfo RAISES', type(e).__name__, e); raise
b.makeTextInfo = mk
orig_sp = b.shouldPassThrough
def sp(*a, **k): r = orig_sp(*a, **k); print('  shouldPassThrough', getattr(a[0],'name',a[0]), '->', r); return r
b.shouldPassThrough = sp
print(repr(d.press('tab')), b.makeTextInfo(textInfos.POSITION_CARET)._startOffset)
print(repr(d.press('tab')), b.makeTextInfo(textInfos.POSITION_CARET)._startOffset)
print('passThrough', b.passThrough, 'ready', b.isReady, 'focus', type(api.getFocusObject()).__name__, 'fti', api.getFocusObject().treeInterceptor is b)
for s,e,t in driver.lines(b): print(s,e,repr(t))
d.close()
