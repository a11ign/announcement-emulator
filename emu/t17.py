import faulthandler; faulthandler.dump_traceback_later(70, exit=True)
import live, extract_cases, traceback, config
cs = {c['name']: c for c in extract_cases.cases()}
c = cs['test_preventDuplicateSpeechFromDescription_browse_tab']
print(c['steps'])
d = live.LiveDoc(c['html'])
try:
    d.place_caret('Test page load complete')
    for k, exp in c['steps']:
        if isinstance(k, tuple):
            sect = config.conf
            for part in k[1][:-1]: sect = sect[part]
            sect[k[1][-1]] = k[2]; continue
        try: act = d.press(k)
        except BaseException: traceback.print_exc(limit=-8); break
        print(k, 'PASS' if act == exp else 'FAIL', repr(act), '| expected', repr(exp))
finally: d.close()
