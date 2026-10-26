"""A11-234 round one: the ceiling the oracle's own noise puts on the agreement, the figures by announcement shape with every miss attributed, the movement against the previous round, and the supported-versions list the
figures fill (middleware/results/agreement-round-1/rule.md).

    python3 round.py report --work <dir> --out <dir> [--notes attribution-notes.json] [--previous <dir>] [--list middleware/supported-versions.json --dates <build>=<YYYY-MM-DD> ...]
    python3 round.py blocked <report.json>

`<dir>/<held-out|fitted>/<build>/<reading>/agreement.json` is what `measure.py --include-unstable --tolerate-census --out` wrote for the reading (`ext-linux`, `devtools-linux`, `devtools-macos`, the control
`devtools-ubuntu-ci`), `<reading>-second/` the same with `--second` (agreement/measure_round.sh makes both), and `<reading>/blocked.json` the pages whose corpus test did not finish in the reading's first run
(`round.py blocked`). The attribution is compare_builds.py's, which is compare_sources.py's with `chromium build` added, and two causes are added to its closed list here: `test blocked` and `offscreen frame`.
`report` writes, under `--out`, `<set>/<build>/<source>-<os>/{agreement.txt,misses.json,rates.json}` for every reading, `round.txt` and `round.json`; with `--list` it also writes the held-out figures into the
supported-versions list, which this and compare_builds.py are the only things that fill. Nothing here writes an a11ign evidence field: the output is a measurement of a prediction (ADR 0047)."""
import argparse, collections, json, math, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_sources as cs        # noqa: E402
import compare_builds as cb         # noqa: E402

SETS = ('held-out', 'fitted')
Z = 1.96            # the Wilson interval is the 95% one
BAND = 0.6          # points: what the same pages moved with nothing changed but the run (middleware/results/tree-source/rule.md, A11-208's 80.8% and 81.4%)
# the misses the oracle or the test made, and not the middleware or the emulator (rule.md, "Low confidence"); every other cause counts against the middleware
ORACLE_CAUSES = ('page moved', 'oracle milestone', 'chromium build', 'network/runner', 'test blocked')
EXTRA_CAUSES = ('chromium build', 'test blocked', 'offscreen frame')
FIGURE = 'middleware/results/agreement-round-1/{set}/{build}/{key}/'
CHANNELS = cb.CHANNELS
LISTED_FLAGS = 10   # how many low-confidence shapes the text names


def is_closed(cause): return cs.is_cause(cause) or cause in EXTRA_CAUSES


def wilson_upper(agreed, units, z=Z):
    """The upper bound of the Wilson score interval of `agreed` in `units`."""
    if not units: return 1.0
    p = agreed / units
    centre, spread = p + z * z / (2 * units), z * math.sqrt(p * (1 - p) / units + z * z / (4 * units * units))
    return min(1.0, (centre + spread) / (1 + z * z / units))


def low_confidence(agreed, units, overall, causes):
    """A shape is low confidence when the interval of its agreement lies below the overall rate (so the shape is weaker than the whole, and not by chance in a few units) and at least one of its misses is the
    middleware's or the emulator's and not the oracle's."""
    return bool(units) and wilson_upper(agreed, units) < overall and any(c not in ORACLE_CAUSES for c in causes)


def printed(agreed, units):
    """The rate as agreement.txt prints it, one decimal of a percent, as a fraction: the list and the figure never read differently."""
    return round(float(f'{100 * agreed / units:.1f}') / 100, 3)


# ---- the corpus tests that did not finish

def unfinished(report):
    """The addresses whose corpus test did not pass in a Playwright JSON report: it timed out or failed before it had typed."""
    found = []
    def walk(suite):
        for s in suite.get('suites', []): walk(s)
        for spec in suite.get('specs', []):
            m = re.match(r'keyboard walk of (\S+)$', spec['title'])
            if m and any(not t['results'] or t['results'][-1]['status'] != 'passed' for t in spec['tests']): found.append(m.group(1))
    walk({'suites': report['suites']})
    return found


def read_blocked(set_dir, build, name):
    path = os.path.join(set_dir, build, name, 'blocked.json')
    if not os.path.exists(path): raise FileNotFoundError(f'{path}: measure_round.sh writes it for every reading; without it a page whose test did not finish would count against the middleware')
    with open(path) as f: return set(json.load(f))


# ---- the causes

