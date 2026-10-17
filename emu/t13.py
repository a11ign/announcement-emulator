import boot, traceback
for m in ['IAccessibleHandler', 'NVDAObjects.IAccessible', 'NVDAObjects.IAccessible.ia2Web', 'NVDAObjects.IAccessible.chromium']:
    try: __import__(m); print('OK', m)
    except BaseException as e: print('FAIL', m, type(e).__name__, str(e)[:300]); traceback.print_exc(limit=-5); break
