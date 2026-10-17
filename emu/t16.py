import boot, traceback
try:
    import api; print('api OK', [n for n in ('getFocusObject','setFocusObject','getFocusAncestors') if hasattr(api, n)])
except BaseException: traceback.print_exc(limit=-4)
