"""A11-229, step 4: the DevTools tree source measured against the fleet on 19 pages, under the rule frozen first (middleware/results/devtools-source/rule.md). One source, so there is no margin and no gate.

    python3 compare_devtools.py --work <dir> --pages <pages.json> --out <dir> [--notes attribution-notes.json] [--cost cost.json] [--old <step 1 dir> <step 2 dir>]

`<dir>/<reading>/agreement.json` is what `measure.py --include-unstable --tolerate-census --out` wrote for the reading (`devtools-linux`, and when they exist `devtools-macos`, `devtools-ubuntu-ci`);
`<dir>/<reading>-second/agreement.json` is the same with `--second`. `--pages` is `make_devtools_pages.py`'s file (its `group` and `class` of each page). This script applies the rule's attribution and tables
mechanically and writes, under `--out`: `figure-<reading>/misses.json` (every miss with one cause), `figure-<reading>/agreement.txt` (copied from the work directory), `comparison.txt` and `comparison.json`.
It prints, beside the figure and labelled as another window: the DevTools figures of steps 1 and 2 on the same pages, the units each item of the work list recovered, the extension's old figures on the table pages,
and (with `--cost`, summarize_cost.py's output) what the runs cost beside step 2's. Nothing here writes an a11ign evidence field: the output is a measurement of a prediction (ADR 0047)."""
import argparse, collections, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_sources as cs
import fields_after_the_figure as fa

READINGS = ('devtools-linux', 'devtools-macos', 'devtools-ubuntu-ci')
OLD_DIRS = ('tree-source', 'tree-source-structure')      # steps 1 and 2, under middleware/results
OLD_GROUPS = ('step 1', 'step 2')
WORK_ITEMS = ('clickable', 'typed value', 'description words', 'header words')

# the closed list of causes, in the order they are assigned (rule.md, 'Attribution'); the extension-only causes of step 1 (`tree:`) do not occur
PLAIN_CAUSES = ('prompt', 'language', 'history', 'page moved', 'quick test', 'network/runner', 'emulator', 'oracle milestone', 'focus match', 'no counterpart', 'unexplained')
PREFIXED_CAUSES = ('conversion', 'events', 'macos')


def is_cause(cause):
    head = cause.split(':')[0]
    return cause in PLAIN_CAUSES or (head in PREFIXED_CAUSES and ': ' in cause)


def load_json(path):
    with open(path) as f: return json.load(f)


# ---- what the earlier extension readings missed

def old_extension_misses(old_dirs):
    """{(address, channel, expected, predicted)} of the units the extension missed in steps 1 and 2, with the string it predicted. The extension is not read in this measurement: this is only what it was seen to get
    wrong in an earlier window, on the same pages, so that a DevTools miss the extension made the same way is not given to the DevTools source."""
    out = set()
    for directory in old_dirs:
        path = os.path.join(directory, 'figure-ext-linux', 'misses.json')
        if not os.path.exists(path): continue
        for m in load_json(path)['misses']: out.add((m['address'], m['channel'], m['expected'], m['predicted']))
    return out


# ---- attribution

def own_cause(name, row, k, readings, old):
    """The cause of a miss of a reading on its own: the extension made it too (`emulator`), else the DevTools source's account (`conversion` for a different string, `events` for none)."""
    address, channel, _ = k
    if (address, channel, row['expected'], row['predicted']) in old:
        return 'emulator', 'the extension, in an earlier window (step 1 or 2), predicted this same string for the unit and missed it too'
    if row['predicted'] is not None:
        return f'conversion: {cs.fields_differing(row["predicted"], row["expected"])}', 'DevTools predicted another string; no second tree source says which of the tree and the emulator is at fault'
    if channel in cs.EVENT_CHANNELS: return f'events: {cs.EVENT_CHANNELS[channel]}', 'nothing was predicted for the unit'
    return 'conversion: node', 'the DevTools tree has no node for the unit'


def attribute(readings, name, k, old):
    """(cause, reason) of the miss at `k` in the reading `name`, by the rule's order. `readings` is {name: Reading}."""
    me, row = readings[name], readings[name].main[k]
    if row['class'] in ('prompt', 'language', 'history'): return row['class'], ''
    if k in me.fleet and not me.fleet[k]['ok']: return 'page moved', 'the second fleet capture does not have this unit'
    address, channel, i = k
    if channel in ('stops', 'typed') and row['predicted'] is None and i == me.last[(address, channel)] and (address, channel) in me.runs_differ:
        return 'quick test', 'the last unit, nothing predicted, and the two runs differ in the channel'
    linux = readings.get('devtools-linux')
    if name != 'devtools-linux' and linux is not None and k in linux.main:
        control, p_here, p_linux = readings.get('devtools-ubuntu-ci'), row['predicted'], linux.main[k]['predicted']
        if name == 'devtools-ubuntu-ci':
            if p_here != p_linux: return 'network/runner', 'the control predicts what this host does not'
        elif control is not None and k in control.main:
            p_control = control.main[k]['predicted']
            if p_here != p_control: return f'macos: {cs.fields_differing(p_here, p_control) if p_here is not None and p_control is not None else "node"}', 'macOS and the control predict different strings'
            if p_here != p_linux: return 'network/runner', 'macOS and the control predict the same string, and this host another'
        if p_here == p_linux and not linux.ok(k): return attribute(readings, 'devtools-linux', k, old)
        if p_here != p_linux: return 'unexplained', 'predicts another string than this host and there is no control reading of the unit'
        return 'unexplained', 'this host agrees on the unit and this reading does not'
    return own_cause(name, row, k, readings, old)