def retag(miss, name, blocked):
    """The miss with the two causes this round adds, where their evidence holds. `test blocked`: nothing was typed because the corpus test did not finish, which is not a prediction at all (the three classes
    that measure.py names from the strings come first, and none of them has nothing predicted). `offscreen frame`: the extension's tree has the frame and nothing in it, because Chromium does not tell the
    browser process of a frame it does not draw (step-1-misses.md), and the DevTools port's tree has it."""
    if miss['channel'] in ('typed', 'field') and miss['predicted'] is None and miss['address'] in blocked and miss['cause'] not in ('prompt', 'language', 'history'):
        return {**miss, 'cause': 'test blocked', 'reason': 'the corpus test did not finish in this reading\'s first run, so nothing was typed'}
    if name == 'ext-linux' and miss['channel'] == 'frames' and miss['cause'].startswith('tree:'):
        return {**miss, 'cause': 'offscreen frame', 'reason': f'{miss["reason"]}; the extension has the frame and nothing in it'}
    return miss


def attribute_set(set_dir, notes=()):
    """({build: {reading: Reading}}, {build: {reading: [miss]}}) of one set of pages: every miss has exactly one cause of the closed list."""
    builds, second = cb.load_builds(set_dir)
    for build, readings in builds.items():
        lacking = [n for n in readings if n not in second[build]]
        if lacking: raise ValueError(f'{build}: no -second reading for {lacking}; without it `chromium build` is never assigned')
    attributed = cb.attribute_builds(builds, second, notes)
    for build, readings in attributed.items():
        for name, misses in readings.items():
            blocked = read_blocked(set_dir, build, name)
            readings[name] = [retag(m, name, blocked) for m in misses]
            bad = [m['cause'] for m in readings[name] if not is_closed(m['cause'])]
            if bad: raise ValueError(f'{build} {name}: a cause that is not in the rule: {sorted(set(bad))}')
    return builds, second, attributed


# ---- the rates

def tally(rows, keyf):
    t = collections.OrderedDict()
    for r in rows:
        c = t.setdefault(keyf(r), [0, 0]); c[0] += r['ok']; c[1] += 1
    return t


def pair(t, label): return dict(zip(('agreed', 'units'), t.get(label, [0, 0])))


def rates_of(reading, misses, held_out):
    """Everything a figure says by shape and by channel, the fleet against itself beside it: what is committed beside `agreement.txt` (`rates.json`) and what the list is filled from."""
    main, fleet = list(reading.main.values()), list(reading.fleet.values())
    agreed, units = cs.headline(reading)
    by_channel_main, by_channel_fleet = tally(main, lambda r: r['channel']), tally(fleet, lambda r: r['channel'])
    by_shape_main, by_shape_fleet = tally(main, cs.shape_name), tally(fleet, cs.shape_name)
    causes = collections.defaultdict(collections.Counter)
    for m in misses: causes[' + '.join(m['shape'])][m['cause']] += 1
    overall = agreed / units if units else 0.0
    shapes = {s: {**pair(by_shape_main, s), 'ceiling': pair(by_shape_fleet, s), 'misses': dict(causes[s].most_common()),
                  'lowConfidence': low_confidence(*by_shape_main[s], overall, causes[s])} for s in sorted(by_shape_main, key=lambda s: (-by_shape_main[s][1], s))}
    return {'heldOut': held_out, 'pages': sum(s['status'] == 'comparable' for s in reading.status.values()), 'headline': {'agreed': agreed, 'units': units},
            'ceiling': {'agreed': sum(r['ok'] for r in fleet), 'units': len(fleet)},
            'byChannel': {ch: {**pair(by_channel_main, ch), 'ceiling': pair(by_channel_fleet, ch)} for ch in CHANNELS if ch in by_channel_main}, 'shapes': shapes,
            'causes': dict(collections.Counter(m['cause'] for m in misses).most_common())}


def list_entry(rates, date, figure):
    """The list's figure for a reading, from its rates: the rate agreement.txt prints, the population, the ceiling, and each shape's rate and flag."""
    h, c = rates['headline'], rates['ceiling']
    if not c['units']: raise ValueError('the figure has no ceiling: no page has a second fleet capture to compare the first with')
    return {'agreement': printed(h['agreed'], h['units']), 'units': h['units'], 'date': date, 'figure': figure,
            'population': {'pages': rates['pages'], 'heldOut': rates['heldOut'], 'units': h['units']},
            'ceiling': {'agreement': printed(c['agreed'], c['units']), 'units': c['units']},
            'shapes': {s: {'agreement': round(v['agreed'] / v['units'], 3), 'units': v['units'], 'lowConfidence': v['lowConfidence']} for s, v in rates['shapes'].items() if v['units'] and s}}      # a unit whose words have no shape (an empty string) has no key a report could look up


