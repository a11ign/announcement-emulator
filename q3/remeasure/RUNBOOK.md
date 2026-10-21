# Re-measure the Gate on a clean-history oracle (A11-155)

Run from the control plane (the host with the fleet inventory), in a checkout of this branch beside a checkout of `control`. Every fleet step is Ansible, one box first and then one at a time, with a read-back after each.
Nothing here is changed by hand on a box, and no step names a worker's address: workers are `a11y-worker-N`, the page server is `capture-host`.

```sh
EMU=$PWD                      # this checkout
CONTROL=~/control             # the control checkout the fleet is run from
export ANSIBLE_CONFIG=$CONTROL/ansible/ansible.cfg
R=$EMU/q3/results/remeasure
mkdir -p $R /tmp/remeasure
FIRST=a11y-worker-2           # the box that goes first
```

`worker_url NAME` below is the worker's own URL (`http://<its inventory address>:8765`), read from the inventory and never written down:

```sh
worker_url() { ansible-inventory --host "$1" | python3 -c 'import json,sys; print("http://%s:8765" % json.load(sys.stdin)["ansible_host"])'; }
```

## 0. Before anything

Serve the probe page from `capture-host` and take the fleet's state:

```sh
python3 -m http.server 8000 --directory $EMU/q3/remeasure &        # on capture-host; the page is http://capture-host:8000/visited-probe.html
( cd $CONTROL && npm run fleet:status ) | tee /tmp/remeasure/status-before.txt
```

**Pass:** `fleet:status` lists the boxes `ready`, none `busy`, and prints the versions. Choose the run's boxes as the spike did: the largest group that agrees on every version, and at least three. Name them in `BOXES`.

```sh
BOXES="a11y-worker-2 a11y-worker-3 a11y-worker-4 a11y-worker-7 a11y-worker-8"      # example: edit to the group fleet:status shows
```

## 1. The probe, before, on the first box (the positive control)

```sh
node $EMU/q3/fleet_capture.mjs $FIRST=$(worker_url $FIRST) http://<capture-host address>:8000/visited-probe.html /tmp/remeasure/$FIRST.before.json
python3 $EMU/q3/remeasure/readback.py probe $R/history-readback.json $FIRST before /tmp/remeasure/$FIRST.before.json
```

