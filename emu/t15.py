import objlayer, standin, json, boot, traceback, controlTypes
from NVDAObjects.IAccessible import ia2Web, chromium
import NVDAObjects.IAccessible as NI
flat = json.load(open(boot.R / 'q2/fix/simple-web.json'))
root = standin.build_platform_tree(flat); W = objlayer.World(root)
for ix in (34, 35, 41, 49, 52, 58):
    o = NI.IAccessible(windowHandle=objlayer.HWND, IAccessibleObject=W.facade(W.by_ix[ix]), IAccessibleChildID=0, event_windowHandle=objlayer.HWND, event_objectID=-4, event_childID=ix)
    print(ix, o.windowClassName, 'Ia2Web' if isinstance(o, ia2Web.Ia2Web) else '-', type(o).__name__, '|', o.role.name, repr(o.name), dict(o.IA2Attributes).get('tag'), o.positionInfo, o.isFocusable)
