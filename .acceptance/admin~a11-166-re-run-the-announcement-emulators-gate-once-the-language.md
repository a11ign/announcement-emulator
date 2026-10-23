A11-166. The announcement emulator's Gate measured once more, cleanly: on 120 addresses nobody had read (A11-170's batch 2, 68 of them held), with the emulator frozen at `1ce9efd` (A11-164's table in it) and committed before any of them was captured, every page recorded with consent already given and served to both sides, the same bytes to the fleet and the emulator. **The held-out figure is 3,497 of 3,507 = 99.71%; each of its ten misses is traced to an emulator bug (named, not fixed); the Gate is passed** by the spike's rule. The earlier 60 held pages are reported at the new freeze, labelled "not held out" (4,828 of 4,856 = 99.42%). The fleet (twelve boxes) is restored and read back. The write-up is the last `### ` subsection of `## Re-measure` in `docs/announcement-emulator-spike.md`; the evidence is in `q3/results/gate/`; the procedure is `q3/gate/RUNBOOK.md`.

Acceptance (reads the page and the committed results; needs no network, no fleet, no browser; the oracle's pages are third-party's and are not committed, so `oracle` and `replay-stamps` read `pending` here and `--require-complete` is the run on `capture-host` with `--oracle`):

```bash
set -eu
python3 -W error::ResourceWarning -m unittest discover -s q3/gate -t q3/gate          # the snapshot, the run list, the consent report, the comparable account, the probes, the attribution
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure   # the earlier checks, and the freeze, consent, comparable, explained, verdict and label checks
python3 -W error::ResourceWarning -m unittest discover -s q3/replay -t q3/replay         # the consent rule and its serving; tests that need the proxy or Chrome are skipped where setup.sh has not built them
# a new freeze, before the held-out half was read: every capture is later, and the emulator and harness are the freeze's
python3 q3/remeasure/check.py --replay --gate --results q3/results/gate --corpus q3/results/gate/corpus-run.json --control-from q3/results/remeasure/history-readback.json | tee /tmp/a11-166-check.txt
! grep -E '^ +FAIL' /tmp/a11-166-check.txt
grep -E '^ +ok  (freeze|consent|comparable|explained|verdict|labels|served|manifest|replay-readback|doc|figures):' /tmp/a11-166-check.txt | wc -l      # 11
# the figure on the page is the figure in the run, and the verdict is the one the figure and the classes give
grep -q '^GATE: 3497 of 3507 = 99.71%' q3/results/gate/measure-held-freeze.txt
grep -q '3,497 of 3,507 = 99.71%' docs/announcement-emulator-spike.md
grep -c '\*\*The Gate is passed\*\*' docs/announcement-emulator-spike.md      # 1 in the new subsection (the Gate section's own sentence is "not passed", unchanged)
# the new pages are not the old ones, and the split is the rule's
python3 - <<'PY'
import json, sys
sys.path.insert(0, 'q3')
from split import split_of
b = json.load(open('q3/results/gate/corpus-batch2.json')); c = {e['url'] for e in json.load(open('q3/results/corpus.json'))}
assert len(b['pages']) == 120 and not ({p['url'] for p in b['pages']} & c) and all(p['split'] == split_of(p['url']) for p in b['pages'])
print('batch 2:', b['source']['commit'][:12], sum(p['split'] == 'held' for p in b['pages']), 'held')
PY
# nothing earlier on the page changed: only additions
git diff origin/main --numstat -- docs/announcement-emulator-spike.md | awk '{ if ($2 != 0) exit 1 }'
# the fleet is restored and read back
python3 - <<'PY'
import json
r = json.load(open('q3/results/gate/replay-readback.json'))['workers']
assert len(r) == 12 and all(b['restoredOk'] and b['status']['state'] == 'ready' and not b['off']['read'] for b in r.values())
h = json.load(open('q3/results/gate/history-readback.json'))['workers']
assert all(b['restored']['evidence'].endswith('value 0') for b in h.values())
print('12 of 12 boxes restored and read back')
PY
```
