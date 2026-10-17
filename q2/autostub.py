import subprocess, re, sys, os
targets = sys.argv[1:]
# NVDA's own modules whose logic is the point of the exercise: never stub these, report the failure instead.
PROTECTED = {'speech','controlTypes','characterProcessing','textInfos','browseMode','virtualBuffers','documentBase','config','languageHandler','globalVars','speechDictHandler','aria','NVDAState','logHandler','keyboardHandler','baseObject','extensionPoints','utils','textUtils','unicodeNormalize','symbols','configobj','XMLFormatting','colors','locationHelper','autoSettingsUtils','buildVersion'}
stubs = os.environ.get('SEED','').split(',') if os.environ.get('SEED') else []
AUTO = []
for rnd in range(120):
    env = dict(os.environ, STUB=','.join(stubs))
    p = subprocess.run(['venv/bin/python', 'probe1.py', *targets], capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    new = []
    for m in re.findall(r"No module named '([^'.]+)", out): new.append(m)
    # an NVDA module that only fails because it needs the Windows DLLs: stub it, unless it is protected
    blocks = out.split('Traceback (most recent call last):')
    for b in blocks:
        if 'Unsupported platform' in b or "no attribute 'add_dll_directory'" in b or 'must be a C type' in b or 'storage info' in b or 'LoadLibrary' in b:
            frames = re.findall(r'source/([\w/]+?)(?:/__init__)?\.py", line \d+, in <module>', b)
            frames = [f.split('/')[0] for f in frames]
            for f in reversed(frames):
                if f not in PROTECTED and f not in stubs: new.append(f); AUTO.append(f); break
    new = [x for x in dict.fromkeys(new) if x not in stubs]
    if not new:
        print('\n'.join(l for l in out.splitlines() if l.startswith(('OK', 'FAIL'))))
        if any(l.startswith('FAIL') for l in out.splitlines()): print(out[-2500:])
        break
    stubs += new
print('STUBBED MODULES', stubs)
