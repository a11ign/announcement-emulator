# The per-build measurement: the rule, fixed before the first fleet capture of A11-230 step 2

A11-230 makes the middleware run in the Chromium the team's Playwright installed, and the package lists the builds it has a **measured agreement rate** for. This file, `compare_builds.py`, `run_build_readings.sh`,
`.github/workflows/playwright-versions-agreement.yml`, `middleware/src/supported.test.ts` and the objects `freeze.json` names are committed, and `freeze.json` names their git objects, before any page is captured on the fleet
for this step. `agreement/make_freeze.py check results/playwright-versions/freeze.json` fails if any of them has moved since, or if a fleet capture is dated before the freeze.

## What is adopted unchanged

The rule of A11-229 (`middleware/results/tree-source/rule.md`) is adopted **unchanged**, and through it A11-208's (`middleware/results/agreement/rule.md`): the same six pages (`middleware/results/agreement/pages.json`),
the corpus project of the sample suite (`middleware/sample-suite/tests/corpus`), the same channels, units, shapes and matching (`middleware/agreement/measure.py`), the same fleet route
(`q3/fleet_capture.mjs --typing-dialog`, through `agreement/capture_fleet.py`), the same runtime, extension and sweep, and the same **headline figure**: every channel, stable or not, the first fleet capture against the first
passive run (`measure.py --include-unstable --tolerate-census`, the second block), with `--second` beside it. The pages are **not held out** (the emulator was fitted against them in A11-155 to A11-176): everything measured
here is *measured* and **not held out**. The attribution causes of A11-229 keep their order and their meaning, and one is added below.

## The builds

Read from `npm view @playwright/test` and each version's `playwright-core/browsers.json` on 2026-10-25 (`latest` is 1.64.1, and nothing newer has shipped since the plan of 2026-10-24):

| Playwright | Chromium revision | Chromium build | measured in |
|---|---|---|---|
| 1.64.0, 1.64.1 | 1248 | `156.0.8078.4` | `@playwright/test@1.64.1` |
| 1.63.0 | 1243 | `153.0.8010.12` | `@playwright/test@1.63.0` |

The list is keyed by the **exact Chromium build**, because the build is what is measured. 1.64.0 and 1.64.1 ship the same revision and the same build, so they are one entry and one measurement (1.64.1, the repository's own).
The build each run used is read from the run itself (`/json/version` of its DevTools port, the `startup.chromium` of each worker in the run's `run.json`), never from `browsers.json`: a run whose workers report another build than its row names is not kept (`run_build_readings.sh` and the workflow check it), and each run's build is recorded in `passive-runs.json`.

## The readings

Per build, three: the extension on Linux, DevTools on Linux, and DevTools on macOS: the three pairs of tree source and platform the automatic pick produces on the two runners. Six readings over the two builds.
Windows is not measured, as in A11-229: it keeps the extension default and reads "not measured".

| reading | tree source | where it runs |
|---|---|---|
| `extension-linux` | the extension (`ANNOUNCEMENT_EMULATOR_TREE=extension`) | this host (Linux x64), the build's own Playwright and `chromium` (the full browser, `channel: "chromium"` as `attach()` sets it) |
| `devtools-linux` | the DevTools port (`ANNOUNCEMENT_EMULATOR_TREE=devtools`) | this host |
| `devtools-macos` | the DevTools port | a `macos-latest` GitHub runner (`playwright-versions-agreement.yml`, job `reading`) |
| `devtools-ubuntu-ci` | the DevTools port | an `ubuntu-latest` runner of the same workflow run: **a control**, reported and used for attribution only, not listed |

Each reading is **two runs** of `corpus` with `ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1` and the source forced explicitly (never left to the platform's default), in the build's own Playwright (`npm i -D @playwright/test@<version>` and
`npx playwright install chromium`, nothing else). The package under test is the one built from the freeze commit.

**The order.** On this host the eight runs are interleaved by build and by source, so that a change of the pages or the network between runs falls on every reading alike:
`extension 156, extension 153, devtools 156, devtools 153`, then the same four again (`run_build_readings.sh`). The macOS and ubuntu-latest jobs run, in one job each, `156, 153, 156, 153` with DevTools forced.
All runs are made within about two hours of the fleet captures, and the workflow run is started (by committing `ci-run.txt`) inside that window.

## The fleet

The same captures for every reading and both builds: each of the six pages twice, on two different boxes, through `agreement/capture_fleet.py`, so the oracle does not differ between the builds. The boxes are chosen with a
read-only `pnpm run fleet:status`: the largest group that agrees on the worker's code hash, the Windows build, the browser build and NVDA. They are recorded in `boxes.md` and `fleet-readings.json` with each capture's own
environment. **The fleet is frozen (A11-205): nothing on any box is changed**, and a box that does not agree with the group is left out, not converged.
The oracle's Edge is a milestone of its own (156 at the plan's reading), and the emulator's mapping tables are Chromium 155's (`pins.env`, `CHROME`). `boxes.md` records both, and the milestone of each build against the oracle's.

## The figure

For each reading, `measure.py --include-unstable --tolerate-census` (the second block is the headline) and `--second`, into `middleware/results/playwright-versions/<build>/<source>-<os>/` (`agreement.txt` and `misses.json`). The list
(`middleware/supported-versions.json`) holds, per build and per reading, the headline: `agreement` (agreed over units, the fraction `agreement.txt` prints as a percent), `units`, `date` (the day of the passive runs) and `figure`
(that directory). `supported.test.ts` asserts that every listed figure directory exists and that its `agreement.txt` gives the same rate.

**No margin and no target** (A11-228: a preview, improved every release, no fixed accuracy gate). Every build that is measured is listed, whatever its rate. What the extension buys is reported per build (the lead in points over
the units both sources compare, and the discordant units), and moves no rule.

## Attribution: every miss gets one cause

A11-229's closed list, in its order, with **one cause added**, `chromium build`, applied by `compare_builds.py` to a miss of a reading **after** `compare_sources.py`'s `quick test` (cause 3 of A11-229's table) and before the
rest, to a unit where **the two builds' runs differ from each other with the same source on the same captures**: the same unit, the same source, the same platform, and the two builds predict different strings, while each build's
own second run predicts what its first run did (so that the difference is the build's and not the run's). Its `reason` names the two strings. The cause applies to the reading of either build; the unit's other reading is named
in `reason`, and the cause stays one per miss.

`oracle milestone` keeps A11-229's meaning, read against each build's milestone: it is available for a unit left `unexplained` or `no counterpart`, in `attribution-notes.json`, only where the build's milestone is not the oracle's
(`boxes.md` says which). A reader's notes change no figure and no count of agreed units.
**`unexplained` is counted in every table, and every one carries its one-line reason.**

## The files

`rule.md` (this), `compare_builds.py` (applies `compare_sources.py`'s attribution to each build's readings, adds `chromium build`, and writes the tables and the lead per build), `run_build_readings.sh` (this host's eight runs, interleaved),
`agreement/measure_readings.sh` (`measure.py` for each reading, run once per build), `freeze.json` (the objects before the first capture), `boxes.md` and `fleet-readings.json`, `passive-runs.json`, `ci-run.txt` (the stamp that
starts the macOS workflow), `<build>/<source>-<os>/` (`agreement.txt`, `misses.json`), `comparison.txt` and `comparison.json`, and `README.md` (the write-up). The fleet's records and the passive reports are third-party pages' data and
are not committed: the tables and each miss are, as in A11-208. The macOS and control reports travel in a workflow artifact kept one day and deleted once downloaded.
