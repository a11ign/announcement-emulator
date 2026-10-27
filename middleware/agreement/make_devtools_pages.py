"""The 19 pages of the DevTools measurement (A11-229, step 4), from the three groups the earlier steps measured or left out, in the shape measure.py reads (`sample` with a `url`).

    python3 make_devtools_pages.py <out pages.json>          run from the repository root

group `step 1`: the six pages of results/agreement/pages.json; group `step 2`: the eight table- and list-heavy pages of results/tree-source-structure/pages.json; group `large`: the five pages that file's `rejected`
list left out for their size (705 to 1,770 tab stops) and that the sample suite's `large` project walks. `class` is the structure measurement's (`table`, `list`) for the second group, `corpus` for the first and `large` for the third.
The order is the order of the groups, so that the page list does not depend on a run."""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
STEP_1 = 'middleware/results/agreement/pages.json'
STEP_2 = 'middleware/results/tree-source-structure/pages.json'
LARGE = 'middleware/sample-suite/tests/large/pages.json'


def load(path):
    with open(os.path.join(ROOT, path)) as f: return json.load(f)


def pages():
    structure = load(STEP_2)
    counts = {p['url']: p['tabStops'] for p in structure['rejected']}
    out = [{'url': p['url'], 'address': p['url'], 'group': 'step 1', 'class': 'corpus'} for p in load(STEP_1)['sample']]
    out += [{'url': p['url'], 'address': p['url'], 'group': 'step 2', 'class': p['class'], 'tabStops': p['tabStops']} for p in structure['sample']]
    out += [{'url': p['address'], 'address': p['address'], 'group': 'large', 'class': 'large', 'tabStops': counts[p['address']]} for p in load(LARGE)]
    if len({p['url'] for p in out}) != len(out): raise ValueError('a page is in two groups')
    return out


def main(argv):
    if len(argv) != 1: sys.exit(__doc__)
    sample = pages()
    with open(argv[0], 'w') as f: json.dump({'rule': 'middleware/results/devtools-source/rule.md', 'sample': sample}, f, indent=1); f.write('\n')
    print(f'{len(sample)} pages written')


if __name__ == '__main__': main(sys.argv[1:])
