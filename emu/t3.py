import boot, json, ctypes, traceback
L = boot.LOCALLIB
L.register_tree((1, 34), json.load(open(boot.R / 'q2/fix/simple-web.json')))
h = L.VBuf_createBuffer(None, 1, 34, 'gecko_ia2')
import virtualBuffers.gecko_ia2 as g, textInfos, controlTypes
import speech, speech.speech as ss
buf = object.__new__(g.Gecko_ia2)
vh = L.VBufRemote_bufferHandle_t(); vh.value = h
buf.VBufHandle = vh
print('TextInfo class', buf.TextInfo)
try:
    ti = buf.makeTextInfo(textInfos.POSITION_FIRST)
    print('first made')
    ti.expand(textInfos.UNIT_LINE)
    print('LINE0', repr(ti.text), ti.bookmark)
    cmds = ti.getTextWithFields({})
    for c in cmds:
        if isinstance(c, textInfos.FieldCommand):
            f = c.field
            print(' ', c.command, {k: f.get(k) for k in ('role', 'states', 'name', 'level', 'alwaysReportName') if k in f})
        else: print('  text', repr(c))
except BaseException as e:
    traceback.print_exc(limit=-6)

print('---- speech by line (CARET)')
from speech.commands import *
def flat(seq):
    out = []
    for x in seq:
        if isinstance(x, str): out.append(x)
        elif isinstance(x, (BeepCommand, EndUtteranceCommand)): pass
        else: out.append('<%s>' % type(x).__name__)
    return out
try:
    off = 0
    n = L.VBuf_getTextLength(h)
    while off < n:
        ti = buf.makeTextInfo(textInfos.offsets.Offsets(off, off))
        ti.expand(textInfos.UNIT_LINE)
        end = ti._endOffset
        seq = list(ss.getTextInfoSpeech(ti, unit=textInfos.UNIT_LINE, reason=controlTypes.OutputReason.CARET, useCache=False))
        print(off, end, '->', [flat(s) if isinstance(s, list) else s for s in seq], flush=True)
        off = end if end > off else off + 1
except BaseException:
    traceback.print_exc(limit=-8)
