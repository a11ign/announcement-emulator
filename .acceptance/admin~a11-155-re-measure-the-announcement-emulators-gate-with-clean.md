A11-155 (partial). The tooling, the checks and the runbook for re-measuring the Gate on a clean-history oracle. **The measurement itself has not been run**: this host has no fleet inventory (`/etc/a11ign/inventory.yml` is absent), so the fleet steps go to the chairman session as exact commands in `q3/remeasure/RUNBOOK.md`, each with what a pass looks like. No figure, no "Re-measure" section and no Gate verdict are claimed here.

Acceptance:

```bash
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure
python3 q3/remeasure/check.py                      # exit 0; the fleet-dependent lines read `pending`, the address line reads `ok`
python3 q3/remeasure/policy_override.py ../control/ansible/roles/worker/defaults/main.yml | tail -2    # needs a control checkout beside this one; ends with SavingBrowserHistoryDisabled / value: 1
```

## What changed

- `q3/remeasure/visited-probe.html`: a control page of ours with two links, one to itself and one to an address the spike's fleet announced `visited`. It is the read-back of a box's history, by capture.
- `q3/remeasure/readback.py`: stores a box's read-back in `q3/results/remeasure/history-readback.json` (the policy value the play asserted, that the store was emptied, and the probe at `before`, `after` and `after-run`). A box passes only if the policy value is 1, the store was emptied, and its `after` probe read both links without `visited`. `before` is the positive control: it must read `visited`.
- `q3/corpus_capture.py`: captures the same addresses on workers (`name=url`), refuses a worker with no passing read-back and a run with fewer than three, retries a failed page, resumes, and stamps every record with a `history` block. Uses `fleet_capture.mjs` unchanged.
- `q3/remeasure/policy_override.py`: writes the `-e @file` for `provision-role.yml --tags policy` from the control checkout's own `worker_edge_policy` plus `SavingBrowserHistoryDisabled=1` (an extra var replaces the whole list, so the list is restated mechanically, not by hand).
- `q3/remeasure/check.py`: the checks of the plan's proof table that need no commit: read-back, oracle stamped and `visited` count 0, each figure equal to its text, no IPv4 literal under the results or in the doc, and the doc diff being one `## Re-measure` section after `## Gate`. Without the fleet they read `pending`; `--require-complete` makes `pending` fail.
- `q3/remeasure/RUNBOOK.md`: every fleet and measure step, in order, with its pass criterion.
- `q3/remeasure/test_remeasure.py`: 27 tests.

## Not done here, and why

The policy on the boxes, the emptying, the probes, the capture of the 102 addresses, the freezes, the held-out figures, their attribution, the restore of the fleet and the write-up all need the fleet. Each is a step of `RUNBOOK.md`. The ticket's Done-when (the Gate passed, or not, on a clean-history corpus, with evidence) is therefore **not yet met**.

## Mutation (measured; each restored, the 27 tests green again)

| Mutation | Tests that fail |
| --- | --- |
| `before` stage reads like `after` (the control passes when it sees nothing) | 3 |
| a worker with no passing read-back is not refused | 2 |
| the `visited` count is not added up | 1 |
| an oracle record from a worker that did not pass is accepted | 1 |
| the override does not add the history policy | 1 |
| the doc check allows existing lines to change | 1 |
| records are not stamped with the `history` block | 1 |
