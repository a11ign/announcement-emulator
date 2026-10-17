import boot, characterProcessing as cp, traceback
for d in cp._symbolDictionaryDefinitions:
    try:
        print(d.name, d.enabled, d.path if hasattr(d,'path') else '')
        print('  ->', d.getSymbols('en') is not None)
    except BaseException as e:
        traceback.print_exc(limit=-3)