def fill_list(listing, entries):
    """`listing` with each build's listed readings replaced by the round's: `entries` is {build: {key: list entry}}. A build the round did not measure is left as it is; so is a reading of a measured build that it
    did not measure."""
    builds = []
    for b in listing.get('builds', []):
        if b['chromium'] in entries: b = {**b, 'measured': dict(sorted({**b['measured'], **entries[b['chromium']]}.items()))}
        builds.append(b)
    unknown = [c for c in entries if c not in {b['chromium'] for b in builds}]
    if unknown: raise ValueError(f'the list does not name Chromium {unknown}: its Playwright versions are not known here (compare_builds.py --list adds a build)')
    return {**listing, 'builds': builds}


# ---- the previous round

def parse_figure(text):
    """(agreed, units, {shape: (agreed, units)}) of the headline block of an agreement.txt: the last `all channels` line and the last by-shape table, which are the every-channel ones."""
    heads = re.findall(r'^all channels: (\d+) of (\d+) units agreed', text, re.M)
    if not heads: raise ValueError('no headline line')
    block = text.split('agreement by shape')[-1]
    shapes = {}
    for line in block.splitlines():
        cells = line.split(' | ')
        first, label = re.match(r'^\s*(\d+) / (\d+)\s', cells[0]), re.search(r'(?:\d+\.\d%|n/a)\s{2}(\S.*)$', cells[-1])
        if len(cells) == 3 and first and label: shapes[label.group(1).strip()] = (int(first.group(1)), int(first.group(2)))
    return int(heads[-1][0]), int(heads[-1][1]), shapes


def points(before, after):
    """The change from one (agreed, units) rate to another, in points of a percent; rounded, so that exactly the band's width reads as within it."""
    return round(100 * (after[0] / after[1] - before[0] / before[1]), 9)


def movement(before, after):
    """`up`, `down` or `within` (the run-to-run band) for two (agreed, units) rates."""
    if not before[1] or not after[1]: return 'not compared'
    change = points(before, after)
    return 'within' if abs(change) <= BAND else ('up' if change > 0 else 'down')


def rate(counts): return cs.rate(*counts)


# ---- the tables

def render_reading(name, rates, previous):
    lines = []
    out = lines.append
    h, c = rates['headline'], rates['ceiling']
    out(f"  {name}: {h['agreed']} of {h['units']} units = {rate((h['agreed'], h['units']))} on {rates['pages']} pages; the fleet agrees with itself on {c['agreed']} of {c['units']} = {rate((c['agreed'], c['units']))}"
        f" (the ceiling: agreement above it cannot be told from the oracle's noise)" + ('' if c['units'] == h['units'] else f"; NOTE the ceiling is over {c['units']} units and the figure over {h['units']}: a page lacks a second fleet capture"))
    if previous:
        before = previous['headline']
        out(f"    against the previous figure ({before[0]} of {before[1]} = {rate(before)}): {points(before, (h['agreed'], h['units'])):+.1f} points, {movement(before, (h['agreed'], h['units']))}")
    out('    by channel (agreed / units, the fleet against itself beside it):')
    for ch, v in rates['byChannel'].items(): out(f"      {ch:<11} {v['agreed']:>4} / {v['units']:<4} {rate((v['agreed'], v['units'])):>6}   fleet {rate((v['ceiling']['agreed'], v['ceiling']['units'])):>6}")
    out('    by shape (the ten commonest; a flag is a low-confidence shape):')
    for s, v in list(rates['shapes'].items())[:cs.TOP]:
        was = previous and previous['shapes'].get(s)
        move = f"   previous {rate(was)}: {movement(was, (v['agreed'], v['units']))}" if was else ''
        out(f"      {s[:52]:<52} {v['agreed']:>4} / {v['units']:<4} {rate((v['agreed'], v['units'])):>6}   fleet {rate((v['ceiling']['agreed'], v['ceiling']['units'])):>6}{move}{'   LOW CONFIDENCE' if v['lowConfidence'] else ''}")
    flagged = [s for s, v in rates['shapes'].items() if v['lowConfidence']]
    out(f"    low-confidence shapes: {len(flagged)} of {len(rates['shapes'])} (all in rates.json); the commonest:")
    for s in flagged[:LISTED_FLAGS]: out(f"      {s[:52]:<52} {rates['shapes'][s]['agreed']:>4} / {rates['shapes'][s]['units']:<4} {rate((rates['shapes'][s]['agreed'], rates['shapes'][s]['units'])):>6}")
    out('    every miss has one cause: ' + (', '.join(f'{k} {v}' for k, v in rates['causes'].items()) or 'no misses'))
    out('    causes by shape (the ten commonest):')
    for s, v in list(rates['shapes'].items())[:cs.TOP]:
        if v['misses']: out(f"      {s[:52]:<52} " + ', '.join(f'{k} {n}' for k, n in v['misses'].items()))
    return '\n'.join(lines)


