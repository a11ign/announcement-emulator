"""Where the browser's focus and NVDA's caret are when the emulator's sweeps start on a page (A11-165): the emulator's side of the evidence for the form-field order.

    <emulator python> start_state.py <address> <out.json> [--port 9800]       run under `with_replay.py`, so the page is read through its archive

It does what `q3/emulate.py` does up to the first sweep (load the page, scroll it to its end and back, `anchorToTop`, the read-through, and, once the emulator has it, the scroll to where the caret left the page) and writes: the element that has focus in the page at load, through the frames (so
an example frame's focus shows), the node the emulator's tree reports as focused, where the caret is after the read-through (its line, and the lines either side), and how the read-through ended. The sweeps start from
that caret, forward and backward, so a side that starts elsewhere lists the same entries in another order."""
import sys, os, json, argparse
os.environ.setdefault('EMU_NVDA_INI', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'nvda-fleet.ini'))
os.environ.setdefault('EMU_FLEET_VOICES', '1')      # as q3/emulate.py: the fleet's voices
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livepage import LivePage
import driver, sweep

ACTIVE = """(function walk(doc, depth) {
  var a = doc.activeElement, out = [];
  while (a && depth < 6) {
    var d = a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') + (a.className && typeof a.className === 'string' ? '.' + a.className.trim().split(/\\s+/).join('.') : '');
    out.push(d);
    if (a.tagName === 'IFRAME' && a.contentDocument) { doc = a.contentDocument; a = doc.activeElement; depth++; } else break;
  }
  return out.join(' > ');
})(document, 0)"""


def node(d, ix):
    n = d.world.by_ix.get(ix)
    return None if n is None else {'role': n.role, 'name': n.raw.get('name'), 'tag': n.raw.get('htmlTag')}


def caret_context(d, around=2):
    lines = list(driver.lines(d.b)); caret = d.caret()[0]
    at = next((i for i, (s, e, t) in enumerate(lines) if s <= caret < e), None)
    if at is None: return {'caret': caret, 'line': None}
    return {'caret': caret, 'lineIndex': at, 'lines': len(lines), 'line': lines[at][2], 'before': [l[2] for l in lines[max(0, at - around):at]], 'after': [l[2] for l in lines[at + 1:at + 1 + around]]}


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('out'); ap.add_argument('--port', type=int, default=9800); a = ap.parse_args(argv)
    d = LivePage(url=a.url, port=a.port); result = {'url': a.url}
    try:
        result['atLoad'] = {'activeElement': d.s.eval(ACTIVE), 'focusedNode': node(d, d.focus_ix)}
        sweep.load_lazy_content(d)
        result['afterScroll'] = {'activeElement': d.s.eval(ACTIVE), 'focusedNode': node(d, d.focus_ix)}
        w = sweep.Walker(d, driver); sweep.anchor_to_top(w)
        result['afterAnchorToTop'] = {'activeElement': d.s.eval(ACTIVE), **caret_context(d)}
        lines, reason = sweep.read_through(w)
        result['readThrough'] = {'count': len(lines), 'stopReason': reason, 'activeElement': d.s.eval(ACTIVE), **caret_context(d)}
        if hasattr(sweep, 'scroll_where_nvda_left_the_page'):      # the emulator after A11-176 scrolls the page where NVDA's caret left it before the sweeps (q3/emulate.py); the frozen one has no such step
            result['afterScroll'] = {'scrolled': sweep.scroll_where_nvda_left_the_page(w), 'activeElement': d.s.eval(ACTIVE), **caret_context(d)}
    finally:
        with open(a.out, 'w') as f: json.dump(result, f, indent=1)
        d.close()


if __name__ == '__main__': main(sys.argv[1:])
