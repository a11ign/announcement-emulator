A11-176. The three emulator bugs the Gate (A11-166) named, and the `Alt plus, m` access key, fixed in `emu/` at the Chromium or NVDA source each was found against: an anchor with no `href` is a link (`standin.py`, `ax_platform_node_win.cc:8242-8245`); the page is scrolled where NVDA's caret leaves it (`live.py` keeps the last IA2 `scrollTo`, `sweep.py` delivers it once after the read-through); the caret follows its field when the buffer is rebuilt (`storage.cpp:677-686` and `:742-760`, with a stable node id from `ext2/bg.js`); `accKeyboardShortcut` and the buffer's `keyboardShortcut` answer `Alt+<accesskey>`. Re-scored on a fresh fleet reading of the nine pages the ten misses were on, **not held out**: 16 of the 18 rows (the ten and the eight access-key rows) are agreed at head; the two others are the National Archives page, which neither reading can score (the write-up says why).

Acceptance (reads the committed results and runs the tests; needs no network and no fleet. The tests that run the emulator over a page need `setup.sh`'s virtualenv and Chrome in `$EMU_DOWNLOADS` and are skipped without them; the fleet's oracle is third-party's and is not committed, so `oracle`, `replay-stamps` and `explained` read `pending`):

```bash
set -eu
python3 -m unittest discover -s emu/gatefixes -t emu/gatefixes                              # 27 tests, from the Gate's evidence; 23 fail on origin/main
python3 -W error::ResourceWarning -m unittest discover -s q3/gate -t q3/gate                # includes fixed_at_head.py and page_readings.py
python3 -W error::ResourceWarning -m unittest discover -s emu/langnames -t emu/langnames
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure
python3 -W error::ResourceWarning -m unittest discover -s q3/replay -t q3/replay
# the re-score: 17 of 18 rows reproduced at the freeze re-run, 16 fixed at head (it exits 1: two rows are the National Archives page)
python3 q3/gate/fixed_at_head.py q3/results/gate/misses-attributed.json q3/results/gate/misses-held-freeze.json \
  q3/results/gate-fixes/misses-nine-freeze-not-held-out.json q3/results/gate-fixes/misses-nine-head-not-held-out.json /tmp/a11-176-fixed.json || test $? -eq 1
python3 - <<'PY'
import json, collections
rows = json.load(open('/tmp/a11-176-fixed.json'))
assert json.load(open('q3/results/gate-fixes/fixed-at-head-not-held-out.json')) == rows
assert collections.Counter(r['head']['status'] for r in rows) == {'fixed': 16, 'page not comparable': 2}
assert collections.Counter(r['freeze']['status'] for r in rows) == {'reproduced': 17, 'not reproduced': 1}
assert all('caselaw' in r['url'] for r in rows if r['head']['status'] != 'fixed')
print('16 of 18 rows fixed at head; the 2 others are the National Archives page')
PY
# the National Archives page, every reading there is: the bar is in none of six freeze runs and in all six head runs
python3 - <<'PY'
import json
r = json.load(open('q3/results/gate-fixes/caselaw-readings-not-held-out.json'))
assert all(sum(v['has'].values()) == 0 for v in r['emulator']['freeze'].values()) and all(sum(v['has'].values()) == 3 for v in r['emulator']['head'].values())
assert len(r['emulator']['freeze']) == len(r['emulator']['head']) == 6
print('caselaw: 0 of 6 freeze runs, 6 of 6 head runs')
PY
# the fleet's part: three boxes cleared, behind the replay server, restored, and the nine pages served the manifest's archives
python3 q3/remeasure/check.py --replay --results q3/results/gate-fixes --corpus q3/results/gate-fixes/corpus.json --control-from q3/results/remeasure/history-readback.json \
  --doc docs/announcement-emulator-spike.md --base origin/main | tee /tmp/a11-176-check.txt
! grep -E '^ +FAIL' /tmp/a11-176-check.txt
grep -E '^ +ok  (readback|summary|figures|addresses|doc|replay-readback|manifest|served):' /tmp/a11-176-check.txt | wc -l      # 8
# nothing earlier on the page changed, and nothing under q3/results/gate/ or any other committed figure
git diff origin/main --numstat -- docs/announcement-emulator-spike.md | awk '{ if ($2 != 0) exit 1 }'
test -z "$(git diff origin/main --name-only -- q3/results | grep -v '^q3/results/gate-fixes/')"
# the Chromium file the access key is cited from is fetched by setup.sh
grep -q 'third_party/blink/renderer/modules/accessibility/ax_object.cc' setup.sh
```

The Q2 suite (`cd emu && $EMU_DOWNLOADS/q2/venv/bin/python run_cases.py`, about 12 minutes) is 215 of 227 at head with the same per-test table as `emu/results-final.txt`.
