# Re-measure with scripted page replay: the same bytes, scripts included, on both sides (A11-165)

**This is the procedure A11-164 (language names) and A11-166 (the new freeze and the Gate) reuse; A11-166's differences (new pages, consent, the freeze, the verdict) are in `q3/gate/RUNBOOK.md`.** It records each page of the corpus once, with its scripts and every resource it loads, and serves that recording to the fleet's Edge and to the emulator's Chrome
at the page's own address. Nothing is fetched live while a page is read. Every fleet step is Ansible from the control plane, one box first and then one at a time, with a read-back after each; nothing is changed by hand on a box and no box is reached by ssh from this host.
Results name workers (`a11y-worker-N`) and `capture-host`, never an address (`check.py` `addresses`).

What is committed is small: the manifest of the archives (`q3/results/replay/archive-manifest.json`: each address, archive file, sha256, number of exchanges, recording time), the per-page join of the servers' logs, the read-backs, the figures and the evidence.
The third-party bytes (the archives, the certificate authority, the fleet's oracle) are not: they live in `$EMU_DOWNLOADS/q3/replay/<run id>/` on `capture-host`, the persistent directory `emu/paths.py` names, so a later run can serve the same archive and prove it by the manifest's sha256.

## The tool

mitmproxy (pinned in `setup.sh`, in `$EMU_DOWNLOADS/replay/venv`), not Chromium's Web Page Replay. The plan recommended Web Page Replay and allowed another recorder that keeps its properties; this one does:
one recording per page, over an HTTPS proxy, repeated requests answered in the order they were made, the archive loaded by hash, and a certificate authority of the run's own (Web Page Replay's bundled certificate has a public private key and is never installed).
Web Page Replay needs a Go toolchain built from Chromium's `catapult`, which this host does not have, and has no per-run authority. `q3/replay/addon.py` is the whole of the replay server:

- a request is answered from the loaded archive by `archive.Archive.find` (exact, then the same path and query parameter names with other values, `fuzzy`); anything else is a `404` with `x-replay: miss`; **no connection to a real server is ever made** (`server_connect` refuses it);
- a recorded response goes out with its encoding taken off and `cache-control: no-store`, so the browser's cache cannot answer in the archive's place or hold the answer for the next page;
- a page recorded with consent given has `<archive>.consent.json`: the replay server adds its cookies, as `Set-Cookie`, to the page's documents (navigations) whose host may set them, the same for every client, so the fleet's Edge and the emulator's Chrome hold the consent before any script runs, and the log says how many it added (`consentCookies`);
- `http://replay.control/use?archive=<file>` loads an archive and clears the log; `http://replay.control/log` returns every request since, each as `exact`, `fuzzy`, `miss` or `blocked`, with the archive's sha256.

```sh
. ./env.sh      # see 0.; EMU is this checkout, EMU_DOWNLOADS the persistent directory, RUN the run's directory, R the results directory, W scratch
PYR=$EMU_DOWNLOADS/replay/venv/bin/python; PY=$EMU_DOWNLOADS/q2/venv/bin/python
```

## 0. Before anything

```sh
EMU_DOWNLOADS=... ./setup.sh                                      # builds replay/venv too (mitmproxy 12.2.3)
RUN_ID=a11-165-2026-10-21; RUN=$EMU_DOWNLOADS/q3/replay/$RUN_ID; mkdir -p $RUN $R $W
( cd ~/repos/control && pnpm run fleet:status )                   # the boxes are `ready`, none busy
```

**Boxes:** the largest group that agrees on every version `fleet:status` prints (browser, Windows build), at least three. A11-165 used the twelve of A11-155 (Edge 155.0.4283.62, build 26300.9711):
`a11y-worker-2`, `-3`, `-4`, `-7`, `-8`, `-9`, `-10`, `-12`, `-13`, `-14`, `-15`, `-16`.

## 1. Record each page once

```sh
python3 q3/replay/record_all.py q3/results/corpus.json $RUN --jobs 6 --manifest $R/archive-manifest.json
```

