"""A11-230 step 2: each supported Chromium build measured by A11-229's method, the causes of its misses, and the list the measurement fills (middleware/results/playwright-versions/rule.md).

    python3 compare_builds.py --work <dir> --out <dir> [--notes attribution-notes.json]
    python3 compare_builds.py --work <dir> --out <dir> --list middleware/supported-versions.json --dates <build>=<YYYY-MM-DD> ... --playwright <build>=<version>,<version> ...

`<dir>/<build>/<reading>/agreement.json` is what `measure.py --include-unstable --tolerate-census --out` wrote for the reading of that build (`ext-linux`, `devtools-linux`, `devtools-macos`, and the control
`devtools-ubuntu-ci`), and `<dir>/<build>/<reading>-second/agreement.json` the same with `--second` (agreement/measure_readings.sh makes both). The attribution is compare_sources.py's, unchanged, with one cause added:
`chromium build`. This script writes, under `--out`: `<build>/<source>-<os>/agreement.txt` and `misses.json` for every reading, `comparison.txt` and `comparison.json`. With `--list` it also writes the figures into the
supported-versions list, which is the only thing that fills it. Nothing here writes an a11ign evidence field: the output is a measurement of a prediction (ADR 0047)."""
import argparse, collections, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_sources as cs        # noqa: E402

# a reading's name in the work directory, and the key it has in the list and in the figure directory
FIGURE_KEY = {'ext-linux': 'extension-linux', 'devtools-linux': 'devtools-linux', 'devtools-macos': 'devtools-macos', 'devtools-ubuntu-ci': 'devtools-ubuntu-ci'}
LISTED = ('extension-linux', 'devtools-linux', 'devtools-macos')      # the control is reported and never listed
CHANNELS = ('title', 'stops', 'field', 'typed', *cs.LISTS)
# the causes compare_sources.attribute() names before this one in the order of rule.md: a unit that has one of them is not a difference between the builds
BEFORE = ('prompt', 'language', 'history', 'page moved', 'quick test')


def chromium_build(name, k, this, builds, second):
    """The reason the miss at `k` of reading `name` in build `this` is a difference between the builds, or None. `builds` is {build: {reading: Reading}}, `second` the same for the `--second` readings.

    It applies when another build predicts another string for the same unit with the same source on the same captures, and each of the two builds predicted the same string in its second run as in its first
    (so that the difference is the build's and not the run's)."""
    mine = builds[this][name].main[k]
    for other, readings in builds.items():
        if other == this or name not in readings or k not in readings[name].main: continue
        theirs = readings[name].main[k]
        if theirs['predicted'] == mine['predicted']: continue
        steady = all(name in second.get(b, {}) and k in second[b][name].main and second[b][name].main[k]['predicted'] == builds[b][name].main[k]['predicted'] for b in (this, other))
        if steady: return f'Chromium {this} predicted {mine["predicted"]!r}; Chromium {other} predicted {theirs["predicted"]!r}' + (' and agrees' if theirs['ok'] else ' and does not agree either')
    return None


def attribute_builds(builds, second, notes=()):
    """{build: {reading: [miss]}}: compare_sources' attribution inside each build, then `chromium build` for what the builds differ in, then a reader's notes."""
    out = {}
    for build, readings in builds.items():
        attributed = cs.attribute_all(readings)
        out[build] = {}
        for name, misses in attributed.items():
            rows = []
            for m in misses:
                k = (m['address'], m['channel'], m['i'])
                cause, reason, read = m['cause'], m['reason'], False
                if cause not in BEFORE:
                    why = chromium_build(name, k, build, builds, second)
                    if why: cause, reason = 'chromium build', why
                cause, reason, read = cs.apply_notes(cause, reason, name, k, readings[name].main[k], notes)
                rows.append({**m, 'cause': cause, 'reason': reason, 'read': read})
            out[build][name] = rows
    return out


