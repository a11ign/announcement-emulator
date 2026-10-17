import sys; sys.path.insert(0,'.')
import boot, live, driver, queueHandler, traceback
html = open('/dev/stdin').read() if False else None
import extract_cases
c = next(c for c in extract_cases.cases() if c['name']=='test_ariaDescription_sayAll')
d = live.LiveDoc(c['html']); d.place_caret('Test page load complete')
import speech.sayAll as sa
sa.SayAllHandler.readText(sa.CURSOR.CARET)
for i in range(60):
    try: queueHandler.flushQueue(queueHandler.eventQueue)
    except BaseException: traceback.print_exc(limit=-3)
    n = len(queueHandler.generators)
    try: queueHandler.pumpAll()
    except BaseException: traceback.print_exc(limit=-5); break
    print(i, 'generators', n, 'sequences', len(driver.SPY.sequences))
    if not queueHandler.generators and i > 3: break
print(repr(driver.SPY.text_since(0))[:600])
d.close()
