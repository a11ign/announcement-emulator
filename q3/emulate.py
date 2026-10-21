"""Run the worker's structural sweep over one live address in the emulator and write what it announced.

    python emulate.py <url> <out.json> [--port 8765]

Prints nothing but errors; the result is the JSON. Needs the emulator's virtualenv (see Reproduction in docs/announcement-emulator-spike.md)."""
import sys, os, json, time, argparse
os.environ.setdefault('EMU_NVDA_INI', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvda-fleet.ini'))      # the fleet's NVDA settings, not the system tests'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver, sweep

ap = argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('out'); ap.add_argument('--port', type=int, default=8765)
ap.add_argument('--history', help='JSON list of addresses the fleet browser has visited'); ap.add_argument('--budget', type=int, default=420, help='seconds, the worker captures within 420 (DEFAULT_BUDGET_MS)')
a = ap.parse_args()
t0 = time.time(); res = {'url': a.url, 'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'emulator': {'nvda': '2026.1.1', 'chrome': '155.0.8059.84'}}
d = None
try:
    d = LivePage(url=a.url, port=a.port, history=json.load(open(a.history)) if a.history else None)
    res['firstLink'] = next((pn.raw.get('url') for ix, pn in sorted(d.world.by_ix.items()) if pn.raw.get('role') == 'link' and pn.raw.get('url')), None)
    res['title'] = d.world.root.raw.get('name')
    res['viewport'] = d.s.eval("innerWidth+'x'+innerHeight"); res['href'] = d.navigated.get('href'); res['nodes'] = len(d.world.by_ix); res['census'] = d.census()
    w = sweep.Walker(d, driver)
    deadline = time.time() + a.budget
    sweep.anchor_to_top(w)
    lines, reason = sweep.read_through(w)
    res['readThrough'] = {'count': len(lines), 'stopReason': reason}
    structure, marks = sweep.structure_sweep(w, deadline)
    res['structure'] = structure; res['sweeps'] = marks; res['actions'] = w.actions; res['errors'] = w.errors
    res['census_after'] = {k: v for k, v in d.census().items() if k != 'roles'}
except BaseException as e:
    import traceback; traceback.print_exc()
    res['fault'] = f'{type(e).__name__}: {e}'
finally:
    res['seconds'] = round(time.time() - t0, 1)
    open(a.out, 'w').write(json.dumps(res, indent=1))
    if d: d.close()
