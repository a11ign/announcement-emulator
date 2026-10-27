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

## Under the plan of 2026-10-26 (DevTools as the only tree source): step 1 of 4, the fields DevTools lacks, with the extension still there as the reference

The earlier "step 1 of 3" and "step 2 of 3" above are the merged measurements (#13, #16). The plan was rewritten after the chairman's work list (DevTools first: `clickable`, a field's typed value, the description words, the `row N` / `column N`
header words, and the cost), as four steps. This is the first: the DevTools conversion (`middleware/runtime/axtree.py`) is held to the companion extension's tree for the same pages, recorded here before the extension is removed
(`middleware/runtime/fixtures/structure/`, three small pages of `middleware/sample-suite/pages/fields/` walked by the new `fields` project), and the fields it lacked are filled from the protocol and Chromium's own rules. It also carries over
the two parts of the closed #14 that do not depend on the extension: `check-report.mjs` refuses an option it does not know, and the `contexts` project (a suite that opens its own `browser.newContext()`).

Acceptance (needs no network, no fleet and no browser; the recordings are in the repository):

```bash
set -eu
# the conversion equals the extension's tree, field by field, on the three recorded pages: table cells (index, span, aria index, header cells), positions in a set, the click verb, values, descriptions, links
(cd middleware/runtime && python3 -m unittest test_axtree test_cdp)
# the pages and the tests that walk them are there, and the recordings were made of them
test -f middleware/sample-suite/pages/fields/tables.html && test -f middleware/sample-suite/pages/fields/lists.html && test -f middleware/sample-suite/pages/fields/clickable.html
grep -q 'name: "fields"' middleware/sample-suite/base.config.ts && grep -q 'name: "contexts"' middleware/sample-suite/base.config.ts
for page in tables lists clickable; do test -s middleware/runtime/fixtures/structure/$page.jsonl.gz && test -s middleware/runtime/fixtures/structure/devtools-$page.json.gz; done
# every other recorded replay still says the same (the DevTools sequences and the extension's)
(cd middleware/runtime && python3 -m unittest test_replay test_pure test_fallback test_flags)
# check-report refuses an option it does not know (exit 2) and holds the contexts test to the speech of both its pages
(cd middleware && pnpm exec rstest run src/check-report.test.ts)
# nothing the two earlier freezes name has moved at the commit each was named at (they name whole directories the runtime lives in, which this ticket changes by design)
python3 middleware/agreement/make_freeze.py check middleware/results/tree-source/freeze.json --head bcec5908e7
python3 middleware/agreement/make_freeze.py check middleware/results/tree-source-structure/freeze.json --head 1cf8cd09f7
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
```

This is step 1 of 4; the ticket stays open for steps 2 (read the tree incrementally), 3 (remove the extension) and 4 (re-measure under a fresh freeze).

## Under the plan of 2026-10-26: step 2 of 4, the tree is read again at the cost of what changed

The profile of the `structure` run found that reading the tree was a few percent of its time and that 95% of `speechMs` was one quadratic search in the emulator (`emu/standin.py`, the reverse relations of the tree, found for every node
by looking in every node); that is fixed with the same speech. The runtime (`middleware/runtime/incremental.py`) keeps what the last full read of a page gave and reads again only the AX nodes that can have changed, when a probe the page
answers says that nothing but the focus, a control's value or an element's title, class or style did; `Converter.patch` brings the node list up to date. `verify` (the reporter's option, now also the runtime's `--verify`) reads the page from
scratch after each incremental read and records where the two differ. The five pages of 705 to 1,770 tab stops that produced no prediction have a project (`large`) and a prediction. The tables are in `middleware/results/devtools-source/cost/`.

Acceptance (needs no network, no fleet and no browser; the recordings and the profiles are in the repository):

```bash
set -eu
# the incremental reader: what it reads again, when it reads whole, that its tree is the one a read from scratch gives, the patch of the node list, the reads recorded in Chromium and played again
(cd middleware/runtime && python3 -m unittest test_incremental test_axtree test_cdp test_relations)
# the events the page reports are the extension's, and the speech made of them (needs the emulator's virtualenv: skipped without it)
(cd middleware/runtime && python3 -m unittest test_replay)
# every other test of the runtime and of the measurement, the walks the sample suite's projects share, and the cost summary
(cd middleware/runtime && python3 -m unittest discover -p 'test_*.py')
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
# the reporter's verify option reaches the runtime
(cd middleware && pnpm exec rstest run src/runtime.test.ts)
# the recordings, the projects and the cost tables are there, and the tables in the README are the ones the committed summary makes
for f in form basket devtools-basket-live devtools-error-alert devtools-spa-route; do test -s middleware/runtime/fixtures/incremental/$f.jsonl.gz; done
grep -q 'name: "large"' middleware/sample-suite/base.config.ts && grep -q 'name: "paced"' middleware/sample-suite/base.config.ts
python3 - <<'PY'
import json, re, subprocess
C = 'middleware/results/devtools-source/cost'
readme = open(f'{C}/README.md').read()
for labels in (['structure-before', 'structure-after'], ['paced-before', 'paced-after']):
    table = subprocess.run(['python3', 'middleware/agreement/summarize_cost.py', '--table', f'{C}/summary.json', *labels], capture_output=True, text=True, check=True).stdout.strip()
    assert table in readme, labels
PY
# nothing the two earlier freezes name has moved at the commit each was named at (they name whole directories the runtime lives in, which this ticket changes by design)
python3 middleware/agreement/make_freeze.py check middleware/results/tree-source/freeze.json --head bcec5908e7
python3 middleware/agreement/make_freeze.py check middleware/results/tree-source-structure/freeze.json --head 1cf8cd09f7
```

This is step 2 of 4; the ticket stays open for steps 3 (remove the extension) and 4 (re-measure under a fresh freeze).
