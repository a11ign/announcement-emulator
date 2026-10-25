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
    lines = []
    out = lines.append
    names = [n for n in cs.READINGS if n in readings]
    out(f'## Chromium {build}')
    out('# the readings, the headline: every channel, the first fleet capture against the first passive run')
    for n in names:
        ok, tot = cs.headline(readings[n]); s_ok, s_tot = cs.headline(second[n]) if n in second else (0, 0)
        out(f'  {n:<20} {ok:>5} of {tot:<5} = {cs.rate(ok, tot):>6}' + (f'    second capture against second run: {s_ok} of {s_tot} = {cs.rate(s_ok, s_tot)}' if n in second else ''))
    result = None
    if 'ext-linux' in readings and 'devtools-linux' in readings:
        ext, dev = readings['ext-linux'], readings['devtools-linux']
        result = cs.buys(ext, dev)
        result.pop('recommendation'); result.pop('margin')       # this ticket has no margin and no recommendation: the lead is reported (rule.md)
        out('\n# what the extension buys over DevTools on this host (the units both readings compare); reported, with no margin and no recommendation')
        out(f"  units {result['units']}: extension {result['extension']} ({cs.rate(result['extension'], result['units'])}), DevTools {result['devtools']} ({cs.rate(result['devtools'], result['units'])}), lead {result['leadPoints']:+.1f} points")
        out(f"  discordant units: the extension agrees and DevTools does not {result['extensionOnly']}; DevTools agrees and the extension does not {result['devtoolsOnly']}")
        if 'ext-linux' in second and 'devtools-linux' in second:
            s = cs.buys(second['ext-linux'], second['devtools-linux'])
            result['secondLeadPoints'] = s['leadPoints']
            out(f"  the noise: the same lead from the second capture against the second run {s['leadPoints']:+.1f} points ({s['extension']} against {s['devtools']} of {s['units']})")
        result['byChannel'] = cs.lead_by(ext, dev, lambda x: x['channel'], CHANNELS)
        for r in result['byChannel']:
            out(f"    {r['label']:<11} {r['extension']:>4} / {r['devtools']:>4} of {r['units']:<4} {cs.rate(r['extension'], r['units']):>6} / {cs.rate(r['devtools'], r['units']):>6}  lead {100 * (r['extension'] - r['devtools']) / r['units']:+.1f}")
    out('\n# the readings side by side, by channel (agreed of units, the fleet against itself in brackets)')
    out(f'  {"":<11} ' + ' | '.join(f'{n:<{cs.CELL}}' for n in names))
    for ch in CHANNELS:
        cells = []
        for n in names:
            t = cs.tally([r for r in readings[n].main.values() if r['channel'] == ch], lambda r: 0).get(0, [0, 0])
            f = cs.tally([r for r in readings[n].fleet.values() if r['channel'] == ch], lambda r: 0).get(0, [0, 0])
            cells.append(f'{t[0]:>3}/{t[1]:<3} {cs.rate(*t):>6} ({cs.rate(*f)})'.ljust(cs.CELL))
        out(f'  {ch:<11} ' + ' | '.join(cells))
    ranked = cs.top_shapes([r for rd in readings.values() for r in rd.main.values()])
    out(f'\n# the readings side by side, by shape (the {cs.TOP} commonest)')
    out(f'  {"":<44} ' + ' | '.join(f'{n:<{cs.CELL}}' for n in names))
    for sh in ranked:
        cells = []
        for n in names:
            t = cs.tally([r for r in readings[n].main.values() if cs.shape_name(r) == sh], lambda r: 0).get(0, [0, 0])
            f = cs.tally([r for r in readings[n].fleet.values() if cs.shape_name(r) == sh], lambda r: 0).get(0, [0, 0])
            cells.append(f'{t[0]:>3}/{t[1]:<3} {cs.rate(*t):>6} ({cs.rate(*f)})'.ljust(cs.CELL))
        out(f'  {sh[:44]:<44} ' + ' | '.join(cells))
    out('\n# every miss has one cause (count of misses)')
    for n in names:
        c = collections.Counter(m['cause'] for m in attributed[n])
        out(f'  {n}: {len(attributed[n])} misses; ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
        out(f"    unexplained {c['unexplained']} of {len(attributed[n])}; read by a person (attribution-notes.json) {sum(m['read'] for m in attributed[n])}")
    return '\n'.join(lines), result


def differ_between_builds(builds):
    """Per reading, the units both builds compare, and the ones where they predicted another string: how much the builds differ from each other, whatever the oracle says."""
    out = {}
    names = sorted({n for rs in builds.values() for n in rs}, key=cs.READINGS.index)
    keys = list(builds)
    for n in names:
        if len(keys) < 2 or not all(n in builds[b] for b in keys[:2]): continue
        a, b = builds[keys[0]][n], builds[keys[1]][n]
        both = [k for k in a.main if k in b.main]
        out[n] = {'units': len(both), 'predictionsDiffer': sum(a.main[k]['predicted'] != b.main[k]['predicted'] for k in both),
                  'agreeInOneOnly': sum(a.main[k]['ok'] != b.main[k]['ok'] for k in both)}
    return out


def fill_list(listing, figures, dates, playwright):
    """`listing` (supported-versions.json) with each build's figures: `figures` is {build: {key: (agreed, units, figure path)}}, `dates` {build: day}, `playwright` {build: [versions]}. A build already listed is replaced."""
    builds = []
    for build in sorted(figures, key=lambda b: [int(x) for x in b.split('.')], reverse=True):
        measured = {key: {'agreement': round(agreed / units, 4), 'units': units, 'date': dates[build], 'figure': path} for key, (agreed, units, path) in figures[build].items() if key in LISTED and units}
        builds.append({'chromium': build, 'playwright': playwright[build], 'measured': dict(sorted(measured.items()))})
    return {**listing, 'builds': builds + [b for b in listing.get('builds', []) if b['chromium'] not in figures]}


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--out', required=True); ap.add_argument('--notes')
    ap.add_argument('--list'); ap.add_argument('--dates', nargs='*', default=[], metavar='BUILD=DAY'); ap.add_argument('--playwright', nargs='*', default=[], metavar='BUILD=V,V')
    a = ap.parse_args(argv)

    def load(build, name):
        path = os.path.join(a.work, build, name, 'agreement.json')
        if not os.path.exists(path): return None
        with open(path) as f: return cs.Reading(name, json.load(f))
    builds_found = sorted(d for d in os.listdir(a.work) if os.path.isdir(os.path.join(a.work, d)) and d[:1].isdigit())
    builds = {b: {n: r for n in cs.READINGS if (r := load(b, n))} for b in builds_found}
    second = {b: {n: r for n in cs.READINGS if (r := load(b, f'{n}-second'))} for b in builds_found}
    for b in builds_found:
        if 'ext-linux' not in builds[b] or 'devtools-linux' not in builds[b]: sys.exit(f'compare_builds.py: Chromium {b} needs ext-linux and devtools-linux in --work')
    attributed = attribute_builds(builds, second, cs.load_notes(a.notes))
    texts, results = [], {}
    for b in sorted(builds, reverse=True):
        text, results[b] = render_build(b, builds[b], second[b], attributed[b])
        texts.append(text)
    between = differ_between_builds(builds)
    tail = ['## the builds against each other (the units both compare, the first fleet capture against the first run)']
    for n, d in between.items(): tail.append(f"  {n:<20} {d['units']:>5} units: the two builds predicted another string for {d['predictionsDiffer']}; the oracle agrees with one build only on {d['agreeInOneOnly']}")
    tail.append('\n## causes by build and reading (misses)')
    for b in sorted(builds, reverse=True):
        for n, ms in attributed[b].items():
            c = collections.Counter(m['cause'] for m in ms)
            tail.append(f'  {b} {n:<20} ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
    text = '\n\n'.join([*texts, '\n'.join(tail)])
    print(text)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'comparison.txt'), 'w') as f: f.write(text + '\n')
    figures = {}
    summary = {'builds': {}, 'betweenBuilds': between}
    for b in builds:
        summary['builds'][b] = {'readings': {n: dict(zip(('agreed', 'units'), cs.headline(r))) for n, r in builds[b].items()}, 'second': {n: dict(zip(('agreed', 'units'), cs.headline(r))) for n, r in second[b].items()},
                                'extensionBuys': results[b], 'causes': {n: dict(collections.Counter(m['cause'] for m in ms)) for n, ms in attributed[b].items()}}
        figures[b] = {}
        for n, ms in attributed[b].items():
            key = FIGURE_KEY[n]
            d = os.path.join(a.out, b, key); os.makedirs(d, exist_ok=True)
            counts = collections.Counter((r['channel'], bool(r['ok'])) for r in builds[b][n].main.values())
            with open(os.path.join(d, 'misses.json'), 'w') as f:
                json.dump({'status': builds[b][n].status, 'units': {ch: [counts[(ch, True)], counts[(ch, True)] + counts[(ch, False)]] for ch in sorted({c for c, _ in counts})}, 'misses': ms}, f, indent=1, ensure_ascii=False)
            src = os.path.join(a.work, b, n, 'agreement.txt')
            if os.path.exists(src): shutil.copy(src, os.path.join(d, 'agreement.txt'))
            agreed, units = cs.headline(builds[b][n])
            figures[b][key] = (agreed, units, f'middleware/results/playwright-versions/{b}/{key}/')
    with open(os.path.join(a.out, 'comparison.json'), 'w') as f: json.dump(summary, f, indent=1)
    if a.list:
        dates = dict(x.split('=', 1) for x in a.dates); playwright = {k: v.split(',') for k, v in (x.split('=', 1) for x in a.playwright)}
        missing = [b for b in builds if b not in dates or b not in playwright]
        if missing: sys.exit(f'compare_builds.py: --list needs --dates and --playwright for {missing}')
        with open(a.list) as f: listing = json.load(f)
        with open(a.list, 'w') as f: json.dump(fill_list(listing, figures, dates, playwright), f, indent=2); f.write('\n')
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