**Pass:** the command prints `before ... visited: True ... as expected`. This proves the probe can see history. If it prints `NOT AS REQUIRED`, stop: `visited-probe.html`'s second link needs an address this box has visited
(any address of `q3/results/corpus.json` that the spike's misses name as `visited`). Change that link and capture again; do not go on with a probe that cannot see history.

## 2. Policy and emptying, one box at a time

For each box `B` in `BOXES`, `$FIRST` first (check the box is idle, run the policy play, read the value back, empty the store, probe):

```sh
python3 $EMU/q3/remeasure/policy_override.py $CONTROL/ansible/roles/worker/defaults/main.yml > /tmp/remeasure/override.yml      # once; read it: it must be the declared list plus SavingBrowserHistoryDisabled=1
cd $CONTROL

# idle: both must hold, because --tags skips the play's own busy check
curl -s http://$(ansible-inventory --host $B | python3 -c 'import json,sys; print(json.load(sys.stdin)["ansible_host"])'):8765/health | python3 -c 'import json,sys; assert json.load(sys.stdin)["busy"] is False'
ansible $B -m ansible.windows.win_shell -a '(Get-Process msedge -ErrorAction SilentlyContinue | Measure-Object).Count'          # must print 0

# the policy, through the fleet's own play (look first on the first box only)
ansible-playbook ansible/provision-role.yml --tags policy -l $B -e @/tmp/remeasure/override.yml --check --diff                   # first box only: the diff is one value, SavingBrowserHistoryDisabled
ansible-playbook ansible/provision-role.yml --tags policy -l $B -e @/tmp/remeasure/override.yml | tee /tmp/remeasure/$B.policy.txt
ansible $B -b -m ansible.windows.win_reg_stat -a 'path=HKLM:\SOFTWARE\Policies\Microsoft\Edge name=SavingBrowserHistoryDisabled'  # "value": 1

# empty the history the box already has: as the worker's own account, no -b
for f in History History-journal 'Visited Links'; do
  ansible $B -m ansible.windows.win_file -a "path='%LOCALAPPDATA%\\a11y-witness\\edge-profile\\Default\\$f' state=absent"
done

cd $EMU
python3 q3/remeasure/readback.py policy $R/history-readback.json $B 1 "provision-role.yml --tags policy asserted all policy values; win_reg_stat read value 1"
python3 q3/remeasure/readback.py emptied $R/history-readback.json $B "Default/History, History-journal, Visited Links"
node q3/fleet_capture.mjs $B=$(worker_url $B) http://<capture-host address>:8000/visited-probe.html /tmp/remeasure/$B.after.json
python3 q3/remeasure/readback.py probe $R/history-readback.json $B after /tmp/remeasure/$B.after.json
```

**Pass, per box:** the policy task `Refuse to call this provisioned if a policy value did not land` is `ok` and says `all N policy values verified`; `win_reg_stat` shows `"value": 1`; the `after` probe prints `visited: False ... as expected`
and `readback.py` ends with `<box> passes`. **A box that does not pass stays off the run**; name it in the write-up and go on with the others.
Then read `fleet:status` again: the boxes still `ready`, and `provisionRevision` unchanged (it hashes the role's files, so it does not move; that is why the capture records the setting).

## 3. Capture the same 102 addresses

```sh
WORKERS=$(for B in $BOXES; do printf '%s=%s,' $B $(worker_url $B); done | sed 's/,$//')
python3 q3/corpus_capture.py q3/results/corpus.json /tmp/remeasure/oracle --workers "$WORKERS" --readback $R/history-readback.json --summary $R/capture-run.json
```

**Pass:** exit 0, `capture-run.json` shows `captured: 102, failed: []`, and the box names are the passing ones (a worker without a passing read-back is refused by name). Then, per box, capture the probe again as in step 2 into `/tmp/remeasure/$B.after-run.json` and record it with `readback.py probe $R/history-readback.json $B after-run ...`,
and read `fleet:status` and `/health` again (the spike kept both readings in `fleet-readings.txt`; keep these in `$R/fleet-readings.txt`).

## 4. The visited count: the run stops here if it is not 0

```sh
python3 q3/remeasure/check.py --oracle /tmp/remeasure/oracle
```

**Pass:** `ok  oracle: 102 records, all stamped, visited count 0` and no `FAIL` line. A non-zero count means the history was not clean: record why in the write-up and measure nothing.

## 5. Freeze, then measure (needs `setup.sh`'s `$EMU_DOWNLOADS`)

Name both freezes in `$R/freeze.json` and commit it **before** the held output exists:

```sh
git worktree add /tmp/remeasure/emu-gate 5fbd726                  # the Gate figure: the last emulator commit fitted to the dev half only
HEAD_SHA=$(git rev-parse 43b7fc1)                                  # the head figure: the emulator at the plan's branch point
printf '{"gate": {"commit": "%s"}, "head": {"commit": "%s", "note": "not held out: fitted to the held half"}}\n' $(git rev-parse 5fbd726) $HEAD_SHA > $R/freeze.json
git add $R/freeze.json && git commit -m "docs(q3): the two freezes of the re-measure, named before the held reading"

( cd /tmp/remeasure/emu-gate && python3 q3/run_all.py /tmp/remeasure/oracle /tmp/remeasure/emu-gate-out --split held --runs 2 )          # no --history
python3 q3/run_all.py /tmp/remeasure/oracle /tmp/remeasure/emu-head-out --split held --runs 2                                              # at head
python3 q3/measure.py /tmp/remeasure/oracle /tmp/remeasure/emu-gate-out --split held --final --json $R/misses-held-freeze.json > $R/measure-held-freeze.txt
python3 q3/measure.py /tmp/remeasure/oracle /tmp/remeasure/emu-head-out --split held --final --json $R/misses-held-head.json > $R/measure-held-head.txt
python3 q3/attribute.py $R/misses-held-freeze.json $R/misses-held-head.json $R/misses-held-freeze-attributed.json
```

`measure.py` is run from head in both cases (its rules are the corrected ones); only the emulator differs. No emulator fix is made in this ticket. The held half only; the dev half is not needed for the Gate figure.

## 6. Put the fleet back, one box at a time

```sh
cd $CONTROL
for B in $BOXES; do
  ansible $B -b -m ansible.windows.win_regedit -a 'path=HKLM:\SOFTWARE\Policies\Microsoft\Edge name=SavingBrowserHistoryDisabled state=absent'
  ansible $B -b -m ansible.windows.win_reg_stat -a 'path=HKLM:\SOFTWARE\Policies\Microsoft\Edge name=SavingBrowserHistoryDisabled'      # "exists": false
done
npm run fleet:status
```

**Pass:** `"exists": false` on every box that was changed, and `fleet:status` shows them `ready`. A box that fails the read-back is not carried on from; the others continue.

## 7. Write it up and check

Append one `## Re-measure` section to `docs/announcement-emulator-spike.md`, after `## Gate` (the Gate section's own text is not changed): the date and boxes by name, the policy, the read-back and probe results, the capture window
(`capture-run.json`), the `visited` count, both figures with their populations, the misses by cause, whether the Gate is passed on the spike's reading (at least 98% and no unexplained miss; a miss on a page that changed is unexplained),
and that the fleet was restored. Then:

```sh
python3 q3/remeasure/check.py --oracle /tmp/remeasure/oracle --require-complete
python3 -m unittest discover -s q3/remeasure -t q3/remeasure
```

**Pass:** no `pending` and no `FAIL`.
