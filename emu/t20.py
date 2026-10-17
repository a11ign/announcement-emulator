import sys; sys.path.insert(0,'.')
import boot, live, driver, textInfos
d = live.LiveDoc('<p>Hello world!</p><p>This text is <b>bold</b></p><p>Second line is <font size="15pt">large</font></p><p>Third line is <mark>highlighted</mark></p>')
b = d.b
for s,e,t in driver.lines(b):
    info = b.makeTextInfo(textInfos.POSITION_FIRST); info._startOffset = s; info._endOffset = e
    st = b._mergeIdenticalStyles(b._extractStyles(info))
    print(repr(t)); [print('   ', (x.field if not isinstance(x,str) else repr(x))) for x in st]
d.close()
