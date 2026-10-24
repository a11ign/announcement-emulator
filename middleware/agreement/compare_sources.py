"""A11-229: what the extension's tree buys over the DevTools port's, measured against the fleet, and the recommendation the frozen rule gives (middleware/results/tree-source/rule.md).

    python3 compare_sources.py --work <dir> --out <dir> [--notes attribution-notes.json] [--margin 1.0]

`<dir>/<reading>/agreement.json` is what `measure.py --include-unstable --tolerate-census --out` wrote for the reading (`ext-linux`, `devtools-linux`, and when they exist `devtools-macos`,
`devtools-ubuntu-ci`); `<dir>/<reading>-second/agreement.json` is the same with `--second`. This script applies the rule's margin, attribution and tables mechanically and writes, under `--out`:
`figure-<reading>/misses.json` (every miss with one cause), `figure-<reading>/agreement.txt` (copied from the work directory), `comparison.txt` and `comparison.json`.
Nothing here writes an a11ign evidence field: the output is a measurement of a prediction (ADR 0047)."""
import argparse, collections, json, os, re, shutil, sys

READINGS = ('ext-linux', 'devtools-linux', 'devtools-macos', 'devtools-ubuntu-ci')
MARGIN = 1.0
TOP = 10
CELL = 22      # the width of a cell of the side-by-side tables
LISTS = ('headings', 'landmarks', 'formFields', 'graphics', 'links', 'lists', 'frames')
EVENT_CHANNELS = {'stops': 'focus', 'field': 'focus', 'typed': 'typed'}

# the closed list of causes: the plain ones, and the prefixes of those that carry a field or a kind
PLAIN_CAUSES = ('prompt', 'language', 'history', 'page moved', 'quick test', 'network/runner', 'emulator', 'oracle milestone', 'focus match', 'no counterpart', 'unexplained')
PREFIXED_CAUSES = ('conversion', 'events', 'tree', 'macos')

STATES = {'selected', 'not selected', 'checked', 'not checked', 'half checked', 'expanded', 'collapsed', 'required', 'invalid entry', 'read only', 'unavailable', 'pressed', 'not pressed',
          'has auto complete', 'editable', 'opens list', 'sub Menu', 'blank', 'focused', 'off screen', 'multi line', 'protected', 'busy'}
ROLES = {'link', 'button', 'graphic', 'heading', 'edit', 'combo box', 'list', 'list item', 'frame', 'grouping', 'table', 'check box', 'radio button', 'menu button', 'tab', 'section', 'separator', 'dialog',
         'document', 'article', 'figure', 'toggle button', 'tab control', 'tree view', 'slider', 'spin button', 'region', 'form', 'alert', 'status', 'menu', 'menu item', 'toolbar'}
TOKEN_FIELDS = (
    (re.compile(r'^clickable$'), 'clickable'),
    (re.compile(r'^visited$'), 'visited'),
    (re.compile(r'^\d+ of \d+$'), 'position in set'),
    (re.compile(r'^with \d+ items?$'), 'set size'),
    (re.compile(r'^level \d+$'), 'level'),
    (re.compile(r'^(row|column)( \d+)?$'), 'table index'),
    (re.compile(r'landmark$'), 'landmark'),
)


def is_cause(cause):
    head = cause.split(':')[0]
    return cause in PLAIN_CAUSES or (head in PREFIXED_CAUSES and ': ' in cause)


def tokens(text): return [t.strip() for t in (text or '').split(',')]


def token_field(token):
    for pattern, field in TOKEN_FIELDS:
        if pattern.search(token): return field
    if token in STATES: return 'state'
    if token in ROLES: return 'role'
    return 'name'


def fields_differing(a, b):
    """The fields in which two spoken strings differ: those of the tokens one has and the other has not, `order` when they are the same tokens in another order, joined with `+`."""
    ta, tb = tokens(a), tokens(b)
    if ta == tb: return 'other'
    ca, cb = collections.Counter(ta), collections.Counter(tb)
    odd = list((ca - cb).elements()) + list((cb - ca).elements())
    if not odd: return 'order'
    return '+'.join(sorted({token_field(t) for t in odd}))


