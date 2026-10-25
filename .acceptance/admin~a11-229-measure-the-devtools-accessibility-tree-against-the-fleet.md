Row A11-229, step 1 of 3: measure the extension's and the DevTools port's accessibility trees against the fleet, by the Q5 rule frozen before the first capture, and recommend by the numbers. It adds the rule
(`middleware/results/tree-source/rule.md`), `agreement/compare_sources.py` (the margin, the attribution of every miss and the tables), a `make_freeze.py` that names extra objects, a `measure.py` that refuses
runs that mix tree sources and reads the second capture against the second run, the workflow that takes the macOS and control readings, the committed figures and misses, and a section of the spike doc.
No runtime, extension or package code changes: the source choice itself is steps 2 and 3.

Acceptance (needs no network, no fleet and no browser; the fleet's records and the passive reports are third-party pages and are not committed):

```bash
set -eu
T=middleware/results/tree-source
# the rule was frozen before any capture: nothing the figure is made by has moved since the freeze commit, and every fleet reading is dated after the freeze
python3 middleware/agreement/make_freeze.py check $T/freeze.json --head bcec5908e7
python3 - <<'PY'
import json
freeze = json.load(open('middleware/results/tree-source/freeze.json'))
readings = json.load(open('middleware/results/tree-source/fleet-readings.json'))
assert len(readings) == 12 and all(r['status'] == 200 for r in readings)
assert all(r['capturedAt'] > freeze['namedAt'].replace('Z', '.000Z') for r in readings), 'a capture is older than the freeze'
PY
# a figure for each reading, and every miss has one cause from the rule's closed list; an unexplained miss has its reason
python3 - <<'PY'
import json, sys
sys.path.insert(0, 'middleware/agreement')
import compare_sources as cs
for reading in ('ext-linux', 'devtools-linux', 'devtools-macos', 'devtools-ubuntu-ci'):
    d = json.load(open(f'middleware/results/tree-source/figure-{reading}/misses.json'))
    assert d['misses'], reading
    for m in d['misses']:
        assert cs.is_cause(m['cause']), (reading, m['cause'])
        assert m['cause'] != 'unexplained' or m['reason'], (reading, m)
    open(f'middleware/results/tree-source/figure-{reading}/agreement.txt').read().index('agreement by shape')
PY
# the recommendation is the rule's: the lead against the 1.0-point margin, and the spike doc says the same
python3 - <<'PY'
import json
c = json.load(open('middleware/results/tree-source/comparison.json'))['extensionBuys']
assert c['margin'] == 1.0
assert c['recommendation'] == ('drop the extension' if c['leadPoints'] <= 1.0 else 'keep both')
doc = open('docs/playwright-middleware-spike.md').read()
assert '## The tree sources, measured against the fleet (A11-229)' in doc
assert 'DROP THE EXTENSION: its lead is +0.7 points (934 against 926 of 1,138 units)' in doc
assert (c['extension'], c['devtools'], c['units']) == (934, 926, 1138)
PY
grep -q 'recommendation by the frozen rule (the chairman reads it): DROP THE EXTENSION' $T/comparison.txt
# the tests of the measurement
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
```

This is step 1 of 3; the ticket stays open for steps 2 and 3.

## Step 2 of 3: the structure safeguard (table- and list-heavy pages), measured under a rule frozen before capture

The chairman's decision of 2026-10-25 replaced the plan's steps 2 and 3 (drop the extension, with one safeguard first). This step is the safeguard: eight table- and list-heavy real pages chosen by DOM counts only
(`middleware/results/tree-source-structure/`), both sources against the fleet on them, and the gate (the extension's lead at most 1.0 point overall and on each class of page). **The gate says STOP AND REPORT**
(table pages +1.8 points), so step 3 (remove the extension) is held for the chairman. No runtime, extension or package code changes in this step.

Acceptance (needs no network, no fleet and no browser; the fleet's records and the passive reports are third-party pages and are not committed):

```bash
set -eu
S=middleware/results/tree-source-structure
# the rule (second freeze) was frozen before any capture: nothing the figure is made by has moved since, and every fleet reading is dated after it
python3 middleware/agreement/make_freeze.py check $S/freeze.json --head 1cf8cd09f7
python3 - <<'PY'
import json
freeze = json.load(open('middleware/results/tree-source-structure/freeze.json'))
readings = json.load(open('middleware/results/tree-source-structure/fleet-readings.json'))
assert len(readings) == 16 and all(r['status'] == 200 for r in readings)
assert all(r['capturedAt'] > freeze['namedAt'].replace('Z', '.000Z') for r in readings), 'a capture is older than the freeze'
pages = json.load(open('middleware/results/tree-source-structure/pages.json'))['sample']
assert [p['class'] for p in pages].count('table') == 4 and [p['class'] for p in pages].count('list') == 4 and all(p['tabStops'] <= 500 for p in pages)
PY
# a figure for each source, every miss has one cause from the closed list, an unexplained one has its reason
python3 - <<'PY'
import json, sys
sys.path.insert(0, 'middleware/agreement')
import compare_sources as cs
for reading in ('ext-linux', 'devtools-linux'):
    d = json.load(open(f'middleware/results/tree-source-structure/figure-{reading}/misses.json'))
    assert d['misses'], reading
    for m in d['misses']:
        assert cs.is_cause(m['cause']), (reading, m['cause'])
        assert m['cause'] != 'unexplained' or m['reason'], (reading, m)
PY
# the gate is the rule's, and the spike doc says the same
python3 - <<'PY'
import json
c = json.load(open('middleware/results/tree-source-structure/comparison.json'))['extensionBuys']
g = c['gate']
assert g['margin'] == 1.0
by_class = {b['label']: b for b in c['byClass']}
assert g['proceed'] == (c['leadPoints'] <= 1.0 and all(b['leadPoints'] <= 1.0 for b in c['byClass']))
assert not g['proceed'] and [o['label'] for o in g['over']] == ['table pages']
assert (by_class['table']['extension'], by_class['table']['devtools'], by_class['table']['units']) == (323, 317, 342)
assert (c['extension'], c['devtools'], c['units']) == (1062, 1135, 1492)
doc = open('docs/playwright-middleware-spike.md').read()
assert '## The structure safeguard: table- and list-heavy pages (A11-229, step 2)' in doc
assert 'STOP AND REPORT: the extension leads by more than the 1.0-point margin on table pages (+1.8)' in doc
PY
grep -q 'gate by the frozen rule (the chairman reads it): STOP AND REPORT' $S/comparison.txt
# the tests of the measurement
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
```

This is step 2 of 3; the gate stopped, so step 3 waits for the chairman.
