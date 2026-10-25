# Re-measure the Gate on a clean-history oracle (A11-155)

This is how the re-measure was run, and how to run it again. Every fleet step is Ansible from the control plane, one box first and then one at a time, with a read-back after each; nothing is changed by hand on a box.
Workers are `a11y-worker-N` and the page server is `capture-host`: no step writes an address into a result.
**Every capture is a fleet job** (A11-246): `q3/fleet_capture.py`, `q3/corpus_capture.py` and `q3/control_capture.py` submit it to the job service on the control plane, which books the boxes, and print the job ID. A job outlives the shell that submitted it. A person gives `--wait <duration>` for one foreground `fleet job wait` that collects when the job is done;
an agent writes the job ID in its outcome (`waitingOn: fleetJob`), ends its turn and is woken when the job ends, then runs the same command with `collect` in place of the submit. Nothing here runs a capture in the shell, or waits in a loop.

```sh
EMU=$PWD                                  # this checkout (it is also capture-host, where the probe page is served)
R=$EMU/q3/results/remeasure; W=/tmp/remeasure; mkdir -p $R $W
PY=$EMU_DOWNLOADS/q2/venv/bin/python      # the emulator's Python (setup.sh builds it); the Q3 steps run under it
export A11Y_CONTROL_HOST=$(cat ~/.config/a11ign/control-host) A11Y_PVE_KEY=~/.ssh/agents-fleet_ed25519      # control's own commands (fleet:status) reach the plane with these
LABEL=<the ticket key>                    # every capture below is a fleet job, and a job is labelled with the ticket that asked for it (fleet capture submit --label)
plane() { ssh -i $A11Y_PVE_KEY -o StrictHostKeyChecking=no root@$A11Y_CONTROL_HOST "$@"; }                  # ansible runs ON the plane, which holds the fleet key; /root/control is its checkout
PROBE=http://<capture-host address>:8000/visited-probe.html
```

## 0. Before anything

Serve the probe page from `capture-host`, take the fleet's state, and choose the boxes:

```sh
mkdir $W/probe && cp q3/remeasure/visited-probe*.html $W/probe && (cd $W/probe && nohup python3 -m http.server 8000 --bind 0.0.0.0 &)
( cd ~/repos/control && pnpm run fleet:status ) > $W/status-before.raw         # then replace every address by its worker's name before it is kept
```

**Pass:** the boxes are `ready`, none `busy`. The run's boxes are the largest group that agrees on every version `fleet:status` prints (browser, Windows build) and has at least three.

## 1. One box at a time: probe, stop Edge, policy, empty, probe

For each box `B`, the first one alone first. Nothing runs on a box that is not idle (`/health` `busy: false`).

```sh
python3 q3/remeasure/policy_override.py <the plane's control>/ansible/roles/worker/defaults/main.yml > $W/override.yml      # the plane's own list plus SavingBrowserHistoryDisabled=1; copy to the plane
python3 q3/remeasure/policy_override.py <the same file> --restore > $W/restore.yml                                           # the same list with it at 0; step 6

# BEFORE: the first capture visits the probe page, a later one reads it back. Edge writes its history in batches, so allow up to three reads, thirty seconds apart.
python3 q3/fleet_capture.py capture $B $PROBE $W/$B.before0.json --label $LABEL --wait 30m      # one job on the box; its records are written when it is done
python3 q3/fleet_capture.py capture $B $PROBE $W/$B.before1.json --label $LABEL --wait 30m
python3 q3/remeasure/readback.py probe $R/history-readback.json $B before $W/$B.before1.json

# The worker keeps Edge alive between captures, and a running Edge holds its History file: stop it (ad hoc Ansible on the idle box), then the policy through the fleet's own play
plane "cd /root/control/ansible && ansible $B -m ansible.windows.win_shell -a 'Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep 3; (Get-Process msedge -ErrorAction SilentlyContinue | Measure-Object).Count'"      # 0
plane "cd /root/control/ansible && ANSIBLE_CONFIG=ansible.cfg ansible-playbook provision-role.yml --tags policy -l $B -e @/tmp/remeasure/override.yml" | tee $W/$B.policy.txt
plane "cd /root/control/ansible && ansible $B -b -m ansible.windows.win_reg_stat -a 'path=HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge name=SavingBrowserHistoryDisabled'"                     # "value": 1

# empty the history the box already has: as the worker's own account, no -b. JSON arguments, because a backslash-a in key=value form is read as a bell character.
for f in History History-journal 'Visited Links'; do
  plane "cd /root/control/ansible && ansible $B -m ansible.windows.win_file -a '{\"path\": \"%LOCALAPPDATA%\\\\a11y-witness\\\\edge-profile\\\\Default\\\\$f\", \"state\": \"absent\"}'"
done

python3 q3/remeasure/readback.py policy $R/history-readback.json $B 1 "provision-role.yml --tags policy asserted all policy values; win_reg_stat read value 1"
python3 q3/remeasure/readback.py emptied $R/history-readback.json $B "Default/History, History-journal removed by win_file"
python3 q3/fleet_capture.py capture $B $PROBE $W/$B.after0.json --label $LABEL --wait 30m     # the visit
python3 q3/fleet_capture.py capture $B $PROBE $W/$B.after1.json --label $LABEL --wait 30m     # the read
python3 q3/remeasure/readback.py probe $R/history-readback.json $B after $W/$B.after1.json
```

