A11-165. The 102 corpus pages recorded once, with their scripts and every resource, and replayed to the fleet's Edge and the emulator's Chrome at their own addresses; the eleven misses the drift-free reading left unexplained are explained (ten are `method`: the script-free copy; one is Windows-only and could not be re-read), and the replay's figure at the freeze is **4,437 of 4,470 = 99.26%**. The write-up is the `### Scripted replay: the same bytes, scripts included` subsection of `docs/announcement-emulator-spike.md`; the evidence is in `q3/results/replay/`; the procedure A11-164 and A11-166 reuse is `q3/replay/RUNBOOK.md`.

Acceptance:

```bash
python3 -W error::ResourceWarning -m unittest discover -s q3/replay -t q3/replay          # 57 tests; the ones that start the proxy or Chrome are skipped where `setup.sh` has not built them
python3 -m unittest discover -s q3/remeasure -t q3/remeasure                              # the earlier checks and their tests, unchanged, plus the doc check's subsection rule and the replay checks
python3 q3/remeasure/check.py --replay --results q3/results/replay --control-from q3/results/remeasure/history-readback.json     # exit 0: readback, summary, figures, addresses, doc, replay-readback, manifest, served, explained all ok; `oracle` and `replay-stamps` read pending (the oracle's pages are third-party's and are not committed)
python3 q3/remeasure/check.py                                                              # the A11-155 run's checks, unchanged
grep -E '^GATE' q3/results/replay/measure-held-freeze.txt q3/results/replay/measure-held-head.txt     # 4437 of 4470 = 99.26% ; 4367 of 4376 = 99.79%
git diff origin/main --numstat -- docs/announcement-emulator-spike.md                      # additions only: N 0
```

With the oracle (`$EMU_DOWNLOADS/q3/replay/a11-165-2026-10-21/` on `capture-host`, or a run of `RUNBOOK.md`): `python3 q3/remeasure/check.py --replay --results q3/results/replay --control-from q3/results/remeasure/history-readback.json --oracle <oracle dir> --require-complete` exits 0.

## What changed

- `q3/replay/` (new): `record_all.py` and `record.mjs` record each page once through a mitmproxy recording proxy (the emulator's Chrome 155, Edge's user agent, scrolled to the end and back); `addon.py` and `archive.py` are the replay server (every request answered from one archive, nothing fetched live, `no-store`, the log of every request); `proxy.py`, `control.py`, `ca.py`, `flows.py`, `make_probe.py` start, steer and prove it; `fleet/replay-on.yml` and `replay-off.yml` put a box behind it and take it back (Edge's proxy policy strings and a per-run CA in the Trusted Root store, read back and asserted), `fleet/box.sh` runs them with the history plays and the probes, `fleet/scrub.py` takes every address out of what is kept; `serve_fleet.py`, `capture_hooks.py`, `run_replayed.py`, `with_replay.py`, `process.py`, `export_freeze.py` serve each box, read each page through its archive for the emulator, and export the freeze; `join.py` joins the two sides' logs; `evidence.py`, `start_state.py`, `explain.py`, `moved.py`, `oracle_summary.py` produce the evidence; `RUNBOOK.md` is the procedure.
- `q3/corpus_capture.py`: `--replay-run`, `--replay-ports`, `--replay-readback` capture each address at its own address with the box's server loaded with the page's archive, stamp the record with a `replay` block, and keep only a resumed record that is this run's. Without them it is as it was (the replay modules are not imported).
- `q3/remeasure/check.py`: `check_doc` accepts one `### ` subsection at the end of `## Re-measure` once the base has the section; `--replay` adds `replay-readback`, `manifest`, `replay-stamps`, `served` and `explained`.
- `emu/session.mjs`: with `EMU_PROXY` (and `EMU_PROXY_SPKI`) set, Chrome is launched through the proxy and trusts the run's authority by its hash; unset, the launch is unchanged.
- `setup.sh`: a pinned mitmproxy in `$EMU_DOWNLOADS/replay/venv`.
- `q3/results/replay/`: the manifest of the archives, the read-backs, the plays' output, the join, the figures, the misses and their classes, the evidence, the stamped summary of the oracle.