def attribute_all(readings, old, notes=()):
    """{reading: [miss]} with `cause`, `reason` and `read` (true when a reader's note gave the cause)."""
    out = {}
    for name, rd in readings.items():
        out[name] = []
        for k, row in rd.main.items():
            if row['ok']: continue
            cause, reason = attribute(readings, name, k, old)
            cause, reason, read = cs.apply_notes(cause, reason, name, k, row, notes)
            out[name].append({'address': k[0], 'channel': k[1], 'i': k[2], 'expected': row['expected'], 'predicted': row['predicted'], 'measureClass': row['class'], 'cause': cause, 'reason': reason,
                              'read': read, 'shape': row['shape'], 'stable': row.get('stable', True)})
    return out


# ---- the work list of the chairman's decision: what a miss of each kind is

def work_item(channel, expected, predicted):
    """Which item of the work list a missed unit is, or None: `clickable` (the token differs), `header words` (the cell's string with words missing around its `row N` / `column N`), `typed value` (a miss of
    the field or typed channel), `description words` (the predicted tokens are all in the fleet's string and some of the fleet's are not predicted). A reading of the tokens, not a proof of the cause."""
    if predicted is None: return None
    if 'clickable' in cs.fields_differing(predicted, expected).split('+'): return 'clickable'
    if fa.words_missing(expected, predicted): return 'header words'
    if channel in ('field', 'typed'): return 'typed value'
    e, p = cs.tokens(expected), cs.tokens(predicted)
    left = list(e)
    for t in p:
        if t in left: left.remove(t)
        else: return None
    return 'description words' if left else None


def work_counts(misses, groups, wanted):
    """{item: units} of the misses on pages of the groups `wanted`."""
    c = collections.Counter(work_item(m['channel'], m['expected'], m['predicted']) for m in misses if groups.get(m['address']) in wanted)
    return {item: c[item] for item in WORK_ITEMS}


def old_misses(old_dirs):
    out = []
    for directory in old_dirs:
        path = os.path.join(directory, 'figure-devtools-linux', 'misses.json')
        if os.path.exists(path): out += load_json(path)['misses']
    return out


def old_headline(old_dirs):
    """(agreed, units) of the DevTools headline of steps 1 and 2 added, from their comparison.json."""
    agreed = units = 0
    for directory in old_dirs:
        path = os.path.join(directory, 'comparison.json')
        if os.path.exists(path):
            r = load_json(path)['readings']['devtools-linux']; agreed += r['agreed']; units += r['units']
    return agreed, units


def old_extension_table(old_dirs):
    """(extension agreed, DevTools agreed, units) on the table pages of step 2, from its comparison.json, or None."""
    path = os.path.join(old_dirs[-1], 'comparison.json')
    if not os.path.exists(path): return None
    for c in load_json(path)['extensionBuys'].get('byClass', []):
        if c['label'] == 'table': return c['extension'], c['devtools'], c['units']
    return None


# ---- the figures

def selected(rd, address_ok):
    """(main rows, fleet-against-itself rows) of the reading on pages `address_ok` says yes to."""
    return [r for r in rd.main.values() if address_ok(r['address'])], [r for r in rd.fleet.values() if address_ok(r['address'])]


def share(rows): return sum(r['ok'] for r in rows), len(rows)


def cell(rows, fleet_rows):
    ok, n = share(rows); fok, fn = share(fleet_rows)
    return f'{ok:>5} of {n:<5} {cs.rate(ok, n):>6}   (the fleet against itself {cs.rate(fok, fn)})'


