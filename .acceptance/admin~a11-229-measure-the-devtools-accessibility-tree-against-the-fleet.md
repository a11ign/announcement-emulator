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

---

Row A11-229, step 2 of 3: the middleware picks the tree source automatically, with one option to force either. `withAnnouncements(config, { tree: "auto" | "extension" | "devtools" })` (default `auto`; `ANNOUNCEMENT_EMULATOR_TREE` is its environment form and the option wins). Under `auto`: the extension on Linux and Windows, the DevTools port on macOS, and a run-time switch to the DevTools port when the extension posts no tree (a `ready` alone no longer counts). Every report says which source it used and why, and the rate that source measured at in A11-229 step 1 (the words "lower fidelity" are gone). A sample-suite test pins that a context the suite opens itself (`browser.newContext()`) is served by the extension; no rule keys on it.

Acceptance (no network, no fleet, no browser; `pnpm install` once):

```bash
set -eu
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
# the Python rules: the extension that is ready and posts no tree is taken over after the wait
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_fallback.py'
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_pure.py'
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_cdp.py'
# the figures a report quotes are the ones committed in step 1
grep -q '"leadPoints": 0.70298769771529' middleware/results/tree-source/comparison.json
# nothing says the DevTools tree is of lower fidelity any more
test -z "$(grep -rn 'lower fidelity\|lower-fidelity' middleware/src middleware/sample-suite middleware/README.md .github/workflows/middleware-spike.yml)"
```

With the bundle installed and Playwright's Chromium (CI does this in the `demo` job of `.github/workflows/middleware-spike.yml`; `$P` is a project made as that job makes one):

```bash
cd "$P"
WORKERS=1 npx playwright test --project=contexts && node check-report.mjs --expect-unmeasured <build>             # linux: the extension serves both contexts
ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT=2 npx playwright test --config playwright.fallback.config.ts && node check-report.mjs --expect-fallback --expect-unmeasured <build>
```
