"""Pull (page, [(key, expected speech)]) out of NVDA's own system tests, tests/system/robot/chromeTests.py, by AST.
Nothing is retyped: the page is the test's prepareChrome(...) argument and the expectation is its strings_match(...) argument,
both evaluated in a namespace built from the file's own module-level constants and helper functions."""
import ast, pathlib, sys
R = pathlib.Path.home() / 'spikes/announcement-emulator-5661'
SRC = R / 'nvda-src/tests/system/robot/chromeTests.py'


NOEXP = object()


class SpyStub:
    def getLanguageDescription(self, lang):
        # speechSpyGlobalPlugin.getLanguageDescription calls languageHandler.getLanguageDescription. On Windows that reads the OS's locale
        # names; here it is NVDA's Linux fallback, so these five tests compare structure, not Windows' names (flagged in the write-up).
        try:
            import languageHandler; return languageHandler.getLanguageDescription(lang)
        except Exception: return f'<LANG:{lang}>'


def namespace(tree):
    import os; ns = {'SPEECH_SEP': '  ', 'os': os}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) or (isinstance(node, ast.FunctionDef) and not node.name.startswith('test_')):
            try:
                exec(compile(ast.Module([node], []), str(SRC), 'exec'), ns)
            except Exception:
                pass
    ns['ARIAPatternsDir'] = '/aria/content/patterns'      # the submodule NVDA pins, served by session.mjs instead of read from a file:// path
    return ns


def cases():
    src = SRC.read_text(); tree = ast.parse(src); ns = namespace(tree)
    out = []
    # The suite is the .robot file's test cases (47 at release-2026.1.1); each runs one function of chromeTests.py, not all named test_*.
    robot = (SRC.parent / 'chromeTests.robot').read_text().split('*** Test Cases ***')[1].splitlines()
    names = [l.strip() for l in robot if l.startswith('\t') and l.strip() and not l.strip().startswith(('[', '#', '...'))]
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def ev(node, local): return eval(compile(ast.Expression(node), 'x', 'eval'), local)

    def run_body(stmts, local, st, depth=0):
        """Walk a function body in order, as a reader would: constants are bound, helper functions of this module are entered with their
        arguments bound, every key press is a step, every strings_match fills the step before it."""
        for stmt in stmts:
            if isinstance(stmt, ast.For) and isinstance(stmt.target, ast.Name):      # a loop is read as the sequence of its presses, one per element
                try: items = list(ev(stmt.iter, local))
                except Exception as e: items = None; st['issues'].append(f'loop not evaluable: {type(e).__name__} {e}')
                if items is not None:
                    for v in items:
                        local[stmt.target.id] = v; run_body(stmt.body, local, st, depth)
                    continue
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                try: local[stmt.targets[0].id] = ev(stmt.value, local)
                except Exception: pass
            for call in [c for c in ast.walk(stmt) if isinstance(c, ast.Call)]:
                if isinstance(call.func, ast.Name) and call.func.id in fns and not call.func.id.startswith('test_') and depth < 4:
                    h = fns[call.func.id]; inner = dict(local)
                    try:
                        for prm, arg in zip(h.args.args, call.args): inner[prm.arg] = ev(arg, local)
                        for kw in call.keywords: inner[kw.arg] = ev(kw.value, local)
                    except Exception: pass
                    run_body(h.body, inner, st, depth + 1)
                    continue
                if not isinstance(call.func, ast.Attribute): continue
                a = call.func.attr
                if a == 'prepareChrome' and st['html'] is None:
                    try: st['html'] = ev(call.args[0], local)
                    except Exception as e: st['issues'].append(f'page not evaluable: {type(e).__name__} {e}')
                elif a in ('getSpeechAfterKey', 'getSpeechAfterAction', 'getSpeechAndBrailleAfterKey') and call.args:
                    st['last'] = ast.literal_eval(call.args[0]) if isinstance(call.args[0], ast.Constant) else (ev(call.args[0], local) if isinstance(call.args[0], ast.Name) and isinstance(local.get(call.args[0].id), str) else ('<action>', ast.unparse(call.args[0])))
                    st['steps'].append([st['last'], NOEXP])      # every press is a step; the next strings_match fills its expectation
                elif a == 'getSpeechAfterTab':
                    st['last'] = 'tab'; st['steps'].append([st['last'], NOEXP])
                elif a in ('strings_match', 'speech_matches') and len(call.args) >= 2:
                    if 'getLanguageDescription' in ast.unparse(call.args[1]):
                        st['issues'].append('windows locale names')       # the expectation is Windows' name for the language: not reproducible on Linux
                    try: exp = ev(call.args[1], local)
                    except Exception as e: exp = None; st['issues'].append(f'expected not evaluable: {type(e).__name__} {e}')
                    if st['steps'] and st['steps'][-1][1] is NOEXP: st['steps'][-1][1] = exp
                    else: st['steps'].append([st['last'], exp])
                elif a == 'assignGesture':      # the spy binds a key to a script in NVDA's own user gesture map: applied by the runner before the next press
                    try: st['steps'].append([('assign',) + tuple(ev(x, local) for x in call.args), None])
                    except Exception as e: st['issues'].append(f'assignGesture not evaluable: {type(e).__name__}')
                elif a == 'set_configValue' and len(call.args) == 2:
                    try: st['steps'].append([('config',) + tuple(ev(x, local) for x in call.args), None])
                    except Exception as e: st['issues'].append(f'config not evaluable: {type(e).__name__}')
                elif a == 'modifyNVDAConfig' and call.args:
                    try:
                        for kv in ev(call.args[0], local): st['steps'].append([('config', kv[0], kv[1]), None])
                    except Exception as e: st['issues'].append(f'config not evaluable: {type(e).__name__}')
                elif a == 'speech_contains' and len(call.args) >= 2:
                    try: exp = ('contains', ev(call.args[1], local))
                    except Exception as e: exp = None; st['issues'].append(f'expected not evaluable: {type(e).__name__} {e}')
                    if st['steps'] and st['steps'][-1][1] is NOEXP: st['steps'][-1][1] = exp
                    else: st['steps'].append([st['last'], exp])
                elif a in ('braille_matches', 'braille_contains'):
                    st['braille'] += 1          # the emulator has no braille layer: these assertions are not checked
                elif a == 'string_contains_strings':
                    st['issues'].append(f'other assertion: {a}')

    for fn in [fns[n] for n in names if n in fns]:
        local = dict(ns); local['spy'] = SpyStub()
        st = dict(html=None, steps=[], issues=[], last=None, braille=0)
        run_body(fn.body, local, st)
        out.append(dict(name=fn.name, html=st['html'], steps=st['steps'], issues=st['issues'], braille=st['braille']))
    return out


if __name__ == '__main__':
    cs = cases()
    print(len(cs), 'tests;', sum(len(c['steps']) for c in cs), 'steps')
    for c in cs: print(c['name'], len(c['steps']), c['issues'])