def figure_lines(readings, second, pages):
    """The headline of each reading: all 19 pages, the 14 of steps 1 and 2, by group and by class of page."""
    groups = {p['url']: p['group'] for p in pages}
    classes = {p['url']: p['class'] for p in pages}
    names = [n for n in READINGS if n in readings]
    lines = ['# the readings, the headline: every channel, the first fleet capture against the first passive run']
    scopes = [('all 19 pages', lambda a: True), ('the 14 pages of steps 1 and 2', lambda a: groups.get(a) in OLD_GROUPS)]
    scopes += [(f'group {g}', lambda a, g=g: groups.get(a) == g) for g in dict.fromkeys(groups.values())]
    scopes += [(f'class {c}', lambda a, c=c: classes.get(a) == c) for c in dict.fromkeys(classes.values())]
    for label, ok_address in scopes:
        lines.append(f'  {label}')
        for n in names:
            lines.append(f'    {n:<20} ' + cell(*selected(readings[n], ok_address)))
        if label == 'all 19 pages':
            for n in names:
                if n in second: lines.append(f'    {n + " second":<20} ' + cell(*selected(second[n], ok_address)) + '   second capture against second run')
    return lines


def work_list_lines(attributed, groups, old_dirs):
    """The units each item of the work list cost in steps 1 and 2 (DevTools on Linux, on their pages) and cost now on the same pages. Another window, so another page state: the difference is a reading, not a proof."""
    lines = ['\n# the work list of the chairman\'s decision, in units missed on the 14 pages of steps 1 and 2 (another window: steps 1 and 2\'s DevTools reading, and this one)']
    old = old_misses(old_dirs)
    if not old: return lines + ['  (no earlier DevTools misses to set beside)'], {}
    before = work_counts(old, groups, OLD_GROUPS)
    after = work_counts(attributed['devtools-linux'], groups, OLD_GROUPS)
    out = {}
    lines.append(f'  {"item":<20} {"before":>7} {"now":>5} {"recovered":>10}')
    for item in WORK_ITEMS:
        out[item] = {'before': before[item], 'after': after[item], 'recovered': before[item] - after[item]}
        lines.append(f'  {item:<20} {before[item]:>7} {after[item]:>5} {before[item] - after[item]:>10}')
    ok, n = old_headline(old_dirs)
    lines.append(f'  the DevTools headline of steps 1 and 2 on these pages: {ok} of {n} = {cs.rate(ok, n)} (the two figures added; not the same window)')
    return lines, out


def extension_context_lines(old_dirs, readings, pages):
    """The extension's old lead on the table pages beside this reading's DevTools figure on them; labelled as another window."""
    table = old_extension_table(old_dirs)
    if not table: return []
    classes = {p['url']: p['class'] for p in pages}
    ext, dev, n = table
    rows = [r for r in readings['devtools-linux'].main.values() if classes.get(r['address']) == 'table']
    ok, units = share(rows)
    return ['\n# the extension on the table pages (context: it is not read in this measurement; step 2\'s window, over the units it and DevTools both read)',
            f'  step 2: the extension {ext} of {n} = {cs.rate(ext, n)}, DevTools {dev} of {n} = {cs.rate(dev, n)}',
            f'  now: DevTools {ok} of {units} = {cs.rate(ok, units)} on the table pages (all the units of those pages, four pages)']


def cost_lines(cost, old_runs, step2_cost):
    """What the runs cost, by project, beside step 2's. `cost` is summarize_cost.py's output for the runs, labelled `<project>-<n>`."""
    if not cost: return []
    lines = ['\n# the cost of the runs on this host (wall time, the runtime finishing after the last test, the predictor, the tree reads), in seconds']
    for label in sorted(cost):
        r = cost[label]; reads = r['reads']
        lines.append(f"  {label:<12} wall {r['wallMs'] / 1000:>7.1f}  after the last test {(r['drainMs'] or 0) / 1000:>7.1f}  speechMs {r['speechMs'] / 1000:>7.1f}  reads {reads['count']:>3} ({reads['full']} full, {reads['incremental']} incremental) {reads['totalMs'] / 1000:>6.1f} s")
    if step2_cost:
        for label in ('structure-before', 'structure-after', 'large-after'):
            if label in step2_cost:
                r = step2_cost[label]
                lines.append(f"  step 2's {label:<17} wall {r['wallMs'] / 1000:>7.1f}  speechMs {r['speechMs'] / 1000:>7.1f}  reads {r['reads']['count']} {r['reads']['totalMs'] / 1000:.1f} s")
    if old_runs:
        walls = {k: v['wallMs'] / 1000 for k, v in old_runs.items() if k.startswith(('devtools', 'ext'))}
        lines.append('  step 2 (the first measurement), wall time of the structure project: ' + ', '.join(f'{k} {v:.0f} s' for k, v in sorted(walls.items())))
    return lines