def render_build(build, readings, second, attributed):
    """(the text of one build's section of comparison.txt, what the extension buys there). The tables are compare_sources.py's own."""
    names = [n for n in cs.READINGS if n in readings]
    lines = [f'## Chromium {build}', *cs.headline_lines(readings, second, names)]
    result = None
    if 'ext-linux' in readings and 'devtools-linux' in readings:
        ext, dev = readings['ext-linux'], readings['devtools-linux']
        result = cs.buys(ext, dev)
        result.pop('recommendation'); result.pop('margin')       # this ticket has no margin and no recommendation: the lead is reported (rule.md)
        second_lead = cs.buys(second['ext-linux'], second['devtools-linux']) if 'ext-linux' in second and 'devtools-linux' in second else None
        if second_lead: result['secondLeadPoints'] = second_lead['leadPoints']
        by_channel, result['byChannel'] = cs.lead_by_channel_lines(ext, dev)
        lines += ['\n# what the extension buys over DevTools on this host (the units both readings compare); reported, with no margin and no recommendation', *cs.lead_lines(result, second_lead), *by_channel]
    lines += cs.by_channel_lines(readings, names)
    lines += cs.by_shape_lines(readings, names, cs.top_shapes([r for rd in readings.values() for r in rd.main.values()]))
    lines += cs.cause_count_lines(names, attributed)
    return '\n'.join(line.rstrip() for line in lines), result


def differ_between_builds(builds):
    """Per reading, the units both builds compare, and the ones where they predicted another string: how much the builds differ from each other, whatever the oracle says."""
    out = {}
    names = sorted({n for rs in builds.values() for n in rs}, key=cs.READINGS.index)
    keys = sorted(builds, reverse=True)      # the list has two builds; with more, the two newest are compared
    for n in names:
        if len(keys) < 2 or not all(n in builds[b] for b in keys[:2]): continue
        a, b = builds[keys[0]][n], builds[keys[1]][n]
        both = [k for k in a.main if k in b.main]
        out[n] = {'units': len(both), 'predictionsDiffer': sum(a.main[k]['predicted'] != b.main[k]['predicted'] for k in both),
                  'agreeInOneOnly': sum(a.main[k]['ok'] != b.main[k]['ok'] for k in both)}
    return out


def fill_list(listing, figures, dates, playwright):
    """`listing` (supported-versions.json) with each build's figures: `figures` is {build: {key: (agreed, units, figure path)}}, `dates` {build: day}, `playwright` {build: [versions]}. The rate is the one `agreement.txt` prints (one decimal of a percent, as measure.py rounds it), so that the list and the figure never read differently. A build already listed is replaced."""
    builds = []
    for build in sorted(figures, key=lambda b: [int(x) for x in b.split('.')], reverse=True):
        measured = {key: {'agreement': round(float(f'{100 * agreed / units:.1f}') / 100, 3), 'units': units, 'date': dates[build], 'figure': path} for key, (agreed, units, path) in figures[build].items() if key in LISTED and units}
        builds.append({'chromium': build, 'playwright': playwright[build], 'measured': dict(sorted(measured.items()))})
    return {**listing, 'builds': builds + [b for b in listing.get('builds', []) if b['chromium'] not in figures]}


def load_builds(work):
    """({build: {reading: Reading}}, the same for the `--second` readings) of every build directory in `work`."""
    def load(build, name):
        path = os.path.join(work, build, name, 'agreement.json')
        if not os.path.exists(path): return None
        with open(path) as f: return cs.Reading(name, json.load(f))
    found = sorted(d for d in os.listdir(work) if os.path.isdir(os.path.join(work, d)) and d[:1].isdigit())
    builds = {b: {n: r for n in cs.READINGS if (r := load(b, n))} for b in found}
    second = {b: {n: r for n in cs.READINGS if (r := load(b, f'{n}-second'))} for b in found}
    for b in found:
        if 'ext-linux' not in builds[b] or 'devtools-linux' not in builds[b]: sys.exit(f'compare_builds.py: Chromium {b} needs ext-linux and devtools-linux in --work')
    return builds, second


