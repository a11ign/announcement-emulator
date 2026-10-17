import faulthandler; faulthandler.dump_traceback_later(25, exit=True)
import objlayer, standin, json, boot, traceback, controlTypes
import NVDAObjects.IAccessible as NI
flat = json.load(open(boot.R / 'q2/fix/simple-web.json'))
root = standin.build_platform_tree(flat); W = objlayer.World(root)
def mk(ix): return NI.IAccessible(windowHandle=objlayer.HWND, IAccessibleObject=W.facade(W.by_ix[ix]), IAccessibleChildID=0, event_windowHandle=objlayer.HWND, event_objectID=-4, event_childID=ix)
o = mk(41); print('made', o.role)
print('parent', end=' '); p = o.parent; print(p.role if p else None)
print('next', end=' '); n = o.next; print(n.role if n else None)
print('children', len(o.children))
print('presType', o.presentationType)
print('treeInterceptor', o.treeInterceptor)
print('isPresentableFocusAncestor', o.isPresentableFocusAncestor)
