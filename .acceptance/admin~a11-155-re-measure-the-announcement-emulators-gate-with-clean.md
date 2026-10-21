A11-155 (partial). The tooling, the checks and the runbook for re-measuring the Gate on a clean-history oracle. **The measurement itself has not been run**: this host has no fleet inventory (`/etc/a11ign/inventory.yml` is absent), so the fleet steps go to the chairman session as exact commands in `q3/remeasure/RUNBOOK.md`, each with what a pass looks like. No figure, no "Re-measure" section and no Gate verdict are claimed here.

Acceptance:

```bash
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure
python3 q3/remeasure/check.py                      # exit 0; the fleet-dependent lines read `pending`, the address line reads `ok`
python3 q3/remeasure/policy_override.py ../control/ansible/roles/worker/defaults/main.yml | tail -2    # needs a control checkout beside this one; ends with SavingBrowserHistoryDisabled / value: 1
```

## What changed

- `q3/remeasure/visited-probe.html` (and `visited-probe-other.html`): a control page of ours with two links on `capture-host`, one to itself and one to a page that is never opened. Captured twice, the first capture puts the page in a history-keeping browser's store and the second reads it as `visited`. Chromium keys `visited` by the top-level site, so a link to another site could not serve as the control.
- `q3/remeasure/readback.py`: stores a box's read-back in `q3/results/remeasure/history-readback.json`. A box may be captured from only if, in this order, its `before` probe read `visited` (its own positive control), the policy value read back is 1, its store was emptied, and its `after` probe read both links without `visited`; and it has not been `restored`. It counts as having held only with a clean `after-run` probe too. A probe record counts only if it is of the probe page.
- `q3/corpus_capture.py`: captures the same addresses on workers (`name=url`), refuses a worker with no passing read-back and a run with fewer than three, retries a failed page, survives a worker command that crashes, re-captures a record that is unstamped or from a worker that no longer passes, exits non-zero unless every page was captured, and stamps every record with a `history` block. Uses `fleet_capture.mjs` unchanged.
- `q3/remeasure/policy_override.py`: writes the `-e @file` for `provision-role.yml --tags policy` from the control checkout's own `worker_edge_policy` plus `SavingBrowserHistoryDisabled=1` (an extra var replaces the whole list). Run against `control` at its head it gives the eight declared entries plus the new one.
- `q3/remeasure/check.py`: the checks of the plan's proof table that need no commit: read-back, oracle (exactly the corpus addresses, each a good stamped capture from a box that held, `visited` count 0 over swept and spoken announcements), each Gate figure equal to its text, no IPv4 literal under the results or in the doc, and the doc diff being one `## Re-measure` section between `## Gate` and the next section. Without the fleet they read `pending`; `--require-complete` makes `pending` fail.
- `q3/remeasure/RUNBOOK.md`: every fleet and measure step, in order, with its pass criterion.
- `q3/remeasure/test_remeasure.py`: 38 tests.

## Not done here, and why

The policy on the boxes, the emptying, the probes, the capture of the 102 addresses, the freezes, the held-out figures, their attribution, the restore of the fleet and the write-up all need the fleet. Each is a step of `RUNBOOK.md`. The ticket's Done-when (the Gate passed, or not, on a clean-history corpus, with evidence) is therefore **not yet met**.

## Unchecked

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
