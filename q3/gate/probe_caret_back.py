"""PROBE (A11-166), run by `probes.py run-caret-back`: the export's q3/emulate.py with one change at run time: when a form-field probe (the sweep presses Enter on a control announced `collapsed`, asks for the focus, then Escape) is over, the
caret is put back on the line of the control that was probed.

Why: the probe can open a menu and the Escape closes it, which removes the nodes the caret had followed focus into. vbufBase/storage.cpp (replaceSubtree, 742-760) puts the selection back in "the deepest field the selection started in that still
exists"; emu/live.py `refresh` keeps the old selection as a number, which after the menu's text is gone is another line. This puts the caret on the surviving field's line. It is a probe of that cause and not an implementation of storage.cpp's rule
(the emulator's node identifiers are renumbered at every read, so the rule cannot be applied there as it stands)."""
import sys, os, runpy
ROOT = os.environ['PROBE_ROOT']; Q3 = os.path.join(ROOT, 'q3')
os.environ.setdefault('EMU_NVDA_INI', Q3 + '/nvda-fleet.ini'); os.environ.setdefault('EMU_FLEET_VOICES', '1')
sys.path.insert(0, Q3)
import livepage
import sweep, driver
original = sweep.disclosure_probe


def probe(w, phrase):
    lines = list(driver.lines(w.d.b)); caret = w.d.caret()[0]
    here = next((t for s, e, t in lines if s <= caret < e), None)
    probed = original(w, phrase)
    if probed and here:
        try: w.d.place_caret(here)
        except RuntimeError: pass
    return probed


sweep.disclosure_probe = probe
sys.argv = [Q3 + '/emulate.py'] + sys.argv[1:]
runpy.run_path(Q3 + '/emulate.py', run_name='__main__')
