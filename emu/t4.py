import driver, traceback, controlTypes
b = driver.load(driver.boot.R / 'q2/fix/simple-web.json')
for s, e, t in driver.lines(b):
    try: print(s, e, repr(t), '->', driver.speak_line(b, s))
    except BaseException: print(s, e, repr(t), 'ERR'); traceback.print_exc(limit=-4)
