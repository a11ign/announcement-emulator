import sys; sys.path.insert(0,'.')
import session, capture, pathlib, time
page = capture.CACHE / 'live-simple.html'
page.write_text(capture.WRAP.format(title='T', case=open('../q2/fix/simple.html').read().split('<body>')[1].split('</body>')[0]))
s = session.Session(page)
time.sleep(1.5)
try:
    nodes, f = s.dump(); print('nodes', len(nodes), 'focusIx', f)
    byix = {n['ix']: n for n in nodes}
    print('focus initially:', byix.get(f, {}).get('role'), byix.get(f, {}).get('name'))
    for i in range(4):
        s.key('Tab'); nodes, f = s.dump(); byix = {n['ix']: n for n in nodes}
        n = byix.get(f, {}); print('Tab', i + 1, '->', n.get('role'), repr(n.get('name')), n.get('state'))
finally:
    s.close()
