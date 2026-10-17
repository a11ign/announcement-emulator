import driver, traceback
b = driver.load(driver.boot.R / 'q2/fix/simple-web.json')
driver.set_caret(b, 0)
for k in ['downArrow', 'downArrow', 'downArrow', 'downArrow', 'downArrow', 'upArrow']:
    try: print(k, '->', repr(driver.press(b, k)))
    except BaseException: print(k, 'ERR'); traceback.print_exc(limit=-6); break