def causes_by_shape_lines(attributed, names, ranked):
    out = ['\n# the causes by shape (the ten commonest), one block per reading']
    for n in names:
        out.append(f'  {n}')
        for sh in ranked:
            c = collections.Counter(m['cause'] for m in attributed[n] if ' + '.join(m['shape']) == sh)
            if c: out.append(f'    {sh[:44]:<44} ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
        rest = collections.Counter(m['cause'] for m in attributed[n] if ' + '.join(m['shape']) not in ranked)
        if rest: out.append(f'    {"(other shapes)":<44} ' + ', '.join(f'{k} {v}' for k, v in rest.most_common()))
    return out


def render(readings, second, attributed, pages, old_dirs, cost=None, old_runs=None, step2_cost=None):
    names = [n for n in READINGS if n in readings]
    groups = {p['url']: p['group'] for p in pages}
    lines = figure_lines(readings, second, pages)
    lines += cs.by_channel_lines(readings, names)
    ranked = cs.top_shapes([r for rd in readings.values() for r in rd.main.values()])
    lines += cs.by_shape_lines(readings, names, ranked)
    lines += cs.cause_count_lines(names, attributed)
    lines += causes_by_shape_lines(attributed, names, ranked)
    work_lines, work = work_list_lines(attributed, groups, old_dirs) if 'devtools-linux' in attributed else ([], {})
    lines += work_lines
    lines += extension_context_lines(old_dirs, readings, pages) if 'devtools-linux' in readings else []
    lines += cost_lines(cost, old_runs, step2_cost)
    return '\n'.join(lines), work


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--pages', required=True); ap.add_argument('--out', required=True); ap.add_argument('--notes')
    ap.add_argument('--cost', help='summarize_cost.py\'s output for this measurement\'s runs'); ap.add_argument('--old', nargs=2, metavar='DIR', help='the results directories of steps 1 and 2 (default: middleware/results/tree-source and tree-source-structure)')
    a = ap.parse_args(argv)
    results = os.path.join(HERE, '..', 'results')
    old_dirs = a.old or [os.path.join(results, d) for d in OLD_DIRS]

    def load(name):
        path = os.path.join(a.work, name, 'agreement.json')
        if not os.path.exists(path): return None
        return cs.Reading(name, load_json(path))
    readings = {n: r for n in READINGS if (r := load(n))}
    second = {n: r for n in READINGS if (r := load(f'{n}-second'))}
    if 'devtools-linux' not in readings: sys.exit('compare_devtools.py: needs devtools-linux in --work')
    pages = load_json(a.pages)['sample']
    attributed = attribute_all(readings, old_extension_misses(old_dirs), cs.load_notes(a.notes))
    step2 = os.path.join(results, 'devtools-source', 'cost', 'summary.json')
    old_runs = os.path.join(old_dirs[-1], 'passive-runs.json')
    text, work = render(readings, second, attributed, pages, old_dirs, cost=load_json(a.cost) if a.cost else None, old_runs=load_json(old_runs) if os.path.exists(old_runs) else None,
                        step2_cost=load_json(step2) if os.path.exists(step2) else None)
    print(text)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'comparison.txt'), 'w') as f: f.write(text + '\n')
    groups = {p['url']: p['group'] for p in pages}; classes = {p['url']: p['class'] for p in pages}

    def by(keyf, rd): return {k: dict(zip(('agreed', 'units'), share([r for r in rd.main.values() if keyf(r) == k]))) for k in dict.fromkeys(keyf({'address': p['url']}) for p in pages)}
    with open(os.path.join(a.out, 'comparison.json'), 'w') as f:
        json.dump({'readings': {n: dict(zip(('agreed', 'units'), cs.headline(r))) for n, r in readings.items()}, 'second': {n: dict(zip(('agreed', 'units'), cs.headline(r))) for n, r in second.items()},
                   'byGroup': {n: by(lambda r: groups.get(r['address']), r) for n, r in readings.items()}, 'byClass': {n: by(lambda r: classes.get(r['address']), r) for n, r in readings.items()},
                   'oldPages': {n: dict(zip(('agreed', 'units'), share([r for r in rd.main.values() if groups.get(r['address']) in OLD_GROUPS]))) for n, rd in readings.items()},
                   'causes': {n: dict(collections.Counter(m['cause'] for m in ms)) for n, ms in attributed.items()}, 'workList': work}, f, indent=1)
    for n, ms in attributed.items():
        d = os.path.join(a.out, f'figure-{n}'); os.makedirs(d, exist_ok=True)
        counts = collections.Counter((r['channel'], bool(r['ok'])) for r in readings[n].main.values())
        with open(os.path.join(d, 'misses.json'), 'w') as f:
            json.dump({'status': readings[n].status, 'units': {ch: [counts[(ch, True)], counts[(ch, True)] + counts[(ch, False)]] for ch in sorted({c for c, _ in counts})}, 'misses': ms}, f, indent=1, ensure_ascii=False)
        src = os.path.join(a.work, n, 'agreement.txt')
        if os.path.exists(src): shutil.copy(src, os.path.join(d, 'agreement.txt'))
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
