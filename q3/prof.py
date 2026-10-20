import sys, time, os, cProfile, pstats
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'emu'))
import boot, driver, live
d = live.LiveDoc(url=sys.argv[1], port=8765); d.scroll_browser = False
d.press('control+home'); d.press('h')
pr = cProfile.Profile(); pr.enable()
for _ in range(3): d.press('h')
pr.disable(); d.close()
pstats.Stats(pr).sort_stats('cumulative').print_stats(25)
