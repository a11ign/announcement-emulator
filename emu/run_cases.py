import sys, json, traceback, hashlib, pathlib
import capture, extract_cases
import driver, textInfos, controlTypes
SUPPORTED = {'k', 'rightArrow', 'leftArrow', 'end', 'nvda+space', 'd', 's', 'shift+d', 'shift+s', 'control+alt+home', 'control+alt+end', 'control+alt+pageUp', 'control+alt+pageDown', 'control+alt+downArrow', 'control+alt+upArrow', 'control+alt+rightArrow', 'control+alt+leftArrow', 'tab', 'shift+tab', 'enter', 'space', 'NVDA+space', 'downArrow', 'upArrow', 'control+rightArrow', 'control+leftArrow', 'NVDA+upArrow', 'control+home', 'end', 'h', 't', 'e', 'p', 'shift+p', '2', '3', 'x', 'NVDA+d', 'NVDA+tab', 'numpad8', 'numpad6', 'NVDA+downArrow', 'NVDA+control+alt+downArrow', 'NVDA+control+alt+upArrow', 'NVDA+control+alt+leftArrow', 'NVDA+control+alt+rightArrow'}

def find_status_line(b):
    for s, e, t in driver.lines(b):
        if 'Test page load complete' in t: return s
    raise RuntimeError('no load-status line')

LIVE_KEYS = {'tab', 'shift+tab', 'enter', 'space'}

def run_live(case):
    import live, config
    d = live.LiveDoc(case['html'])
    try:
        d.place_caret('Test page load complete')
        res = []
        for k, exp in case['steps']:
            if isinstance(k, tuple) and k[0] == 'assign':      # SystemTestSpy's assignGesture: inputCore.manager.userGestureMap.add(gesture, module, className, script)
                import inputCore, types      # the InputManager is not started here; the user gesture map is NVDA's own class
                if inputCore.manager is None: inputCore.manager = types.SimpleNamespace(userGestureMap=inputCore.GlobalGestureMap(), localeGestureMap=inputCore.GlobalGestureMap())
                inputCore.manager.userGestureMap.add(*k[1:]); continue
            if isinstance(k, tuple) and k[0] == 'config':
                sect = config.conf
                for part in k[1][:-1]: sect = sect[part]
                sect[k[1][-1]] = k[2]; continue
            try: act = d.press(k)
            except BaseException as e:
                import traceback; traceback.print_exc(limit=-6); act = f'ERR {type(e).__name__}: {e}'
            if exp is not extract_cases.NOEXP: res.append((k, exp if not isinstance(exp, tuple) else list(exp), act, (act == exp) if not isinstance(exp, tuple) else all(x in act for x in exp[1])))
        return res
    finally: d.close()

def run(case, only=None):
    return run_live(case)      # every test runs in a live session now: NVDA's real _set_selection needs the object layer
    key = hashlib.sha1(case['html'].encode()).hexdigest()[:12]
    nodes = capture.capture(case['html'], key)
    path = capture.CACHE / f'{key}.json'
    b = driver.load(path)
    driver.set_caret(b, find_status_line(b))
    res = []
    import config
    for k, exp in case['steps']:
        if isinstance(k, tuple) and k[0] == 'config':      # spy.set_configValue(path, value), applied to NVDA's real config
            sect = config.conf
            for part in k[1][:-1]: sect = sect[part]
            sect[k[1][-1]] = k[2]; continue
        try: act = driver.press(b, k)
        except BaseException as e: act = f'ERR {type(e).__name__}: {e}'
        if exp is not extract_cases.NOEXP: res.append((k, exp if not isinstance(exp, tuple) else list(exp), act, (act == exp) if not isinstance(exp, tuple) else all(x in act for x in exp[1])))
    return res

def run_one(name):
    case = next(c for c in extract_cases.cases() if c['name'] == name)
    return run(case)

IN_SCOPE_KEYS = SUPPORTED

def in_scope(c):
    return bool(c['html']) and bool(c['steps']) and not c['issues'] and all((isinstance(k, str) and k in SUPPORTED) or (isinstance(k, tuple) and k[0] in ('config', 'assign')) for k, _ in c['steps'])

if __name__ == '__main__':
    import json
    if len(sys.argv) > 2 and sys.argv[1] == '--one':      # one test per process: NVDA is started fresh for each test (chromeTests.robot: Test Setup)
        res = run_one(sys.argv[2])
        print('@@' + json.dumps([[k if isinstance(k, str) else list(k), exp, act, ok] for k, exp, act, ok in res]))
        sys.exit(0)
    import subprocess
    cs = extract_cases.cases(); scope = [c for c in cs if in_scope(c)]
    print('in scope:', len(scope), 'of', len(cs), [c['name'] for c in scope])
    total = passed = 0; table = []
    for c in scope:
        try:
            p = subprocess.run([sys.executable, '-u', __file__, '--one', c['name']], capture_output=True, text=True, timeout=240)
            line = next((l for l in p.stdout.splitlines() if l.startswith('@@')), None)
            res = json.loads(line[2:]) if line else []
            if not line: print('==', c['name'], 'HARNESS ERR', p.stderr.strip().splitlines()[-1:] )
        except subprocess.TimeoutExpired:
            res = []; print('==', c['name'], 'TIMEOUT')
        n_ok = 0
        for k, exp, act, ok in res:
            total += 1; passed += ok; n_ok += ok
            print('==', c['name'], k, 'PASS' if ok else 'FAIL')
            if not ok: print('   expected:', repr(exp)); print('   actual:  ', repr(act))
        table.append((c['name'], len(res), n_ok))
    print('RESULT', passed, '/', total)
    for n, t, o in table: print(f'  {o}/{t}  {n}')