`record.mjs` loads each address in the emulator's own Chrome 155 (Edge's user agent, the 1008x872 window, scrolled to the end and back, as `snapshot.mjs` did) through a recording proxy; the scripts stay. The run's certificate authority is made fresh in `$RUN/ca` (its key never leaves it) and Chrome trusts it by its hash.
**Consent (A11-166).** Every page is recorded with consent already given, so neither side is served a cookie dialog: `record.mjs` first loads the page once in a browser of its own with no proxy, and `consent.mjs` finds the dialog's "accept all" control by role and accessible name from the one list in `consent-names.json` (one list for every page, no entry for a site). If it finds one, it is activated, the cookies the browser then holds are read through CDP, and the recorded load is made with them. `<archive>.consent.json` (`consent.py`), written beside the archive like `served.json`, says what happened: `given` (with the cookies), `no-dialog`, or `not-matched` (a dialog or a cookie-named region and no control of the list: nothing is served, and the page is named); the manifest carries each page's `consent`. `record.mjs --consent <address> <out.json>` runs only that pass.
**Pass:** exit 0, `102 of 102 addresses recorded`, and every address's `mainStatus` is read: a page that was down when it was recorded (`503` maintenance pages, A11-165 had seven) is recorded as it was and both sides read the same page, but its figures are not those of the live page. **The worker refuses a page the server answered with other than 2xx**, so such a page's archive gets a sidecar (`<archive>.served.json`, written by `record_all.py`) and the replay server answers its own address with status 200, the body as recorded; the manifest carries `servedStatus`, and `check.py` `manifest` fails a page recorded with an error status that is not served as 200. `python3 q3/remeasure/check.py --replay --results $R` has `manifest: ok`.

## 2. The servers: one for each box, and the archive-only probe

```sh
MARKER=$($PYR q3/replay/make_probe.py marker); echo $MARKER > $RUN/marker.txt        # three plain words: NVDA says a hex string in pieces
$PYR q3/replay/make_probe.py $RUN/archives "$MARKER"                                  # https://replay-probe.test/ exists in the archive and nowhere else
$PYR q3/replay/ca.py identify $RUN/ca/mitmproxy-ca-cert.pem > $RUN/ca-identity.json   # thumbprint (the Windows store) and SPKI (Chrome's flag)
python3 q3/replay/replay_readback.py init $R/replay-readback.json $RUN_ID <thumbprint> "$MARKER"
nohup $PYR q3/replay/serve_fleet.py $RUN a11y-worker-2=3202 a11y-worker-3=3203 ... > $RUN/serve-fleet.log &      # one server each, on this machine; `ready ...` when all answer
( mkdir $W/probe && cp q3/remeasure/visited-probe*.html $W/probe && cd $W/probe && nohup python3 -m http.server 8000 --bind 0.0.0.0 & )   # the history probe, as A11-155; Edge does not send it through the proxy
```

