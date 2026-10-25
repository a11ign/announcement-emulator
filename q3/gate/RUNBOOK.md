# The Gate on new pages, held out: consent given, the emulator frozen first (A11-166)

This is `q3/replay/RUNBOOK.md` with four things changed. Read that first: the recording, the servers, the fleet's set-up and restoration, the capture, the emulator's runs and the proof that both sides were served the same bytes are its steps 0 to 6 and 8, and they are not repeated here.
Every fleet step is Ansible from the control plane, the first box alone and then one at a time, with a read-back after each; nothing is changed by hand on a box and no box is reached by ssh from this host.
**Its step 4, the replayed corpus capture, is withdrawn on the fleet job service (A11-246)**: see that step's note. The capture below that this runbook builds on cannot be run until a replay server can serve a whole run's archives at once, which is a follow-up.
Results go to `q3/results/gate/`. They name workers (`a11y-worker-N`) and `capture-host`, never an address (`check.py addresses`).

```sh
export EMU=$PWD EMU_DOWNLOADS=~/spikes/announcement-emulator-5661 RUN_ID=a11-166-2026-10-23 R=$PWD/q3/results/gate W=<scratch>
RUN=$EMU_DOWNLOADS/q3/replay/$RUN_ID; PYR=$EMU_DOWNLOADS/replay/venv/bin/python; PY=$EMU_DOWNLOADS/q2/venv/bin/python; CORPUS=$R/corpus-run.json
```

## What differs

**1. The address list: new pages, never read (`q3/gate/snapshot_batch2.py`).** The Gate's population is a batch of the lab's real-page corpus that nobody has read, drawn by ADR 0010's rule (A11-170, a11ign/lab#144) and split by `q3/split.py` as the earlier corpus was.

```sh
python3 q3/gate/snapshot_batch2.py <lab checkout> <the lab's merge commit of A11-170> $R/corpus-batch2.json      # the entries marked `batch: 2`, the lab commit, the file's sha256, each address's split
python3 q3/gate/snapshot_batch2.py --run-list $R/corpus-batch2.json q3/results/corpus.json $CORPUS             # what is recorded and captured: batch 2 (both halves) and the earlier corpus's 60 held pages
```

The lab is read with `git show <commit>:src/training/real-page-corpus.mjs`, never imported (ADR 0045). The earlier 60 held pages are in the run again so that one cookie rule holds for every page measured; they are reported at the new freeze, **labelled "not held out"**: the emulator was fixed against their misses.

**2. Consent is given in the recording (`q3/replay/consent.py`, `consent.mjs`, `consent-names.json`).** A page that builds a cookie dialog with its scripts shows it to the fleet's Edge and not to the script-free copy, or the reverse, and the fleet's NVDA starts reading in it. So no page is served a dialog: `record_all.py` loads each page once in a browser of its own, finds the dialog's "accept all" control by role and accessible name from **one list for every page** (no entry names a site), activates it, reads the cookies the browser then holds through CDP, and records the page with those cookies. `<archive>.consent.json` says `given` (with the cookies), `no-dialog`, or `not-matched` (a dialog or a cookie-named region and no control in the list; nothing is served and the page is named). The replay server then adds the cookies, as `Set-Cookie`, to the page's documents for every client alike, so the fleet's Edge and the emulator's Chrome hold the consent before any script runs.
**The list is fixed before the freeze.** It was made by reading the earlier corpus's dialogs only (`record.mjs --consent <address> <out.json>` prints what the rule finds on a page); no page of batch 2 was read before the freeze, and nothing of the list is changed after it.

```sh
python3 q3/replay/record_all.py $CORPUS $RUN --jobs 6 --manifest $R/archive-manifest.json        # the manifest carries each page's `consent`
python3 q3/gate/consent_report.py $R/archive-manifest.json $W/oracle $W/emu-out $R/consent-report.json      # after the captures and the emulator's runs: where each side begins, page by page
```

**3. The freeze is named and committed before any page of the run is captured (`q3/gate/make_freeze.py`).** The emulator is the commit of `origin/main` after A11-164 (its language table), with no change from this ticket. `freeze.json` names the commit, the time, and the git object of `emu/` and of the harness and the rules the figure is measured by; `check.py freeze` compares them with the branch's head and every record's `capturedAt` with `namedAt`.

```sh
python3 q3/gate/make_freeze.py origin/main $R/freeze.json --includes A11-164=<A11-164's merge commit>
git add $R/freeze.json && git commit && git push                                                  # BEFORE the first capture of the run
python3 q3/replay/export_freeze.py $(python3 -c "import json;print(json.load(open('$R/freeze.json'))['commit'])") $W/emu-freeze      # `git archive` of that commit; with the proxy launch it already has, nothing is patched
```

The emulator's runs (`run_replayed.py`, two runs a page, no `--history`) use `--root $W/emu-freeze`; there is no run of head beside it, because head and the freeze are the same emulator.

**4. The verdict follows the spike's rule as written (`check.py verdict`).** The Gate is passed only when the held figure of batch 2 is at least 98% **and** every one of its ten-shape misses is attributed to an `emulator bug` or a `Windows-only` behaviour. A miss attributed to `method` (something the replay did differently on the two sides) or left `unexplained` fails the Gate, as `visited` did in the spike's Gate section. Every miss is attributed either way, one class each, with evidence: `check.py explained` reads `misses-attributed.json` against the figure's own misses file, every miss once.

## The figures

```sh
python3 q3/gate/views.py $W/oracle $CORPUS $W/views                                                           # the oracle read as `batch2` and `old60`
python3 q3/measure.py $W/views/batch2 $W/emu-out --split held --final --json $R/misses-held-freeze.json > $R/measure-held-freeze.txt      # THE GATE FIGURE
python3 q3/measure.py $W/views/batch2 $W/emu-out --split dev  --json $R/misses-dev-freeze.json > $R/measure-dev-freeze.txt                # batch 2's dev half, also never read before the freeze: labelled
python3 q3/measure.py $W/views/old60  $W/emu-out --split held --final --json $R/misses-old60-freeze.json > $R/measure-old60-freeze.txt   # the earlier 60 pages at this freeze: NOT HELD OUT
python3 q3/attribute.py $R/misses-held-freeze.json $R/misses-held-freeze.json $R/misses-held-freeze-attributed.json > $R/attribute.txt
python3 q3/gate/comparability.py $R/misses-held-freeze.json $R/consent-report.json $R/comparability.json      # how many pages are comparable, and one reason for each that is not
```

`measure.py` and `attribute.py` are unchanged (their git objects are in `freeze.json`). The emulator at head is the freeze, so `attribute.py` is given the freeze twice and finds nothing "fixed afterwards".

## Check

```sh
python3 q3/remeasure/check.py --replay --gate --results $R --corpus $CORPUS --control-from q3/results/remeasure/history-readback.json --oracle $W/oracle --require-complete
python3 -W error::ResourceWarning -m unittest discover -s q3/replay -t q3/replay
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure
python3 -W error::ResourceWarning -m unittest discover -s q3/gate -t q3/gate
```

**Pass:** no `pending` and no `FAIL`. Without the oracle (its pages are third-party's and are not committed), `oracle` and `replay-stamps` read `pending`, which is as for the earlier readings.