def previous_of(root, build, key):
    """The previous round's figure for the reading, as `parse_figure` reads it, or None."""
    path = os.path.join(root, build, key, 'agreement.txt') if root else None
    if not path or not os.path.exists(path): return None
    with open(path) as f: agreed, units, shapes = parse_figure(f.read())
    return {'headline': (agreed, units), 'shapes': shapes}


def write_reading(out, set_name, build, name, reading, misses, rates):
    """`<out>/<set>/<build>/<source>-<os>/{misses.json,rates.json}` of one reading (`agreement.txt` is copied beside them): (the reading's key in the list, its directory)."""
    key = cb.FIGURE_KEY[name]
    d = os.path.join(out, set_name, build, key)
    os.makedirs(d, exist_ok=True)
    counts = collections.Counter((r['channel'], bool(r['ok'])) for r in reading.main.values())
    with open(os.path.join(d, 'misses.json'), 'w') as f:
        json.dump({'status': reading.status, 'units': {ch: [counts[(ch, True)], counts[(ch, True)] + counts[(ch, False)]] for ch in sorted({c for c, _ in counts})}, 'misses': misses}, f, indent=1, ensure_ascii=False)
    with open(os.path.join(d, 'rates.json'), 'w') as f: json.dump(rates, f, indent=1)
    return key, d


SET_LABEL = {'held-out': 'chosen and frozen before they were read', 'fitted': 'the six the emulator was fitted against: NOT held out'}


def report_set(set_name, set_dir, out, notes, previous):
    """(the text of one page set's tables, {build: {key: rates}}); every reading's figure is written under `out`."""
    builds, _, attributed = attribute_set(set_dir, notes)
    texts, rates_by_build = [f'## {set_name} pages ({SET_LABEL[set_name]})'], {}
    for build in sorted(builds, reverse=True):
        rates_by_build[build] = {}
        texts.append(f'### Chromium {build}')
        for name in (n for n in cs.READINGS if n in builds[build]):
            rates = rates_of(builds[build][name], attributed[build][name], set_name == 'held-out')
            key, d = write_reading(out, set_name, build, name, builds[build][name], attributed[build][name], rates)
            src = os.path.join(set_dir, build, name, 'agreement.txt')
            if os.path.exists(src): shutil.copy(src, os.path.join(d, 'agreement.txt'))
            rates_by_build[build][key] = rates
            texts.append(render_reading(key, rates, None if set_name == 'held-out' else previous_of(previous, build, key)))
    return '\n'.join(texts), rates_by_build


def report(work, out, notes=(), previous=None):
    """(the text of round.txt, {set: {build: {key: rates}}})."""
    texts, all_rates = [], {}
    for set_name in (s for s in SETS if os.path.isdir(os.path.join(work, s))):
        text, all_rates[set_name] = report_set(set_name, os.path.join(work, set_name), out, notes, previous)
        texts.append(text)
    return '\n'.join(texts), all_rates


def update_list(path, all_rates, dates):
    entries = {}
    for build, readings in all_rates.get('held-out', {}).items():
        if build not in dates: raise ValueError(f'--dates needs {build}=YYYY-MM-DD')
        entries[build] = {key: list_entry(r, dates[build], FIGURE.format(set='held-out', build=build, key=key)) for key, r in readings.items() if key in cb.LISTED and r['headline']['units']}
    with open(path) as f: listing = json.load(f)
    filled = json.dumps(fill_list(listing, entries), indent=2) + '\n'      # built before the file is opened for writing: a refusal must not leave the list empty
    with open(path, 'w') as f: f.write(filled)


def main(argv):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='command', required=True)
    r = sub.add_parser('report'); r.add_argument('--work', required=True); r.add_argument('--out', required=True); r.add_argument('--notes'); r.add_argument('--previous', help="the previous round's figures (middleware/results/playwright-versions)")
    r.add_argument('--list'); r.add_argument('--dates', nargs='*', default=[], metavar='BUILD=DAY')
    b = sub.add_parser('blocked'); b.add_argument('report')
    a = ap.parse_args(argv)
    if a.command == 'blocked':
        with open(a.report) as f: print(json.dumps(unfinished(json.load(f))))
        return 0
    text, all_rates = report(a.work, a.out, cs.load_notes(a.notes), a.previous)
    print(text)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'round.txt'), 'w') as f: f.write(text + '\n')
    with open(os.path.join(a.out, 'round.json'), 'w') as f: json.dump(all_rates, f, indent=1)
    if a.list: update_list(a.list, all_rates, dict(x.split('=', 1) for x in a.dates))
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
