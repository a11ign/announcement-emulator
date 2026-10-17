import objlayer, standin, json, boot, traceback, controlTypes
flat = json.load(open(boot.R / 'q2/fix/simple-web.json'))
root = standin.build_platform_tree(flat); W = objlayer.World(root)
import NVDAObjects.IAccessible as NI
for ix in (34, 35, 41, 49, 52, 58):
    pn = W.by_ix[ix]
    try:
        o = NI.IAccessible(windowHandle=objlayer.HWND, IAccessibleObject=W.facade(pn), IAccessibleChildID=0, event_windowHandle=objlayer.HWND, event_objectID=-4, event_childID=ix)
        print(ix, type(o).__mro__[0].__name__, [c.__name__ for c in type(o).__mro__[1:4]], repr(o.name), o.role, sorted(s.name for s in o.states))
    except BaseException as e:
        print(ix, 'ERR'); traceback.print_exc(limit=-5); break
