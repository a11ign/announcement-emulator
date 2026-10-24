"""What each reading of one page has: the fleet's readings and the emulator's runs, side by side, for the announcements that decide a row (A11-176; NOT HELD OUT).

    python3 page_readings.py <address> <channel>=<announcement> [...] --fleet <label>=<oracle dir> [...] --emulator <label>=<run dir> [...] [--out <file.json>]

A page whose script reacts to scrolling (caselaw's document bar) is not read the same way every time: the fleet's reading and the census the emulator compares it by differ from one reading to the next. One reading of each, as `measure.py` takes
them, can then be a coin toss, so this lists every reading there is. A fleet reading is an oracle directory (`corpus_capture.py`), an emulator run is every `<slug>.run<k>.json` of a directory (`run_replayed.py`).
For each: whether it has each announcement, and for an emulator run its first census (headings and links). Nothing is scored here."""
import glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, Q3)
import corpus_capture as cc


def has(structure, wanted): return {f'{channel}={text}': text in (structure.get(channel) or []) for channel, text in wanted}


def fleet_reading(directory, slug, wanted):
    record = json.loads(open(os.path.join(directory, slug + '.json'), encoding='utf-8').read())
    return {'worker': record.get('worker'), 'capturedAt': record.get('capturedAt'), 'has': has(record['capture']['structure'], wanted)}


def emulator_runs(directory, slug, wanted):
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, slug + '.run*.json')), key=lambda p: int(re.search(r'\.run(\d+)\.json$', p).group(1))):
        run = json.loads(open(path, encoding='utf-8').read())
        out[re.search(r'\.(run\d+)\.json$', path).group(1)] = {'census': {k: run['census'][k] for k in ('heading', 'link')}, 'has': has(run['structure'], wanted)}
    return out


def readings(address, wanted, fleet, emulator):
    slug = cc.slug_of(address)
    return {'page': address, 'announcements': [f'{c}={t}' for c, t in wanted], 'fleet': {label: fleet_reading(d, slug, wanted) for label, d in fleet.items()},
            'emulator': {label: emulator_runs(d, slug, wanted) for label, d in emulator.items()}}


def main(argv):
    if not argv or argv[0] in ('-h', '--help'): sys.exit(__doc__)
    address, fleet, emulator, wanted, out = argv[0], {}, {}, [], None
    args = iter(argv[1:])
    for a in args:
        if a == '--fleet': label, d = next(args).split('=', 1); fleet[label] = d
        elif a == '--emulator': label, d = next(args).split('=', 1); emulator[label] = d
        elif a == '--out': out = next(args)
        else: channel, text = a.split('=', 1); wanted.append((channel, text))
    result = readings(address, wanted, fleet, emulator)
    if out: open(out, 'w', encoding='utf-8').write(json.dumps(result, indent=1, ensure_ascii=False) + '\n')
    for label, r in result['fleet'].items(): print('fleet', label, r['worker'], r['capturedAt'], sum(r['has'].values()), 'of', len(wanted))
    for label, runs in result['emulator'].items():
        print('emulator', label, ' '.join(f"{k}:{sum(v['has'].values())}/{len(wanted)}" for k, v in runs.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
