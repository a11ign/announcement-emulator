"""Explain the eleven misses the drift-free reading left (A11-165): what the scripted replay shows of each, and the class that follows.

    python explain.py <drift-free attributed misses.json> <drift-free misses.json> <replay freeze misses.json> <replay head misses.json> <out.json> [--manual manual.json]

The eleven are the unexplained misses of the drift-free reading on the ten shapes of that reading (`top` of its misses file; q3/attribute.py's `unexplained` rows of the gate's shapes). For each, on the replay at the freeze and at head, the page's comparability and whether the same
announcement is a miss. Class:
  method        at the freeze the page is comparable and the announcement is not a miss: the replay agrees where the script-free copy did not, so the copy caused it;
  from --manual a class and evidence the operator read from the evidence files, for a miss the replay cannot answer (the page is no longer comparable) or answers otherwise;
  unexplained   anything else, with what was tried.
The evidence of a `method` entry is the page's evidence file (evidence.py), the emulator's start state at head (start_state.py: the frozen emulator has no scroll step to start from) and the earlier reading's list-order evidence."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'remeasure'))
import readback as rb
import corpus_capture as cc

EARLIER_ORDER_EVIDENCE = '../remeasure/static/evidence-form-field-order.json'


def eleven(attributed, top):
    """The unexplained misses of the earlier reading on the gate's shapes."""
    return [m for m in attributed if m['class'] == 'unexplained' and ' + '.join(m['shape']) in top and m['channel'] != 'frames']


def observe(measure, miss):
    """What one reading says of an earlier miss: the page's status, and whether the same announcement is a miss on that page."""
    status = next((p['status'] for p in measure['pages'] if p['url'] == miss['url']), None)
    missed = any(m['url'] == miss['url'] and m['channel'] == miss['channel'] and m['expected'] == miss['expected'] for m in measure['misses'])
    return {'page': status, 'comparable': status == 'comparable', 'missed': missed}


def classify(at_freeze, manual):
    if at_freeze['comparable'] and not at_freeze['missed']: return 'method'
    return manual['class'] if manual else 'unexplained'


def build(attributed, top, freeze, head, manual=None, evidence_for=lambda url: []):
    out = []
    for m in eleven(attributed, top):
        gate_view, head_view = observe(freeze, m), observe(head, m); hand = (manual or {}).get(m['expected'])
        cls = classify(gate_view, hand)
        entry = {'page': m['url'], 'channel': m['channel'], 'expected': m['expected'], 'earlierPredicted': m['predicted'], 'class': cls, 'atFreeze': gate_view, 'atHead': head_view}
        if cls == 'method': entry['evidence'] = [EARLIER_ORDER_EVIDENCE] + evidence_for(m['url']); entry['why'] = 'the replay agrees where the script-free copy did not'
        elif hand: entry['evidence'] = hand['evidence']; entry['why'] = hand['why']
        else: entry['tried'] = 'the replay cannot answer it and no reading of it was made'
        out.append(entry)
    return {'misses': out}


if __name__ == '__main__':
    argv = sys.argv[1:]; manual = rb.read_json(argv[argv.index('--manual') + 1]) if '--manual' in argv else None
    if '--manual' in argv: del argv[argv.index('--manual'):argv.index('--manual') + 2]
    if len(argv) != 5: sys.exit(__doc__)
    attributed, before, freeze, head, out = rb.read_json(argv[0]), rb.read_json(argv[1]), rb.read_json(argv[2]), rb.read_json(argv[3]), argv[4]
    rb.write_json(out, build(attributed, before['top'], freeze, head, manual, lambda url: [f'evidence/evidence-{cc.slug_of(url)}.json', f'start/{url.rstrip("/").rsplit("/", 1)[-1]}.head.json']))
