import boot, json, standin
flat = json.load(open(boot.R / 'q2/fix/simple-web.json'))
L = boot.LOCALLIB; L.register_tree((1, 34), flat)
h = L.VBuf_createBuffer(None, 1, 34, 'gecko_ia2')
b = L.buffers[h]
print('LEN', L.VBuf_getTextLength(h))
print(repr(b.all_text()))
print(L.VBuf_getTextInRange(h, 0, 20, True)[:1500])
off = 0
while off < L.VBuf_getTextLength(h):
    import ctypes
    s, e = ctypes.c_int(), ctypes.c_int()
    L.VBuf_getLineOffsets(h, off, 0, False, ctypes.byref(s), ctypes.byref(e))
    print('LINE', s.value, e.value, repr(b.all_text()[s.value:e.value]))
    off = e.value
