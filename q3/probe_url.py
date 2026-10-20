import sys, time, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'emu'))
import boot, driver, live
url = sys.argv[1]
t0 = time.time()
d = live.LiveDoc(url=url, port=int(os.environ.get('PORT', 8765))); d.scroll_browser = False
print('loaded', d.navigated, round(time.time() - t0, 1), 's; nodes', len(d.world.by_ix))
b = d.b
print('text length', driver.L.VBuf_getTextLength(b._h))
for k in ['control+home'] + ['h'] * 6:
    t = time.time(); r = d.press(k); print(repr(k), repr(r), round(time.time() - t, 2))
d.close()
