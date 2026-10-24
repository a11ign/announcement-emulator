"""Every key the emulator's sweeps press on one page, with what was announced, where NVDA's caret is and what has focus in the page after it (A11-166). The evidence for a miss that depends on where the caret was.

    <emulator python> trace_caret.py <address> <out.json> [--root <export dir>]      run under with_replay.py, so the page is read through its archive

The sweeps are q3/sweep.py's own, unchanged; this wraps `Walker.perform` to look after each key."""
import sys, os, json, time, argparse
ap = argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('out'); ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ap.add_argument('--port', type=int, default=9880); a = ap.parse_args()
Q3 = os.path.join(a.root, 'q3') if os.path.isdir(os.path.join(a.root, 'q3')) else a.root
os.environ.setdefault('EMU_NVDA_INI', Q3 + '/nvda-fleet.ini'); os.environ.setdefault('EMU_FLEET_VOICES', '1')
sys.path.insert(0, Q3)
from livepage import LivePage
import driver, sweep
d = LivePage(url=a.url, port=a.port); sweep.load_lazy_content(d); w = sweep.Walker(d, driver); sweep.anchor_to_top(w); sweep.read_through(w)
if hasattr(sweep, 'scroll_where_nvda_left_the_page'): sweep.scroll_where_nvda_left_the_page(w)      # as q3/emulate.py, once the emulator has the step (A11-176); the frozen one has not
rows = []; perform = w.perform
FOCUS = "document.activeElement.tagName + '.' + (document.activeElement.className||'').slice(0,30) + '|' + (document.activeElement.getAttribute('aria-label')||'')"


def traced(key):
    said = perform(key)
    lines = list(driver.lines(d.b)); caret = d.caret()[0]; at = next((i for i, (s, e, t) in enumerate(lines) if s <= caret < e), None)
    rows.append({'n': len(w.log), 'key': key, 'said': said[:90], 'caret': caret, 'line': at, 'lineText': lines[at][2][:60] if at is not None else None, 'focus': d.s.eval(FOCUS)})
    return said


w.perform = traced
sweep.structure_sweep(w, time.time() + 420)
with open(a.out, 'w') as f: json.dump(rows, f, indent=1)
d.close()
