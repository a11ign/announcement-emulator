import json, sys, difflib
e=json.load(open(sys.argv[1])); o=json.load(open(sys.argv[2]))['capture']
print(e.get('fault'), e['seconds'], e.get('errors'), e.get('census_after'))
for ch in ['headings','landmarks','formFields','graphics','links','lists','frames']:
    E=e['structure'][ch]; O=o['structure'][ch]
    sm=difflib.SequenceMatcher(None,O,E,autojunk=False)
    m=sum(b.size for b in sm.get_matching_blocks())
    print(ch, 'oracle',len(O),'emu',len(E),'matched',m)
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag!='equal': print('   ',tag,'\n       O:',O[i1:i2][:4],'\n       E:',E[j1:j2][:4])
