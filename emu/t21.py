import sys; sys.path.insert(0,'.')
import boot, live
d = live.LiveDoc('<p>This text is <b>bold</b></p><p>Second line is <font size="15pt">large</font></p><p><mark>hi</mark></p>')
nodes, f = d.s.dump()
for n in nodes:
    if n.get('role') in ('staticText','inlineTextBox') or n.get('name') in ('bold','large'):
        print({k:v for k,v in n.items() if k not in ('location','unclippedLocation','state','childIds','wordStarts','wordEnds','lineStarts','lineEnds','sentenceStarts','sentenceEnds','markerTypes','markerStarts','markerEnds')})
d.close()
