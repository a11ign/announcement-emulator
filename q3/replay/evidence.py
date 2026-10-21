"""The evidence for each of the 11 misses (A11-165): each side's list for the channel, side by side, on the replay.

    python evidence.py <oracle dir> <out dir> --emulator label=<runs dir> [--emulator label=<runs dir> ...] --page <address substring> [--page ...] [--channel formFields]

For each page it writes `<out dir>/evidence-<slug>.json` with, for the channel:
  - the fleet's list and each emulator run's list, how many entries each holds, the entries only one side has, and the indexes of the entries that open an example frame (those containing `, frame,`), the way
    q3/results/remeasure/static/evidence-form-field-order.json did on the copies;
  - where each side's sweep started: the fleet's `observed` for the channel (whether the quick-navigation sweep ran to both ends, and where it stopped) and each emulator run's `sweeps` entry and the end of its read-through;
  - whether the lists are the same set in the same order (`agree`), the same set in another order (`sameSetOtherOrder`), or not the same set.
`classify_order` is the part that decides, and is tested."""
import sys, os, glob, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import corpus_capture as cc
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'remeasure'))
import readback as rb


def frame_headers(entries): return [i for i, e in enumerate(entries) if ', frame,' in e]


def classify_order(fleet, emulator):
    """How two lists of announcements differ: `agree` (equal), `sameSetOtherOrder` (the same entries, counted, in another order), or `differentEntries` (some entry one side has and the other does not)."""
    if fleet == emulator: return 'agree'
    return 'sameSetOtherOrder' if collections.Counter(fleet) == collections.Counter(emulator) else 'differentEntries'


def only_in(a, b):
    """The entries of `a` that `b` does not have, counted (an entry `a` has twice and `b` once is once)."""
    left = collections.Counter(b); out = []
    for x in a:
        if left[x] > 0: left[x] -= 1
        else: out.append(x)
    return out


def side(entries, label=None):
    return {'entries': len(entries), 'frameHeaderIndexes': frame_headers(entries), 'first': entries[:3], **({'run': label} if label else {})}


def sweep_start(emulator_run, channel):
    """What an emulator run says of where the channel's sweep started: its read-through's stop and the channel's sweep marks (how many were found before the starting point, `prevCount`)."""
    label = {'formFields': 'formField', 'headings': 'heading', 'links': 'link', 'landmarks': 'landmark', 'graphics': 'graphic', 'lists': 'list', 'frames': 'frame'}[channel]
    mark = next((m for m in emulator_run.get('sweeps') or [] if m.get('type') == label), None)
    return {'readThrough': emulator_run.get('readThrough'), 'sweep': mark}


SWEEP_LABEL = {'formFields': 'formField', 'headings': 'heading', 'links': 'link', 'landmarks': 'landmark', 'graphics': 'graphic', 'lists': 'list', 'frames': 'frame'}


def fleet_start(capture, channel):
    """Where the fleet's browser focus and read-through were when the channel's sweep started, from the worker's own diagnostics: how the read-through ended, where focus was just before the sweep (`focusFrame`: null is the top
    document), and whether any element took focus before the read-through ended (the first focus event of the page, against the read-through's time): a page that moved focus on load would show one."""
    events = capture.get('diagnostics') or []
    read = next((e for e in events if e.get('event') == 'readThrough'), None)
    before = next((e for e in events if e.get('event') == 'pageState' and e.get('beforeProbe') == 'sweep:' + SWEEP_LABEL[channel]), None)
    log = next((e for e in events if e.get('event') == 'focusEventLog'), None)
    first = next((x for x in (log or {}).get('events') or [] if x.get('type') == 'focusin'), None)
    return {'readThrough': {k: read.get(k) for k in ('count', 'stopReason', 'atMs')} if read else None, 'focusFrameBeforeSweep': before.get('focusFrame') if before else None,
            'firstFocusIn': first, 'focusBeforeReadThroughEnded': bool(first and read and first['atMs'] < read['atMs'])}


def build(page_url, fleet_record, emulator_runs, channel):
    """One page's evidence. `emulator_runs` maps a label (`gate.run1`) to that run's output."""
    cap = fleet_record['capture']; fleet = list((cap.get('structure') or {}).get(channel) or [])
    out = {'url': page_url, 'channel': channel, 'worker': fleet_record.get('worker'), 'capturedAt': fleet_record.get('capturedAt'), 'fleet': side(fleet), 'fleetObserved': (cap.get('observed') or {}).get(channel), 'fleetStart': fleet_start(cap, channel), 'emulator': {}}
    for label, run in sorted(emulator_runs.items()):
        lst = list((run.get('structure') or {}).get(channel) or [])
        out['emulator'][label] = {**side(lst), 'order': classify_order(fleet, lst), 'onlyInFleet': only_in(fleet, lst), 'onlyInEmulator': only_in(lst, fleet), 'start': sweep_start(run, channel)}
    return out


def entries_with(entries, needle): return [e for e in entries if needle in e]


def entry_evidence(page_url, before_misses, fleet_record, emulator_runs, channel, needle):
    """One entry looked at on its own (the nidirect link of the drift-free reading): the rows of the earlier reading's miss list that name it (the fleet's string, and the string the matching paired it with), what the
    fleet's capture on the replay holds for the channel, and the emulator's entries that name it on each run."""
    rows = [{'expected': m['expected'], 'predicted': m['predicted'], 'class': m['class']} for m in before_misses['misses'] if m['url'] == page_url and m['channel'] == channel and (needle in m['expected'] or needle in (m['predicted'] or ''))]
    fleet = list((fleet_record['capture'].get('structure') or {}).get(channel) or [])
    return {'url': page_url, 'channel': channel, 'needle': needle, 'earlierReading': rows, 'fleetOnTheReplay': {'entries': len(fleet), 'withNeedle': entries_with(fleet, needle), 'firstLines': list(fleet_record['capture'].get('transcript') or [])[:3]},
            'emulatorOnTheReplay': {label: {'entries': len(run['structure'][channel]), 'withNeedle': entries_with(run['structure'][channel], needle)} for label, run in sorted(emulator_runs.items())}}


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('oracle'); ap.add_argument('out'); ap.add_argument('--emulator', action='append', default=[]); ap.add_argument('--page', action='append', default=[]); ap.add_argument('--channel', default='formFields'); ap.add_argument('--entry', help='<needle>: look at one entry of the channel instead (with --before-misses)'); ap.add_argument('--before-misses')
    a = ap.parse_args(argv); os.makedirs(a.out, exist_ok=True)
    dirs = dict(x.split('=', 1) for x in a.emulator)
    for f in sorted(glob.glob(os.path.join(a.oracle, '*.json'))):
        rec = rb.read_json(f); url = rec['capture']['url']
        if not any(p in url for p in a.page): continue
        slug = cc.slug_of(url); runs = {f'{label}.{os.path.basename(r)[len(slug) + 1:-5]}': rb.read_json(r) for label, d in dirs.items() for r in sorted(glob.glob(os.path.join(d, f'{slug}.run*.json')))}
        evidence = entry_evidence(url, rb.read_json(a.before_misses), rec, runs, a.channel, a.entry) if a.entry else build(url, rec, runs, a.channel)
        rb.write_json(os.path.join(a.out, f'evidence-{slug}{"-entry" if a.entry else ""}.json'), evidence)
        print(slug, {k: v['order'] for k, v in evidence['emulator'].items()} if not a.entry else 'entry')


if __name__ == '__main__': main(sys.argv[1:])