**Pass, per box:** the policy play's recap is `failed=0` and its `Refuse to call this provisioned if a policy value did not land` task is `ok`; `win_reg_stat` shows `"value": 1`; `win_file` reports `changed` for `History`; the `after` probe prints
`visited: False ... as expected` and `readback.py` ends with `<box> passes`. **A box that does not pass stays off the run**; name it in the write-up. `before` is the positive control **of the method**: it must read `visited` on at least one box
(`check.py` fails otherwise); on a box where three reads do not show it, the box goes on and the write-up says so. The two probe links are on `capture-host`: Chromium keys `visited` by the top-level site, so a link to another site could not read as visited from this page.

## 2. Capture the same 102 addresses

```sh
BOXES=$(echo $BOXES | tr ' ' ',')                                    # the boxes that passed step 1, by name
python3 q3/corpus_capture.py q3/results/corpus.json $W/oracle --boxes $BOXES --label $LABEL --readback $R/history-readback.json --summary $R/capture-run.json
# prints the job ID: the corpus is one job on the boxes named, which it books (it queues behind a job that holds one of them).
#   an agent: write the ID in the outcome (waitingOn: fleetJob), end the turn, and when woken run the next line;  a person: add `--wait 6h`, which makes one `fleet job wait` and collects
python3 q3/corpus_capture.py collect $W/oracle                         # writes the stamped records and the summary; exit 1 names the pages whose capture failed
```

**Pass:** `collect` exits 0, `capture-run.json` shows `captured: 102, failed: []`, and the boxes are the passing ones (a box without a passing read-back is refused by name, before anything is submitted). A capture takes minutes: the service holds the connection to the worker, so no limit of the caller's applies.
The service does not re-capture a failed page: if `collect` names failed pages, run the same `corpus_capture.py` command again, which submits only the pages that have no kept record, and `collect` that job. Then, per box, capture the probe once more and record it as `after-run` (a box without it is not counted as having held, and `check.py` refuses its records):

```sh
python3 q3/fleet_capture.py capture $B $PROBE $W/$B.afterrun.json --label $LABEL --wait 30m
python3 q3/remeasure/readback.py probe $R/history-readback.json $B after-run $W/$B.afterrun.json
```

## 3. The `visited` announcements: explained, or the run stops

```sh
python3 q3/remeasure/check.py --oracle $W/oracle
```

If the oracle carries `visited`, run the emulator (no history) on those pages and explain them:

```sh
$PY q3/run_all.py $W/oracle $W/emu-visited --split all --runs 2 --only <the page's address>            # for each page that carries it
$PY q3/remeasure/explain_visited.py $W/oracle $W/emu-visited $R/visited-explained.json
```

