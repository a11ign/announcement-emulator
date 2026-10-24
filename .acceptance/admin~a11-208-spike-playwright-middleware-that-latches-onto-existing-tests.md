Row A11-208, the spike: a Playwright middleware that latches onto existing tests and reports predicted NVDA speech. The deliverable is `docs/playwright-middleware-spike.md` (Q1 to Q7 with figures, the agreement table, a go/no-go), the package and runtime in `middleware/`, and the report of the sample suite run on a plain `ubuntu-latest` runner after `npx announcement-emulator install`, committed in `middleware/results/ci/linux-x64/`. Nothing is published to npm or any registry.

Acceptance (the checks that need no network, no fleet and no browser; the package's own tests need `pnpm install` once):

```bash
set -eu
d=docs/playwright-middleware-spike.md
# the write-up answers Q1 to Q7, has the recommendation, the decisions made without a person, and the agreement table
for h in '## Q1\.' '## Q2\.' '## Q3\.' '## Q4\.' '## Q5\.' '## Q6\.' '## Q7\.' '## What a real version needs, and the recommendation' '## Decisions made without a person'; do grep -q "^$h" "$d"; done
grep -q 'By channel' "$d"
grep -Eq '\*\*Q5: 83\.1%\*\* \(207 of 249 units\)' "$d"
# the agreement figures on the page are the figures in the committed measure
grep -Eq '^ *all +[0-9]+ / [0-9]+ +83\.1%|83\.1%' middleware/results/agreement/figure-4/agreement.txt
# the sample suite carries no screen-reader code
! git grep -nEi 'announcement-emulator|screen.?reader|nvda' -- middleware/sample-suite/tests | grep -v 'corpus.spec.ts' | grep -q .
# the one line is the only difference between the sample suite's config and the plain one
grep -q 'withAnnouncements' middleware/sample-suite/playwright.config.ts
! grep -q 'withAnnouncements' middleware/sample-suite/playwright.plain.config.ts
# the committed report of the run on plain ubuntu CI: every test has the two attachments, they say "predicted NVDA speech", and the flags are on the tests whose pages have what they look for
( cd middleware/sample-suite && node check-report.mjs ../results/ci/linux-x64/announcement-emulator-run/report.json | grep -Eq '^13 tests, [0-9]+ predicted utterances, [0-9]+ sweeps, 4 flags$' )
grep -q 'matches the pin' middleware/results/ci/linux-x64/install.log
grep -q 'predicted NVDA speech attached to 13 tests, 4 flags' middleware/results/ci/linux-x64/run-with.log
grep -q 'predicted NVDA speech attached to 13 tests, 4 flags' middleware/results/ci/linux-x64/run-zero.log
# the freeze of the agreement measure still names the objects it named before the first capture
python3 middleware/agreement/make_freeze.py check middleware/results/agreement/freeze.json --head ca8145ad47 >/dev/null
# the extension's tree code is shared and the active dump still loads it
grep -q "importScripts('tree.js')" emu/ext2/bg.js
grep -q "importScripts('tree.js')" emu/ext2/passive.js
# nothing is published
grep -q '"private": true' middleware/package.json
# the package: lint, types, tests
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
# the Python tests that need no NVDA checkout
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_flags.py'
python3 -m unittest discover -s middleware/bundle -t middleware/bundle
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
python3 -m unittest discover -s q3 -t q3 -p test_fleet_capture.py
```

The replayed-session tests (`middleware/runtime/test_pure.py`, `test_replay.py`) need NVDA's source: `EMU_DOWNLOADS=<setup.sh's directory> python3 -m unittest discover -s middleware/runtime -t middleware/runtime`.

Closes A11-208