def key(row): return (row['address'], row['channel'], row['i'])


class Reading:
    """The rows of one `agreement.json`, indexed: the first fleet capture against the first run (`main`), against the second capture (`fleet`), and the runs against each other."""

    def __init__(self, name, agreement):
        self.name, self.status = name, agreement['status']
        self.main = {key(r): r for r in agreement['rows'] if r['kind'] == 'fleet-vs-passive'}
        self.fleet = {key(r): r for r in agreement['rows'] if r['kind'] == 'fleet-vs-fleet'}
        self.runs_differ = {(r['address'], r['channel']) for r in agreement['rows'] if r['kind'] == 'passive-vs-passive' and not r['ok']}
        self.last = {}
        for k in self.main: self.last[(k[0], k[1])] = max(self.last.get((k[0], k[1]), -1), k[2])

    def ok(self, k): return self.main[k]['ok']


def attribute(readings, name, k):
    """(cause, reason) of the miss at `k` in the reading `name`, by the rule's order (rule.md, 'Attribution'). `readings` is {name: Reading}."""
    me, row = readings[name], readings[name].main[k]
    measure_class = row['class']
    if measure_class in ('prompt', 'language', 'history'): return measure_class, ''
    if k in me.fleet and not me.fleet[k]['ok']: return 'page moved', 'the second fleet capture does not have this unit'
    address, channel, i = k
    if channel in ('stops', 'typed') and row['predicted'] is None and i == me.last[(address, channel)] and (address, channel) in me.runs_differ:
        return 'quick test', 'the last unit, nothing predicted, and the two runs differ in the channel'
    linux = readings.get('devtools-linux')
    if name in ('devtools-macos', 'devtools-ubuntu-ci') and linux is not None and k in linux.main:
        control, p_here, p_linux = readings.get('devtools-ubuntu-ci'), row['predicted'], linux.main[k]['predicted']
        if name == 'devtools-ubuntu-ci':
            if p_here != p_linux: return 'network/runner', 'the control predicts what this host does not'
        elif control is not None and k in control.main:
            p_control = control.main[k]['predicted']
            if p_here != p_control: return f'macos: {fields_differing(p_here, p_control) if p_here is not None and p_control is not None else "node"}', 'macOS and the control predict different strings'
            if p_here != p_linux: return 'network/runner', 'macOS and the control predict the same string, and this host another'
        if p_here == p_linux and not linux.ok(k): return attribute(readings, 'devtools-linux', k)
        if p_here != p_linux: return 'unexplained', 'predicts another string than this host and there is no control reading of the unit'
        return 'unexplained', 'this host agrees on the unit and this reading does not'
    other = readings.get('devtools-linux' if name == 'ext-linux' else 'ext-linux')
    if name in ('ext-linux', 'devtools-linux') and other is not None and k in other.main:
        if not other.ok(k):
            return 'emulator', 'both tree sources miss the unit'
        here, there = row['predicted'], other.main[k]['predicted']
        if name == 'devtools-linux':
            if here is None: return (f'events: {EVENT_CHANNELS[channel]}', 'nothing predicted from the DevTools tree; the extension predicted it') if channel in EVENT_CHANNELS else ('conversion: node', 'the DevTools tree has no node for the unit')
            return f'conversion: {fields_differing(here, row["expected"])}', 'the extension agrees'
        if here is None: return f'tree: {EVENT_CHANNELS.get(channel, "node")}', 'nothing predicted from the extension tree; DevTools predicted it'
        return f'tree: {fields_differing(here, row["expected"])}', 'DevTools agrees'
    if measure_class == 'no counterpart': return 'no counterpart', ''
    return 'unexplained', f'{row["expected"][:60]!r} -> {(row["predicted"] or "")[:60]!r}' + ('' if other is not None else '; no reading of the other source')