def render_all(builds, second, attributed, between):
    """(the text of comparison.txt, {build: what the extension buys there})."""
    texts, results = [], {}
    for b in sorted(builds, reverse=True):
        text, results[b] = render_build(b, builds[b], second[b], attributed[b])
        texts.append(text)
    tail = ['## the builds against each other (the units both compare, the first fleet capture against the first run)']
    for n, d in between.items(): tail.append(f"  {n:<20} {d['units']:>5} units: the two builds predicted another string for {d['predictionsDiffer']}; the oracle agrees with one build only on {d['agreeInOneOnly']}")
    tail.append('\n## causes by build and reading (misses)')
    for b in sorted(builds, reverse=True):
        for n, ms in attributed[b].items():
            c = collections.Counter(m['cause'] for m in ms)
            tail.append(f'  {b} {n:<20} ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
    return '\n\n'.join([*texts, '\n'.join(tail)]), results


def write_figure(work, out, build, name, reading, misses):
    """`<out>/<build>/<source>-<os>/{misses.json,agreement.txt}` of one reading; returns its place in the list: (agreed, units, path)."""
    key = FIGURE_KEY[name]
    d = os.path.join(out, build, key); os.makedirs(d, exist_ok=True)
    counts = collections.Counter((r['channel'], bool(r['ok'])) for r in reading.main.values())
    with open(os.path.join(d, 'misses.json'), 'w') as f:
        json.dump({'status': reading.status, 'units': {ch: [counts[(ch, True)], counts[(ch, True)] + counts[(ch, False)]] for ch in sorted({c for c, _ in counts})}, 'misses': misses}, f, indent=1, ensure_ascii=False)
    src = os.path.join(work, build, name, 'agreement.txt')
    if os.path.exists(src): shutil.copy(src, os.path.join(d, 'agreement.txt'))
    return key, (*cs.headline(reading), f'middleware/results/playwright-versions/{build}/{key}/')


def summarize(build, readings, second, results, attributed):
    return {'readings': {n: dict(zip(('agreed', 'units'), cs.headline(r))) for n, r in readings.items()}, 'second': {n: dict(zip(('agreed', 'units'), cs.headline(r))) for n, r in second.items()},
            'extensionBuys': results, 'causes': {n: dict(collections.Counter(m['cause'] for m in ms)) for n, ms in attributed.items()}}


def update_list(path, figures, dates, playwright):
    dates = dict(x.split('=', 1) for x in dates); playwright = {k: v.split(',') for k, v in (x.split('=', 1) for x in playwright)}
    missing = [b for b in figures if b not in dates or b not in playwright]
    if missing: sys.exit(f'compare_builds.py: --list needs --dates and --playwright for {missing}')
    with open(path) as f: listing = json.load(f)
    with open(path, 'w') as f: json.dump(fill_list(listing, figures, dates, playwright), f, indent=2); f.write('\n')


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--out', required=True); ap.add_argument('--notes')
    ap.add_argument('--list'); ap.add_argument('--dates', nargs='*', default=[], metavar='BUILD=DAY'); ap.add_argument('--playwright', nargs='*', default=[], metavar='BUILD=V,V')
    a = ap.parse_args(argv)
    builds, second = load_builds(a.work)
    attributed = attribute_builds(builds, second, cs.load_notes(a.notes))
    between = differ_between_builds(builds)
    text, results = render_all(builds, second, attributed, between)
    print(text)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'comparison.txt'), 'w') as f: f.write(text + '\n')
    figures = {b: dict(write_figure(a.work, a.out, b, n, builds[b][n], ms) for n, ms in attributed[b].items()) for b in builds}
    summary = {'builds': {b: summarize(b, builds[b], second[b], results[b], attributed[b]) for b in builds}, 'betweenBuilds': between}
    with open(os.path.join(a.out, 'comparison.json'), 'w') as f: json.dump(summary, f, indent=1)
    if a.list: update_list(a.list, figures, a.dates, a.playwright)
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
