"""A reading of the structure measurement's misses made after the figure (A11-229, step 2), not a part of the frozen rule: which fields make the difference where the two sources disagree, and which units only DevTools
read because the extension gave no reading of the page.

    python3 fields_after_the_figure.py --work <dir> --classes <pages.json> [--write-notes attribution-notes.json]

`<dir>/ext-linux/agreement.json` and `<dir>/devtools-linux/agreement.json` are what `measure.py` wrote (the same input as compare_sources.py). It prints, for each class of page and for all:
  * the discordant units: where the extension agrees and DevTools does not, by the field in which DevTools's string differs from the fleet's (compare_sources.fields_differing), and where DevTools agrees and the
    extension does not, by the field, or `no prediction` when the extension predicted nothing for the unit;
  * the units of pages the extension gave no reading of, which the paired comparison leaves out: DevTools's misses there, and how many of them are the fleet's string with words missing (`words missing`: every
    token DevTools spoke is in the fleet's, and the fleet's has the unit's `row N` or `column N`), the signature of the header text a table cell is spoken with.
`--write-notes` writes, for DevTools's misses on those pages that are `words missing`, a reader's attribution note for compare_sources.py (`conversion: name`, with the evidence in its reason): a cause the rule
cannot assign by itself because the extension has no reading to agree where DevTools does not. The notes change no figure and no count of agreed units (rule.md, 'Attribution').
Nothing here writes an a11ign evidence field: the output is a measurement of a prediction (ADR 0047)."""
import argparse, collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_sources as cs

INDEX = re.compile(r'^(row|column) \d+$')


def words_missing(expected, predicted):
    """True when `predicted` is `expected` with tokens left out, and `expected` carries a row or column index: the cell was spoken without the words NVDA speaks with it."""
    if predicted is None: return False
    e, p = cs.tokens(expected), cs.tokens(predicted)
    left = list(e)
    for t in p:
        if t not in left: return False
        left.remove(t)
    return bool(left) and any(INDEX.match(t) for t in e) and any(INDEX.match(t) for t in p)


def discordant(ext, dev, classes):
    """{class: {'extension only': Counter(field), 'devtools only': Counter(field)}} over the units both readings compare, plus 'all'."""
    out = collections.defaultdict(lambda: {'extension only': collections.Counter(), 'devtools only': collections.Counter()})
    for a, b in cs.paired(ext, dev):
        if a['ok'] == b['ok']: continue
        if a['ok']: field = cs.fields_differing(b['predicted'], b['expected']) if b['predicted'] is not None else 'no prediction'; side = 'extension only'
        else: field = cs.fields_differing(a['predicted'], a['expected']) if a['predicted'] is not None else 'no prediction'; side = 'devtools only'
        for label in (classes.get(a['address'], '?'), 'all'): out[label][side][field] += 1
    return out


def unread(ext, dev, classes):
    """DevTools's units on pages the extension has no unit of: {address: [units, misses, words missing]}."""
    pages = {a['address'] for a in ext.main.values()}
    out = collections.defaultdict(lambda: [0, 0, 0])
    for k, row in dev.main.items():
        if k[0] in pages: continue
        c = out[k[0]]; c[0] += 1
        if not row['ok']: c[1] += 1; c[2] += words_missing(row['expected'], row['predicted'])
    return out


def notes(ext, dev):
    """A reader's attribution note for each DevTools miss on a page the extension has no unit of whose string is the fleet's with words missing."""
    pages = {a['address'] for a in ext.main.values()}
    return [{'reading': 'devtools-linux', 'address': k[0], 'channel': k[1], 'contains': row['expected'], 'cause': 'conversion: name',
             'reason': 'read after the figure: the spoken string is the fleet\'s with words missing around the cell\'s row or column index (the header text NVDA speaks with a table cell); the extension has no reading of the page, so no source agrees where DevTools does not'}
            for k, row in dev.main.items() if k[0] not in pages and not row['ok'] and words_missing(row['expected'], row['predicted'])]


def render(ext, dev, classes):
    lines = []
    for label, sides in sorted(discordant(ext, dev, classes).items(), key=lambda kv: (kv[0] == 'all', kv[0])):
        lines.append(f'{label} pages: the extension agrees and DevTools does not {sum(sides["extension only"].values())}; DevTools agrees and the extension does not {sum(sides["devtools only"].values())}')
        for side in ('extension only', 'devtools only'):
            lines.append(f'  {side}: ' + (', '.join(f'{f} {n}' for f, n in sides[side].most_common()) or 'none'))
    lines.append('pages the extension gave no reading of (left out of the paired comparison): DevTools units, misses, and misses that are the fleet\'s string with words missing')
    for address, (units, misses, missing) in sorted(unread(ext, dev, classes).items()):
        lines.append(f'  {address}: {units} units, {misses} missed, {missing} with words missing')
    return '\n'.join(lines)


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--classes', required=True); ap.add_argument('--write-notes')
    a = ap.parse_args(argv)
    def load(name):
        with open(os.path.join(a.work, name, 'agreement.json')) as f: return cs.Reading(name, json.load(f))
    with open(a.classes) as f: classes = {p['address']: p['class'] for p in json.load(f)['sample']}
    ext, dev = load('ext-linux'), load('devtools-linux')
    print(render(ext, dev, classes))
    if a.write_notes:
        with open(a.write_notes, 'w') as f: json.dump(notes(ext, dev), f, indent=1, ensure_ascii=False); f.write('\n')
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