def load_notes(path):
    if not path or not os.path.exists(path): return []
    with open(path) as f: notes = json.load(f)
    for n in notes:
        if not is_cause(n['cause']): raise ValueError(f'attribution note names a cause that is not in the rule: {n["cause"]}')
        if not n.get('reason'): raise ValueError(f'attribution note without a reason: {n}')
    return notes


def apply_notes(cause, reason, name, k, row, notes):
    """A reader's attribution of a unit the rules left `unexplained` or `no counterpart`."""
    if cause not in ('unexplained', 'no counterpart'): return cause, reason, False
    for n in notes:
        if n.get('reading', '*') in ('*', name) and n['address'] == k[0] and n['channel'] == k[1] and n.get('contains', '') in row['expected']:
            return n['cause'], n['reason'], True
    return cause, reason, False


def attribute_all(readings, notes=()):
    """{reading: [miss]} with `cause`, `reason` and `read` (true when a reader's note gave the cause)."""
    out = {}
    for name, rd in readings.items():
        out[name] = []
        for k, row in rd.main.items():
            if row['ok']: continue
            cause, reason = attribute(readings, name, k)
            cause, reason, read = apply_notes(cause, reason, name, k, row, notes)
            out[name].append({'address': k[0], 'channel': k[1], 'i': k[2], 'expected': row['expected'], 'predicted': row['predicted'], 'measureClass': row['class'], 'cause': cause, 'reason': reason,
                              'read': read, 'shape': row['shape'], 'stable': row.get('stable', True)})
    return out


# ---- the figures

def rate(ok, n): return f'{100 * ok / n:.1f}%' if n else 'n/a'


def shape_name(row): return ' + '.join(row['shape'])


def tally(rows, keyf):
    t = collections.OrderedDict()
    for r in rows:
        c = t.setdefault(keyf(r), [0, 0]); c[0] += r['ok']; c[1] += 1
    return t


def top_shapes(rows, top=TOP): return [s for s, _ in collections.Counter(shape_name(r) for r in rows).most_common(top)]


def headline(rd): return sum(r['ok'] for r in rd.main.values()), len(rd.main)


def paired(a, b):
    """The units both readings compare: [(row in a, row in b)]."""
    return [(a.main[k], b.main[k]) for k in a.main if k in b.main]


def buys(ext, dev, margin=MARGIN):
    """What the extension buys over DevTools on this host, over the units both compare, in points, and the recommendation the margin gives."""
    pairs = paired(ext, dev)
    n = len(pairs)
    e, d = sum(a['ok'] for a, _ in pairs), sum(b['ok'] for _, b in pairs)
    lead = 100 * (e - d) / n if n else 0.0
    return {'units': n, 'extension': e, 'devtools': d, 'leadPoints': lead, 'extensionOnly': sum(a['ok'] and not b['ok'] for a, b in pairs), 'devtoolsOnly': sum(b['ok'] and not a['ok'] for a, b in pairs),
            'margin': margin, 'recommendation': 'drop the extension' if lead <= margin else 'keep both'}


def lead_by(ext, dev, keyf, order):
    pairs = paired(ext, dev)
    out = []
    for label in order:
        sel = [(a, b) for a, b in pairs if keyf(a) == label]
        if sel: out.append({'label': label, 'units': len(sel), 'extension': sum(a['ok'] for a, _ in sel), 'devtools': sum(b['ok'] for _, b in sel)})
    return out


def recommendation_line(b):
    return (f"recommendation by the frozen rule (the chairman reads it): {b['recommendation'].upper()}: the extension's lead is {b['leadPoints']:+.1f} points ({b['extension']} against {b['devtools']} of {b['units']} units agreed), "
            f"{'at most' if b['leadPoints'] <= b['margin'] else 'above'} the {b['margin']:.1f}-point margin")


