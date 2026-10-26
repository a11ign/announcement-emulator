# Round one of the agreement loop: the rule, fixed before the first fleet capture of A11-234 step 2

A11-228 decided (the chairman, 2026-10-24) that the middleware ships as a **preview, improved every release**, with **no fixed gate**. Each release prints its measured agreement by announcement type, and overall,
with the population and the date. Each round is judged by the figures going up against the previous release. The fleet's own agreement with itself is measured as the ceiling, so that the numbers are read
honestly. Predictions on a shape the attribution shows to be weak are flagged. **This round sets no target and asks the chairman for none:** the loop replaces it.

This file, the objects `freeze.json` names, `held-out-pages.json`, `round.py`, `run_round_readings.sh`, `measure_round.sh` and `.github/workflows/agreement-round.yml` are committed, and `freeze.json` names their
git objects, before any page is captured on the fleet for this round. `agreement/make_freeze.py check results/agreement-round-1/freeze.json` fails if any of them has moved since, or if a fleet capture is dated before
the freeze. The runtime it names is **step 1's**: the focus matched by DOM node, "same page" by the address the document has now, and the report's rates by shape (a11ign/announcement-emulator#11).

## What is adopted unchanged

The rule of A11-230 (`middleware/results/playwright-versions/rule.md`) is adopted **unchanged**, and through it A11-229's (`middleware/results/tree-source/rule.md`) and A11-208's (`middleware/results/agreement/rule.md`):
the corpus project of the sample suite (`middleware/sample-suite/tests/corpus`) with its steps, the same channels, units, shapes and matching (`middleware/agreement/measure.py`), the same fleet route
(`q3/fleet_capture.mjs --typing-dialog`, through `agreement/capture_fleet.py`), the same runtime, extension and sweep, the same two builds (Chromium 156.0.8078.4 in Playwright 1.64.0 and 1.64.1; 153.0.8010.12 in
1.63.0), the same six readings (each build × the extension on Linux, DevTools on Linux, DevTools on macOS) and the same control (DevTools on `ubuntu-latest`), and the same **headline figure**: every channel, stable
or not, the first fleet capture against the first passive run (`measure.py --include-unstable --tolerate-census`, the second block), with `--second` beside it. The closed list of causes of A11-229 and A11-230 keeps
its order and its meaning. **What changes is the pages, the cause list's two additions, and what is printed** (below).

## The pages

* **Held-out pages: the next six** by the spike's own selection rule (`agreement/select_pages.py`, with `--skip middleware/results/agreement/pages.json`: the six that were fitted against, and the one the rule rejected).
  The 46 candidates that remain keep the order of the SHA-256 of their address; each in turn is opened and kept if its DOM, and only its DOM, has at least ten tab stops and a text field (`dom_check.mjs`); the first six that
  are kept are the sample. They were selected with Playwright 1.64.1's own Chromium (`chromium-1248`) and written to `held-out-pages.json` **before this file was committed and before the freeze**. Neither the emulator nor the
  fleet read them before the freeze, and **no fix is made against them afterwards**: a fault they show is attributed and listed, and is the next round's to fix.
* **The fitted six** (`middleware/results/agreement/pages.json`) are measured in the same window and labelled **not held out**: the emulator was fitted against them (A11-155 to A11-176) and step 1 of this ticket looked
  at their misses. They are the like-for-like comparison with the previous figures.
* **The figure the supported-versions list prints is the held-out one.** The fitted figure is reported beside it and is never listed.

The corpus test reads its pages from `CORPUS_PAGES=<file>` when that is set, and from `./pages.json` otherwise. Its steps are unchanged.

## The ceiling

The oracle disagrees with itself: pages move between two readings, and a box may differ from another. The ceiling is the **fleet against itself**: the first capture against the second (two boxes, as the spike's rule does) on
**every channel**, on the same pages and units as the figure, overall, by channel and by shape. It is the "fleet against itself" column of `measure.py`, and `round.py` states it beside each figure.

**How it is read.** If the fleet agrees with itself on C% of the units, it disagrees with itself on (100 − C)%. A prediction cannot be told from the oracle's noise above C%: a rate near C% is as high as one reading of
the oracle can say, and a rate below it by more than the oracle's own noise is the middleware's. The ceiling is not a bound that any run reaches: the fleet against itself compares two readings of the oracle with each
other, and the middleware is compared with one. It is measured again for each round, because the pages and the boxes are.

## Attribution: every miss gets one cause

A11-229's closed list, in its order, with A11-230's `chromium build`, and **two causes added** by this round (`round.py` applies them after the others):

* `test blocked`: a miss on the `typed` or `field` channel with nothing predicted, on a page whose corpus test did not pass in the reading's first run (it timed out or failed before it had typed; the report says so).
  On the TfL page the modal cookie dialog blocks the test's click on the first text field. The test is part of this rule and is **not changed**, so those units are not a prediction and are attributed to the test, not "fixed".
  It is applied before every cause but the three that `measure.py` names from the strings (`prompt`, `language`, `history`), none of which has nothing predicted.
* `offscreen frame`: a miss of the `frames` channel in the extension's reading that is attributed `tree: …` (DevTools predicts it). Chromium does not tell the browser process of a frame it does not draw, so the
  extension's tree has the frame and nothing in it until the page is scrolled to it (`step-1-misses.md`); the DevTools source asks the page and has it.

`oracle milestone` keeps its meaning (available for a unit left `unexplained` or `no counterpart`, in `attribution-notes.json`, only where the build's milestone is not the oracle's). A reader's notes change no figure
and no count of agreed units. **`unexplained` is counted in every table, and every one carries its one-line reason.**

## What is printed, and when a shape is low confidence

The supported-versions list (`middleware/supported-versions.json`) holds, per build and per reading, the **held-out** headline: `agreement` (the rate `agreement.txt` prints, as a fraction), `units`, `date` (the day of
the passive runs), `figure` (`middleware/results/agreement-round-1/held-out/<build>/<source>-<os>/`), and the three fields a report prints (`middleware/src/supported.ts`):

* `population`: `{ pages, heldOut, units }`: the pages that were compared (a page that could not be opened, or that was not the same page on both sides, is not counted) and whether they were held out;
* `ceiling`: `{ agreement, units }`: the fleet against itself on the same units;
* `shapes`: one entry per announcement shape (`NAME + ROLE`, …) that has a unit, each `{ agreement, units, lowConfidence }`, over every channel.

Each figure directory holds `agreement.txt`, `misses.json` (every miss with its one cause) and `rates.json` (the counts the list is filled from, by channel and by shape, with the fleet against itself beside each and the
causes of each shape's misses). `supported.test.ts` holds the list to them.

**A shape is low confidence** when both hold, computed here and not at run time:

1. the upper bound of the Wilson 95% interval (z = 1.96) of its agreement is **below the reading's overall agreement**, so that the shape is weaker than the whole and not by chance in a few units;
2. at least one of its misses has a cause that is **not the oracle's or the test's**: not `page moved`, `oracle milestone`, `chromium build`, `network/runner` or `test blocked`. (`history`, `prompt`, `language`,
   `quick test`, `emulator`, `conversion`, `events`, `tree`, `offscreen frame`, `macos`, `focus match`, `no counterpart` and `unexplained` count against the middleware.)

A shape that is weak only because the oracle was is not flagged, and a shape with a handful of units has an interval too wide to be flagged on noise.

## How the round is judged

* **The previous figures** are A11-230 step 2's (`middleware/results/playwright-versions/<build>/<source>-<os>/agreement.txt`), on the fitted six: **up**, **down**, or **within** the 0.6 points of run-to-run
  movement that A11-229's rule records (the same extension source on the same fleet captures read 80.8% and 81.4% in A11-208), overall and for each of the ten commonest shapes that figure printed.
* The **held-out** figure is the next round's baseline. A held-out figure is compared with a fitted one only to say that the two sets differ (the fitted pages overstate what a new page gets).
* There is **no target and no gate.**

## The readings, the order and the fleet

* **Per page set and build, six readings:** the extension on Linux, DevTools on Linux (this host) and DevTools on macOS (`agreement-round.yml`), each two runs of `corpus` with
  `ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1` and the tree source forced explicitly (never left to the platform's default), in the build's own Playwright (`npm i -D @playwright/test@<version>` and
  `npx playwright install chromium`, nothing else). The package under test is the one built from the freeze commit.
* **The order on this host** (`run_round_readings.sh`): for each of two rounds, the held-out pages and then the fitted ones, each as `extension 156, extension 153, DevTools 156, DevTools 153`, so that a change of the
  pages or the network between runs falls on every reading alike. The macOS and `ubuntu-latest` jobs run the same, with DevTools forced. All runs are made within about two hours of the fleet captures, and the
  workflow run is started (by committing `ci-run.txt`) inside that window.
* **The fleet.** The same captures for every reading and both builds: each of the twelve pages twice, on two different boxes, through `agreement/capture_fleet.py`. The boxes are chosen with a read-only
  `fleet:status` and `/health`: the largest group that agrees on the worker's code hash, the Windows build, the browser build and NVDA. They are recorded in `boxes.md` and `fleet-readings.json` with each capture's
  own environment. **The fleet is frozen (A11-205): nothing on any box is changed**; a box that does not agree with the group is left out, not converged. `boxes.md` records each box's Edge version: whether the
  fleet now runs one Edge version (A11-183, A11-205), and a milestone that differs from a build's is the candidate for `oracle milestone`.
* The reports of macOS and of the control hold third-party pages' speech and the repository is public: they travel in a workflow artifact kept one day and deleted once downloaded. Only the tables and each miss are
  committed, as in A11-208.

## The files

`rule.md` (this), `held-out-pages.json`, `round.py` (the ceiling, the attribution's two additions, the rates by shape, the low-confidence flag, the movement and the list), `run_round_readings.sh` and
`measure_round.sh` (this host's runs and `measure.py` for each reading), `.github/workflows/agreement-round.yml`, `freeze.json` (the objects before the first capture), `boxes.md` and `fleet-readings.json`,
`ci-run.txt` (the stamp that starts the macOS workflow), `<held-out|fitted>/<build>/<source>-<os>/` (`agreement.txt`, `misses.json`, `rates.json`), `round.txt` and `round.json` (the tables), and `README.md` (the write-up).