On the control plane (`/tmp/replay/$RUN_ID/`): this repository's two plays, the CA's **public** certificate as `ca.pem`, `override.yml` and `restore.yml` (`q3/remeasure/policy_override.py` on the plane's own `worker/defaults/main.yml`) and one `vars-<box>.json` for each box:
`{"replay_proxy": "<capture-host address>:<the box's port>", "replay_bypass": "<capture-host address>;localhost", "replay_thumbprint": "<thumbprint>", "replay_cert_src": "/tmp/replay/<run id>/ca.pem"}`.

## 3. One box at a time, the first alone: history off, replay on, probes

```sh
q3/replay/fleet/box.sh on a11y-worker-2          # the first box alone; then each other box one at a time: `box.sh change <box>` (the Ansible changes, one box at a time), and `box.sh probes <box>` (the captures, which may overlap)
```

`box.sh on` runs, for the box: the idle check; Edge stopped (ad hoc Ansible); **history off** through control's own play (`provision-role.yml --tags policy -e @override.yml`, as A11-155) and read back (`win_reg_stat` value 1); the history store emptied (`win_file`);
**replay on** through this repository's play (`q3/replay/fleet/replay-on.yml`: Edge's `ProxyMode`, `ProxyServer` and `ProxyBypassList`, the run's CA in `LocalMachine\Root`, the browser profile's cache, cookies and script storage emptied; it reads each back and fails if one did not land); then the two probes.
Each is stored by `readback.py` (history) and `replay_readback.py` (replay) in `$R/history-readback.json` and `$R/replay-readback.json`; the plays' output, with every address taken out by `fleet/scrub.py`, is in `$R/fleet/plays/`.
(control's `apply_dwords` writes DWORDs only and the proxy policy is a string, so the proxy and the certificate go through this repository's play, run from `/root/control/ansible` with control's own `ansible.cfg` and inventory. control is not changed.)

**Pass, per box:** the policy play's recap is `failed=0`; `replay-on.yml`'s last task prints `replay on: ProxyMode=fixed_servers ProxyServer=capture-host:<port> ...; certificate <thumbprint> found once in LocalMachine\Root`; the history `after` probe reads neither link `visited`; **the replay probe reads the run's marker as its heading**
(a page that exists only in the archive: the box is behind the server); `replay_readback.py` ends with `<box> passes`. **A box that does not pass stays off the run**; name it in the write-up.

## 4. Capture the same 102 addresses, at their own addresses

```sh
python3 q3/corpus_capture.py q3/results/corpus.json $W/oracle --workers "$WORKERS" --readback $R/history-readback.json --summary $R/capture-run.json \
  --replay-run $RUN --replay-ports "$PORTS" --replay-readback $R/replay-readback.json
for B in $BOXES; do q3/replay/fleet/box.sh afterrun $B; done      # both probes again, once the corpus is captured
```

Before each capture the page's archive is loaded into the box's own server, and after it the server's log is kept (`$RUN/fleet-logs/<slug>.<worker>.json`). Each record is stamped with a `replay` block (the run, the archive and its sha256, the number of requests and of unanswered ones, the box's read-back).
A worker without a passing history and replay read-back is refused by name. **Pass:** exit 0, `captured: 102, failed: []`.

## 5. The emulator, the same bytes

```sh
python3 q3/replay/export_freeze.py 5fbd726 $W/emu-gate        # the Gate figure's freeze, with the one launch change a replay needs (nothing of the emulator's logic); a commit that already has the launch (A11-165's, so every later one) is exported unchanged
$PYR q3/replay/with_replay.py --run $RUN --archive <slug>.flows --log <log> -- $PY q3/emulate.py <address> <out.json>      # one page, one run: the wrapper is what run_replayed.py calls
python3 q3/replay/run_replayed.py $W/oracle $W/emu-gate-out --run $RUN --root $W/emu-gate --split all --runs 2 --jobs 6 --port-base 10100       # 5fbd726 (a run past --timeout, 900 s, is ended with everything it started and its log kept)
python3 q3/replay/run_replayed.py $W/oracle $W/emu-head-out --run $RUN --root $PWD --split all --runs 2 --jobs 6 --port-base 10500            # head, not held out
```

The emulator reads each page at its original address through a replay server of its own loaded with that page's archive, with Chrome trusting the run's authority by its hash (`EMU_PROXY`, `EMU_PROXY_SPKI`, read by `emu/session.mjs`; with them unset the launch is unchanged). No `--history`. The pages are the oracle's records, so no view is made (`make_views.py` is for copies).

## 6. Prove it was served identically

```sh
python3 q3/replay/join.py $R/archive-manifest.json $RUN/fleet-logs $R/served-identically.json --emulator gate=$W/emu-gate-out/served --emulator head=$W/emu-head-out/served [--explained $R/served-explained.json]
python3 q3/remeasure/check.py --replay --results $R --control-from q3/results/remeasure/history-readback.json --oracle $W/oracle
```

`check.py` `served` fails a page whose sides were served another archive than the manifest's, or where a request the archive did not answer on one side was answered on the other, unless the page is named in `--explained` with its reason (the write-up carries it). A browser's own background requests (`join.BROWSER_OWN`) are counted, not compared.

## 7. Measure