def render(readings, second, attributed, margin=MARGIN):
    lines, out = [], None
    out = lines.append
    names = [n for n in READINGS if n in readings]
    out('# the readings, the headline: every channel, the first fleet capture against the first passive run')
    for n in names:
        ok, tot = headline(readings[n]); s_ok, s_tot = headline(second[n]) if n in second else (0, 0)
        out(f'  {n:<20} {ok:>5} of {tot:<5} = {rate(ok, tot):>6}' + (f'    second capture against second run: {s_ok} of {s_tot} = {rate(s_ok, s_tot)}' if n in second else ''))
    result = None
    if 'ext-linux' in readings and 'devtools-linux' in readings:
        ext, dev = readings['ext-linux'], readings['devtools-linux']
        result = buys(ext, dev, margin)
        out('\n# what the extension buys over DevTools on this host (the units both readings compare)')
        out(f"  units {result['units']}: extension {result['extension']} ({rate(result['extension'], result['units'])}), DevTools {result['devtools']} ({rate(result['devtools'], result['units'])}), lead {result['leadPoints']:+.1f} points")
        out(f"  discordant units: the extension agrees and DevTools does not {result['extensionOnly']}; DevTools agrees and the extension does not {result['devtoolsOnly']}")
        if 'ext-linux' in second and 'devtools-linux' in second:
            s = buys(second['ext-linux'], second['devtools-linux'], margin)
            result['second'] = s
            out(f"  the noise: the same lead from the second capture against the second run {s['leadPoints']:+.1f} points ({s['extension']} against {s['devtools']} of {s['units']}); the two leads differ by {abs(result['leadPoints'] - s['leadPoints']):.1f} points")
        pairs = [a for a, _ in paired(ext, dev)]
        out('\n  by channel (extension / DevTools, agreed of units):')
        for r in lead_by(ext, dev, lambda x: x['channel'], ['title', 'stops', 'field', 'typed', *LISTS]):
            out(f"    {r['label']:<11} {r['extension']:>4} / {r['devtools']:>4} of {r['units']:<4} {rate(r['extension'], r['units']):>6} / {rate(r['devtools'], r['units']):>6}  lead {100 * (r['extension'] - r['devtools']) / r['units']:+.1f}")
        shapes = top_shapes(pairs)
        out(f'\n  by shape (the {TOP} commonest of the paired units):')
        result['byShape'] = lead_by(ext, dev, shape_name, shapes)
        for r in result['byShape']:
            out(f"    {r['label'][:58]:<58} {r['extension']:>4} / {r['devtools']:>4} of {r['units']:<4} {rate(r['extension'], r['units']):>6} / {rate(r['devtools'], r['units']):>6}  lead {100 * (r['extension'] - r['devtools']) / r['units']:+.1f}")
        result['byChannel'] = lead_by(ext, dev, lambda x: x['channel'], ['title', 'stops', 'field', 'typed', *LISTS])
        out('\n# ' + recommendation_line(result))
    out('\n# the readings side by side, by channel (agreed of units, the fleet against itself in brackets)')
    out(f'  {"":<11} ' + ' | '.join(f'{n:<{CELL}}' for n in names))
    for ch in ('title', 'stops', 'field', 'typed', *LISTS):
        cells = []
        for n in names:
            t = tally([r for r in readings[n].main.values() if r['channel'] == ch], lambda r: 0).get(0, [0, 0])
            f = tally([r for r in readings[n].fleet.values() if r['channel'] == ch], lambda r: 0).get(0, [0, 0])
            cells.append(f'{t[0]:>3}/{t[1]:<3} {rate(*t):>6} ({rate(*f)})'.ljust(CELL))
        out(f'  {ch:<11} ' + ' | '.join(cells))
    ranked = top_shapes([r for rd in readings.values() for r in rd.main.values()] if not result else [a for a, _ in paired(readings['ext-linux'], readings['devtools-linux'])])
    out(f'\n# the readings side by side, by shape (the {TOP} commonest)')
    out(f'  {"":<44} ' + ' | '.join(f'{n:<{CELL}}' for n in names))
    for sh in ranked:
        cells = []
        for n in names:
            t = tally([r for r in readings[n].main.values() if shape_name(r) == sh], lambda r: 0).get(0, [0, 0])
            f = tally([r for r in readings[n].fleet.values() if shape_name(r) == sh], lambda r: 0).get(0, [0, 0])
            cells.append(f'{t[0]:>3}/{t[1]:<3} {rate(*t):>6} ({rate(*f)})'.ljust(CELL))
        out(f'  {sh[:44]:<44} ' + ' | '.join(cells))
    out('\n# every miss has one cause (count of misses)')
    causes = collections.Counter(m['cause'] for ms in attributed.values() for m in ms)
    for n in names:
        c = collections.Counter(m['cause'] for m in attributed[n])
        out(f'  {n}: {len(attributed[n])} misses; ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
        out(f"    unexplained {c['unexplained']} of {len(attributed[n])}; read by a person (attribution-notes.json) {sum(m['read'] for m in attributed[n])}")
    out('\n# the causes by shape (the ten commonest), one block per reading')
    for n in names:
        out(f'  {n}')
        for sh in ranked:
            c = collections.Counter(m['cause'] for m in attributed[n] if ' + '.join(m['shape']) == sh)
            if c: out(f'    {sh[:44]:<44} ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
        rest = collections.Counter(m['cause'] for m in attributed[n] if ' + '.join(m['shape']) not in ranked)
        if rest: out(f'    {"(other shapes)":<44} ' + ', '.join(f'{k} {v}' for k, v in rest.most_common()))
    out('\n# the work list of the DevTools source (conversion and events misses), by field and kind')
    work = collections.defaultdict(list)
    for n in ('devtools-linux', 'devtools-macos'):
        for m in attributed.get(n, []):
            if m['cause'].startswith(('conversion', 'events')): work[(m['cause'], n)].append(m)
    for (cause, n), ms in sorted(work.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        chans = collections.Counter(m['channel'] for m in ms)
        out(f"  {cause:<34} {n:<16} {len(ms):>3} units  channels: {', '.join(f'{c} {v}' for c, v in chans.most_common())}")
    return '\n'.join(lines), result, work


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--out', required=True); ap.add_argument('--notes'); ap.add_argument('--margin', type=float, default=MARGIN)
    a = ap.parse_args(argv)

    def load(name):
        path = os.path.join(a.work, name, 'agreement.json')
        if not os.path.exists(path): return None
        with open(path) as f: return Reading(name, json.load(f))
    readings = {n: r for n in READINGS if (r := load(n))}
    second = {n: r for n in READINGS if (r := load(f'{n}-second'))}
    if 'ext-linux' not in readings or 'devtools-linux' not in readings: sys.exit('compare_sources.py: needs ext-linux and devtools-linux in --work')
    attributed = attribute_all(readings, load_notes(a.notes))
    text, result, work = render(readings, second, attributed, a.margin)
    print(text)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'comparison.txt'), 'w') as f: f.write(text + '\n')
    with open(os.path.join(a.out, 'comparison.json'), 'w') as f:
        json.dump({'readings': {n: dict(zip(('agreed', 'units'), headline(r))) for n, r in readings.items()}, 'second': {n: dict(zip(('agreed', 'units'), headline(r))) for n, r in second.items()}, 'extensionBuys': result,
                   'causes': {n: dict(collections.Counter(m['cause'] for m in ms)) for n, ms in attributed.items()},
                   'workList': {f'{c} [{n}]': len(ms) for (c, n), ms in work.items()}}, f, indent=1)
    for n, ms in attributed.items():
        d = os.path.join(a.out, f'figure-{n}'); os.makedirs(d, exist_ok=True)
        counts = collections.Counter((r['channel'], bool(r['ok'])) for r in readings[n].main.values())
        with open(os.path.join(d, 'misses.json'), 'w') as f:
            json.dump({'status': readings[n].status, 'units': {ch: [counts[(ch, True)], counts[(ch, True)] + counts[(ch, False)]] for ch in sorted({c for c, _ in counts})}, 'misses': ms}, f, indent=1, ensure_ascii=False)
        src = os.path.join(a.work, n, 'agreement.txt')
        if os.path.exists(src): shutil.copy(src, os.path.join(d, 'agreement.txt'))
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
