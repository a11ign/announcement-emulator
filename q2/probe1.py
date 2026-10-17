import sys, os, traceback
sys.path.insert(0, os.path.dirname(__file__))
import stubs
SRC = os.path.expanduser('~/spikes/announcement-emulator-5661/nvda-src/source')
sys.path.insert(0, SRC); os.chdir(SRC)
import builtins
builtins._=lambda s:s; builtins.ngettext=lambda a,b,n:a if n==1 else b; builtins.pgettext=lambda c,s:s; builtins.npgettext=lambda c,a,b,n:a if n==1 else b
stubs.install(os.environ.get('STUB', '').split(','))
import globalVars, tempfile
globalVars.appDir = SRC
globalVars.appArgs.configPath = tempfile.mkdtemp(prefix='nvda-cfg-')
globalVars.appArgs.disableAddons = True
import config; config.initialize()
import languageHandler; languageHandler.setLanguage('en')
mods = [m for m in sys.argv[1:] if not m.endswith('.py')]
scripts = [m for m in sys.argv[1:] if m.endswith('.py')]
for m in mods:
    try:
        __import__(m); print('OK  ', m)
    except BaseException as e:
        print('FAIL', m, type(e).__name__, str(e)[:200]); traceback.print_exc(limit=-4)
print('LEDGER', sorted(set(stubs.LEDGER)))

for sc in scripts:
    exec(compile(open(sc).read(), sc, 'exec'), {'__name__': '__main__'})
