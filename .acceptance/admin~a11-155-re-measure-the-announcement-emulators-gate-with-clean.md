A11-155. The Gate re-measured on a clean-history oracle, run on the fleet (12 boxes, 2026-10-21): the held-out figure at the freeze (`5fbd726`) is **4,426 of 4,480 = 98.79%**, `history` misses 0 (were 61), and the Gate is **still not passed on the spike's reading** (13 misses unexplained, 11 on one live page that changed). The write-up is the `## Re-measure` section of `docs/announcement-emulator-spike.md`; the evidence is in `q3/results/remeasure/`.

Acceptance:

```bash
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure
python3 q3/remeasure/check.py        # exit 0: readback ok, summary ok (102 stamped entries), figures ok (2 match their text), addresses ok, doc ok; `oracle` reads pending because the oracle's pages are third-party's and are not committed
grep -E '^GATE' q3/results/remeasure/measure-held-freeze.txt q3/results/remeasure/measure-held-head.txt     # 4426 of 4480 = 98.79% ; 4389 of 4407 = 99.59%
git diff origin/main --numstat -- docs/announcement-emulator-spike.md                                       # additions only: N 0
```

To re-run the live part (fleet and oracle) see `q3/remeasure/RUNBOOK.md`; with the oracle, `python3 q3/remeasure/check.py --oracle <dir> --require-complete` exits 0.

## What changed

- `q3/remeasure/visited-probe.html` (and `visited-probe-other.html`): a control page of ours with two links on `capture-host`, one to itself and one to a page that is never opened. Captured twice, the first capture puts the page in a history-keeping browser's store and the second reads it as `visited`. Chromium keys `visited` by the top-level site, so a link to another site could not serve as the control.
- `q3/remeasure/readback.py`: stores a box's read-back in `q3/results/remeasure/history-readback.json`. A box may be captured from only if, in this order, its `before` probe read `visited` (its own positive control), the policy value read back is 1, its store was emptied, and its `after` probe read both links without `visited`; and it has not been `restored`. It counts as having held only with a clean `after-run` probe too. A probe record counts only if it is of the probe page.
- `q3/corpus_capture.py`: captures the same addresses on workers (`name=url`), refuses a worker with no passing read-back and a run with fewer than three, retries a failed page, survives a worker command that crashes, re-captures a record that is unstamped or from a worker that no longer passes, exits non-zero unless every page was captured, and stamps every record with a `history` block. Uses `fleet_capture.mjs` unchanged.
- `q3/remeasure/policy_override.py`: writes the `-e @file` for `provision-role.yml --tags policy` from the control checkout's own `worker_edge_policy` plus `SavingBrowserHistoryDisabled=1` (an extra var replaces the whole list). Run against `control` at its head it gives the eight declared entries plus the new one.
- `q3/remeasure/check.py`: the checks of the plan's proof table that need no commit: read-back, oracle (exactly the corpus addresses, each a good stamped capture from a box that held, `visited` count 0 over swept and spoken announcements), each Gate figure equal to its text, no IPv4 literal under the results or in the doc, and the doc diff being one `## Re-measure` section between `## Gate` and the next section. Without the fleet they read `pending`; `--require-complete` makes `pending` fail.
- `q3/remeasure/RUNBOOK.md`: every fleet and measure step, in order, with its pass criterion.
- `q3/remeasure/test_remeasure.py`: 57 tests.

## What the run found (details in the write-up)

- Policy `SavingBrowserHistoryDisabled=1` set and read back on 12 boxes through `provision-role.yml --tags policy`; the probe saw history before on 10 of 12 boxes and none after, on all 12, at the end of the run too. Restored through the same play (value 0) and read back on all 12.
- 102 of 102 captured, 0 failed, all stamped; 7 `visited` announcements on 4 pages remain, all announced identically by the emulator with no history (the browser's own mark on a link to the page it is on), so they are not history.
- Two plan assumptions were wrong and are recorded in the write-up and the PR: the worker keeps Edge alive across captures, and `fetch` gave up on slow captures after 300 s (`fleet_capture.mjs` now uses `node:http`).

## Unchecked

- The 300 s `fetch` limit is shown by the first capture attempt's log (`UND_ERR_HEADERS_TIMEOUT`, then `429 a capture is already in progress` on the retries), not by a unit test: a test would need a 300 s answer. The tests cover that `fleet_capture.mjs` writes the record of a late answer, of a 429 and the `capture-host` renaming.
- The `policy`, `emptied` and `restored` readings are typed by the operator from the Ansible output; the tooling does not parse them. Whether `win_file` with `%LOCALAPPDATA%` expands for the `witness` account, and whether Edge 155 honours `SavingBrowserHistoryDisabled` for the probe, are shown only by running the runbook: the `before` and `after` probes are what show it.
- Which of `corpus_capture.py`'s worker names point at which URL is the operator's; the runbook derives both from the inventory name.

## Mutation (measured; each restored, the tests green again)

| Mutation | Tests that fail |
| --- | --- |
| `before` stage reads like `after` | 3 |
| the probe page's address is not required of a probe record | 1 |
| readings out of order accepted | 1 |
| a restored box still passes | 1 |
| `after-run` optional for "held" | 2 |
| fewer than three passing boxes accepted | 1 |
| oracle not compared with the corpus | 1 |
| a bare-list misses file read as a Gate figure | 1 |
| an insertion inside the Gate section accepted | 1 |
| a worker with no passing read-back is not refused | 2 |
| a record of an unclean earlier run kept | 1 |
| a stale `.part` file taken for a capture | 1 |
| an unreadable record kills the worker thread | 1 |
| the `visited` count not added up / records not stamped / override without the history policy | 1 each |
| every `visited` counted as explained, whatever the emulator says | 2 |
| an unexplained `visited` accepted by the check | 1 |
| a stale explanation (another count) accepted | 1 |
| the committed summary not compared with the corpus | 1 |
| a restored box not counted as cleared | 3 |
| a `visited` spoken in the read-through but in no swept channel ignored | 1 |
| `fleet_capture.mjs` does not turn a refused or cut-off connection into a record | 2 |