**Pass:** `explain_visited.py` exits 0 (every one is announced identically by the emulator with no history: the browser's own mark on a link to the page it is on) and `check.py --oracle` has no `FAIL`. An unexplained one is a history that was not clean:
record why in the write-up and measure nothing.

## 4. Freeze, then measure

`freeze.json` names both freezes and is committed **before** any fresh record is read:

```sh
git worktree add $W/emu-gate 5fbd726                  # the Gate figure: the last emulator commit fitted to the dev half only
( cd $W/emu-gate && $PY q3/run_all.py $W/oracle $W/emu-gate-out --split held --runs 2 --jobs 6 --port-base 9100 )      # no --history
$PY q3/run_all.py $W/oracle $W/emu-head-out --split held --runs 2 --jobs 6 --port-base 9300                              # at head (not held out)
$PY q3/measure.py $W/oracle $W/emu-gate-out --split held --final --json $R/misses-held-freeze.json > $R/measure-held-freeze.txt
$PY q3/measure.py $W/oracle $W/emu-head-out --split held --final --json $R/misses-held-head.json > $R/measure-held-head.txt
$PY q3/attribute.py $R/misses-held-freeze.json $R/misses-held-head.json $R/misses-held-freeze-attributed.json
```

`measure.py` is run from head for both (its rules are the corrected ones); only the emulator differs. No emulator fix is made. The oracle (third-party pages) is not committed; the figures, the misses and the stamps are.

## 5. Put the fleet back, one box at a time, through the same route

The policy play only sets values, so putting history back is setting `SavingBrowserHistoryDisabled` to 0, the browser's default (the value stays in the registry, as 0):

```sh
plane "cd /root/control/ansible && ANSIBLE_CONFIG=ansible.cfg ansible-playbook provision-role.yml --tags policy -l $B -e @/tmp/remeasure/restore.yml"
plane "cd /root/control/ansible && ansible $B -b -m ansible.windows.win_reg_stat -a 'path=HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge name=SavingBrowserHistoryDisabled'"      # "value": 0
python3 q3/remeasure/readback.py restored $R/history-readback.json $B "restore play failed=0; win_reg_stat read value 0"
( cd ~/repos/control && pnpm run fleet:status )
```

**Pass:** `"value": 0` on every box that was changed; `fleet:status` shows them `ready`. A restored box no longer passes `box_passes` (it cannot be captured from) but still counts as having held for the run's records.

## 6. Write it up and check

Append one `## Re-measure` section to `docs/announcement-emulator-spike.md`, between `## Gate` and `## What this page does not settle`, and change nothing else on the page. Then:

```sh
python3 q3/remeasure/check.py --oracle $W/oracle --require-complete
python3 -m unittest discover -s q3/remeasure -t q3/remeasure
```

**Pass:** no `pending` and no `FAIL`.

## 7. The drift-free re-score: the same bytes on both sides

A page that moved between the fleet's capture and the emulator's run says nothing about the emulator. To remove that, save each page once, serve the copy, and have the fleet and the emulator read the same file:

```sh
python3 q3/remeasure/snapshot_all.py q3/results/corpus.json $W/static --jobs 6 --index $R/static/static-pages.json     # 102 copies (snapshot.mjs); --frames files / --lazy eager are options, not what the figures used
( cd $W/static && python3 -m http.server 8001 --bind 0.0.0.0 & )                                                         # on capture-host, beside the probe server on 8000
# the fleet: step 1 again for each box (policy through the playbook, stop Edge, empty, `after` probe; no `before` probe is needed, the control was shown in the first run), RB=$R/static/history-readback.json
python3 q3/corpus_capture.py q3/results/corpus.json $W/oracle-static --boxes $BOXES --label $LABEL --readback $R/static/history-readback.json --summary $R/static/capture-run.json --static-base http://<capture-host address>:8001      # a job ID; then `collect $W/oracle-static`, as in step 2
# then the after-run probe on each box, and step 5 (restore) with the same readback file
python3 q3/remeasure/make_views.py $W/oracle-static $W/view-orig $W/view-run http://127.0.0.1:8001                         # view-orig: capture.url is the original address (measure.py, split); view-run: the copy's address (run_all.py)
( cd $W/emu-gate && $PY q3/run_all.py $W/view-run $W/emu-gate-static --split all --runs 2 --jobs 5 --port-base 10100 )     # 5fbd726; and at head into emu-head-static
$PY q3/measure.py $W/view-orig $W/emu-gate-static --split held --final --json $R/static/misses-held-freeze.json > $R/static/measure-held-freeze.txt     # likewise head, and attribute.py
$PY q3/remeasure/explain_visited.py $W/oracle-static $W/emu-head-static $R/static/visited-explained.json
python3 q3/remeasure/check.py --results $R/static --control-from $R/history-readback.json --oracle $W/oracle-static
```

**Pass:** every copy exists (`snapshot_all.py` exits 0), `capture-run.json` shows `captured: 102, failed: []`, and `check.py` has no `FAIL`. The copies keep what a page had loaded (images, fonts and other-origin iframes are still fetched live; shadow DOM is not serialised).