```sh
python3 q3/measure.py $W/oracle $W/emu-gate-out --split held --final --json $R/misses-held-freeze.json > $R/measure-held-freeze.txt
python3 q3/measure.py $W/oracle $W/emu-head-out --split held --final --json $R/misses-held-head.json > $R/measure-held-head.txt
python3 q3/attribute.py $R/misses-held-freeze.json $R/misses-held-head.json $R/misses-held-freeze-attributed.json > $R/attribute.txt
python3 q3/replay/oracle_summary.py $W/oracle $R/oracle-summary.json                                                                  # what is committed of the oracle
python3 q3/replay/moved.py <the earlier reading's misses-held-freeze.json> $R/misses-held-freeze.json $W/oracle $R/pages-moved.json   # which pages' comparability changed, and what the fleet's capture of each holds
```

`measure.py` and `attribute.py` are unchanged and so is the split (`q3/split.py`): the figures are the drift-free subsection's, on the same rules. The eleven misses of the drift-free reading are then classed one by one, by `explain.py`, which reads what the replay shows of each (`method` when the page is comparable at the freeze and the announcement is not a miss) and takes a class and evidence for any other from `$R/misses-manual.json`; each class has evidence files under `$R` (`evidence.py` for the lists side by side, the fleet's own `fleetStart`; `start_state.py` under `with_replay.py` for the emulator's focus and caret when the sweeps start, at head only: the frozen emulator has no scroll step to start from):

```sh
python3 q3/replay/evidence.py $W/oracle $R/evidence --emulator gate=$W/emu-gate-out --emulator head=$W/emu-head-out --page components/checkboxes   # or --channel links --entry <needle> --before-misses <earlier misses.json>
python3 q3/replay/explain.py <earlier attributed misses.json> <earlier misses.json> $R/misses-held-freeze.json $R/misses-held-head.json $R/misses-explained.json --manual $R/misses-manual.json
```

`check.py` `explained` reads `misses-explained.json`: it wants exactly eleven, each `method`, `emulator bug` or `Windows-only` with evidence that is a file under `$R`, or `unexplained` with what was tried, and each on the page.

## 8. Put the fleet back, one box at a time, through the same route

```sh
q3/replay/fleet/box.sh off a11y-worker-2          # then each other box
```

`replay-off.yml` removes the three proxy values and the certificate and reads both back as absent; the history policy goes back to `0` through the same play as before (`provision-role.yml --tags policy -e @restore.yml`, read back with `win_reg_stat`); the replay probe no longer reaches the archive; `fleet:status` shows the box `ready`.
**Pass:** each of those, in that order, after the after-run probe, for every box that was changed (`replay_readback.py` `restoredOk`). The history value stays in the registry, as 0, as after A11-155.

## 9. Write it up and check

Append one `### Scripted replay: the same bytes, scripts included` subsection to `docs/announcement-emulator-spike.md`, at the end of `## Re-measure` (before `## What this page does not settle, and follow-ups`); nothing else on the page changes
(`check.py` `doc` refuses anything else once the base has the section). Then:

```sh
python3 q3/remeasure/check.py --replay --results $R --control-from q3/results/remeasure/history-readback.json --oracle $W/oracle --require-complete
python3 -W error::ResourceWarning -m unittest discover -s q3/replay -t q3/replay
python3 -W error::ResourceWarning -m unittest discover -s q3/remeasure -t q3/remeasure
```

**Pass:** no `pending` and no `FAIL`.

## What the replay does not remove

- The fleet's Edge keeps its own profile between captures (the worker reuses the browser). `replay-on.yml` empties the profile's cache, cookies, service workers and script storage at the start of the run; a cookie or storage entry a page sets during the run is still there for a later page of the same site, which the emulator's fresh Chrome does not have.
- A request a page makes only because of something the recording never did (a control the sweep activates, a timer past the recording) is a `miss` and is logged for the side that made it; the join names it.
- Browser-own background traffic (updates, time sync) differs between Chrome and Edge and is not compared.
- The recording is one load by one Chrome. A page whose scripts choose content by chance or by clock replays the choice they made then, to both sides.
