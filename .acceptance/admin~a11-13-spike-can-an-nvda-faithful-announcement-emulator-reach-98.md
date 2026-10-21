Row A11-13 (a11ign#5661), the announcement-emulator spike. The deliverable is `docs/announcement-emulator-spike.md`: Q1, Q2, Q3 and the Gate each under their own heading, the runs pasted, the Gate's figure with its denominator, and the dates. The code that produced it (`emu/`, `q3/`) and the derived data (`q3/results/`) are in this repository, which is not an a11ign repository in the ticket's sense; no a11ign repository is touched and no evidence record is written.

Acceptance (reads the page and the derived data; needs no network, no fleet, no browser):

```bash
set -eu
d=docs/announcement-emulator-spike.md
# the four headings, each its own, and the dates
for h in '## Dates' '## Q1\.' '## Q2\.' '## Q3\.' '## Gate'; do grep -q "^$h" "$d"; done
# the Gate section states a figure with its denominator and says whether it is at or above 98%
awk '/^## Gate/{f=1;next} /^## /{f=0} f' "$d" > /tmp/gate-section.md
grep -Eq '[0-9],[0-9]{3} of [0-9],[0-9]{3} = [0-9]+\.[0-9]+%' /tmp/gate-section.md
grep -Eq 'Below 98%|below 98%' /tmp/gate-section.md
# the figure on the page is the figure in the committed run
grep -q '4,497 of 4,607 = 97.61%' "$d"
grep -q 'GATE: 4497 of 4607 = 97.61%' q3/results/measure-held-freeze.txt
grep -q 'GATE: 4341 of 4413 = 98.37%' q3/results/measure-held-post.txt
# every miss on the ten shapes at the freeze is classed, and the classes add up to the figure
python3 - <<'PY'
import json, collections
m = json.load(open('q3/results/misses-held-freeze-attributed.json'))
top = set(json.load(open('q3/results/misses-held-freeze.json'))['top'])
g = [r for r in m if ' + '.join(r['shape']) in top and r['channel'] != 'frames']
c = collections.Counter(r['class'] for r in g)
assert len(g) == 110, len(g)
assert 4607 - 4497 == len(g)
assert dict(c) == {'history': 61, 'bug-fixed': 34, 'language': 6, 'unexplained': 9}, dict(c)
# each misses file's gate count is the count in the run it came from
for n in ('control-freeze', 'dev-freeze', 'dev-post', 'held-freeze', 'held-post'):
    gate = json.load(open(f'q3/results/misses-{n}.json'))['gate']
    run = open(f'q3/results/measure-{n}.txt').read()
    assert isinstance(gate['exact'], int) and 'GATE: %d of %d ' % (gate['exact'], gate['total']) in run, n
PY
# the Dates table has end dates and the elapsed days
grep -Eq '^\| Q3 finished; Gate measured +\| 2026-10-21' "$d"
grep -Eq 'Days from the first commit to the Gate' "$d"
# Q2: the committed run is the page's figure
grep -q '^RESULT 215 / 227' emu/results-final.txt
grep -q '215 of 227' "$d"
# no network address of a worker or of the capture server is published: the records name `a11y-worker-N` and `capture-host`
! git grep -nE '192\.168\.[0-9]+\.[0-9]+' -- . ':!.acceptance' | grep -q .
# the code imports no a11ign package, so it cannot write an evidence record (the guard the ADR asks of the layer, in its simplest form)
! git grep -nE '@a11ign|from a11ign|import a11ign' -- emu q1 q2 q3 ':!q3/results' | grep -q .
```

**As run (2026-10-21):** every line exits 0 from the repository root.

Closes A11-13
