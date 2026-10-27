# The DevTools measurement: the rule, fixed before the first fleet capture of A11-229's fourth step

The chairman decided on 2026-10-25 that **DevTools is the only tree source**, and that step 2's stop is a work list and not a veto (the ticket's Decisions). Steps 1 to 3 of the plan did the work: the fields DevTools lacked were filled from the protocol
(#30), the tree is read again at the cost of what changed (#32), and the companion extension is removed (#34). This step measures the source that ships, against the fleet, under a rule written before anything is captured.

This file, `pages.json`, `agreement/make_devtools_pages.py`, `agreement/compare_devtools.py`, `agreement/run_devtools_readings.sh`, `agreement/merge_reports.py`, `.github/workflows/devtools-source-agreement.yml` and the objects
`freeze.json` names are committed, and `freeze.json` names their git objects, before any page is captured on the fleet for this step. `agreement/make_freeze.py check freeze.json` fails if any of them has moved since, or if a fleet capture is dated
before the freeze. **The runtime the freeze names is the runtime that ships** (`middleware/runtime`, `middleware/src` and `emu` as step 3 and A11-234 left them): no file under them changes after the freeze.

## What is adopted unchanged

The rule of steps 1 and 2 (`middleware/results/tree-source/rule.md`, `middleware/results/tree-source-structure/rule.md`), which adopt the Q5 rule of A11-208 (`middleware/results/agreement/rule.md`): the corpus test's walk (Tab until focus comes
round, at most 150 stops, Escape twice, type into the first text field), the channels, units, shapes and matching of `measure.py`, the fleet route (`q3/fleet_capture.mjs --typing-dialog` through `agreement/capture_fleet.py`, as one fleet job), and
the headline: **every channel, stable or not, the first fleet capture against the first passive run, `--include-unstable --tolerate-census`**. `measure.py` is not changed. Everything measured here is *measured* and **not held out**: the
emulator has never been fitted to these pages, but it was fitted to the kinds of page the fleet's corpus holds, and the six pages of step 1 are the ones it was fitted against. The held-out figure of the middleware is A11-234's
(`middleware/results/agreement-round-1/`), which is what `supported-versions.json` lists; this measurement does not replace it (see "What is published").

## Which pages: 19

`middleware/results/devtools-source/pages.json`, written by `agreement/make_devtools_pages.py` from three groups, and held to them by `agreement/test_make_devtools_pages.py`:

| group | pages | class | where it comes from |
|---|---|---|---|
| `step 1` | 6 | `corpus` | the six pages of `results/agreement/pages.json` (step 1's) |
| `step 2` | 8 | `table` (4), `list` (4) | the eight table- and list-heavy pages of `results/tree-source-structure/pages.json` (step 2's) |
| `large` | 5 | `large` | the five pages that file's `rejected` list left out for their size, 705 to 1,770 tab stops, for which the middleware once predicted nothing (the sample suite's `large` project) |

The table pages are in, as the decision asks. The headline is over all 19; it is also reported for the 14 pages of steps 1 and 2 alone, so that the figure sits beside the old ones on the same pages, and by group and by class. The sample
suite's three projects, `corpus`, `structure` and `large`, walk the three groups with one test body (held equal by `test_structure_walk.py` and `test_large_walk.py`); each page is walked by exactly one project.

## The first freeze, and why it was replaced

The rule was first frozen at `eaf063acdb` (2026-10-27 09:25:34 UTC), and a fleet job and the macOS workflow were started under it (09:25 and 09:26). Two things were found before any record of either was read:

1. the fleet job took four captures on `a11y-worker-5`, whose Windows is 22631 where the other fourteen boxes are 26300.9711, so `capture_fleet.py collect` refused to write any record ("a second OS image would blend two corpora into one"). The job's records were never read and are discarded; the second job names the twelve boxes of worker code `25bb45d9b38d7a62` and Windows 26300.9711;
2. the workflow served the bundle at the mirror's root and the package looks for `v<version>/<file>` there: the install answered 404 on both runners and no reading was taken (`gh run view 40480743889`). The workflow is a frozen object, so it was corrected (the mirror is laid out as a release is, as `tree-source-agreement.yml` lays it out) and the rule frozen again.

Nothing was compared: no figure, no agreement and no miss of any reading had been computed, and no fleet record had been opened. The runtime (`middleware/runtime`, `middleware/src`, `emu`) is the same git object in both freezes, so the six Linux passive runs taken between them (09:30 to 09:55 UTC) are readings of the runtime that
ships; they were taken before the second freeze and are not taken again. The first freeze stays in git history; `freeze.json` is the second.

## The readings

| reading | tree source | where it runs |
|---|---|---|
| `devtools-linux` | the DevTools port (the only source) | this host (Linux x64), in Playwright 1.64.1's Chromium 156.0.8078.4 |
| `devtools-macos` | the DevTools port | a `macos-latest` GitHub runner (`devtools-source-agreement.yml`, job `reading`), the same Playwright |
| `devtools-ubuntu-ci` | the DevTools port | an `ubuntu-latest` runner in the same workflow run: **a control**, reported and used for attribution only |

Each reading is **two runs** of each of the three projects with `ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1`, by `agreement/run_devtools_readings.sh` (run 1 of the three projects, then run 2), which writes `<out>/devtools-<n>/<project>/`; `agreement/merge_reports.py`
puts the three reports of a run together for `measure.py`. The runs set `AE_PROFILE`, which makes the runtime append one line to a file for each tree read and changes no prediction. The bundle is built from the freeze commit (`middleware/bundle/build.sh linux-x64`)
and the package packed from it. Windows is not measured. All the runs are made within about two hours of the fleet captures, and the macOS workflow is started (by committing `ci-run.txt`) inside that window.
A run whose workers report another Chromium build than 156.0.8078.4 is not a reading of this measurement.

## The fleet

Each of the 19 pages twice, on two different boxes, through `agreement/capture_fleet.py` as **one fleet job** labelled `A11-229`, read-only: the job takes its boxes by booking, refuses boxes that disagree on a version, and its manifest names each box and
its builds. They are recorded in `boxes.md` and `fleet-readings.json`. **The fleet is frozen (A11-205): nothing on any box is changed.** The oracle's Edge may be a milestone ahead of the browser the runs use; `boxes.md` says so, and `oracle milestone`
is a cause a reader may give (never the script).

## What is reported (no gate between sources: there is one)

For each reading, `measure.py --include-unstable --tolerate-census` and the same with `--second`. `compare_devtools.py` reports, for each reading and over the units it compares:

1. the headline over **all 19 pages**, over the **14 pages of steps 1 and 2**, by **group** and by **class** (`corpus`, `table`, `list`, `large`), each with the fleet against itself beside it (the oracle's own ceiling) and the second reading as the spread;
2. the figure **by channel** and **by the ten commonest announcement shapes**, the three readings side by side, and the causes of the misses by shape;
3. the **work list** of the chairman's decision, in units missed on the 14 pages of steps 1 and 2 *before* (the DevTools misses of steps 1 and 2, committed in `figure-devtools-linux/misses.json`) and *now*: `clickable` (the token differs), `header words` (the cell's string
   with words missing around its `row N` or `column N`), `typed value` (a miss of the `field` or `typed` channel) and `description words` (everything the source predicted is in the fleet's string and some of the fleet's words are not). This is a reading of the tokens
   in a **different window** (other days, the pages move), a count of misses of those kinds and not a proof of their cause; it is labelled so wherever it is printed;
4. the extension's old figures on the table pages (step 2: 323 of 342 units, 94.4%), as **context only**, labelled as not read in the same window: the extension is not read in this measurement, it no longer exists in the middleware;
5. the **cost** of the runs, by project, from the runtime's profile and `run.json` (`summarize_cost.py`): wall time, the runtime finishing after the last test, `speechMs`, and the tree reads, beside step 2's cost figures and the first measurement's wall times (415 to 450 s DevTools, 113 to 130 s the extension).

Nothing is a pass or a fail. **The recommendation is the chairman's decision, "DevTools is the only tree source", and the numbers are put beside it** (the ticket's Before-merge line: the measured tables and the recommendation). If the new figure on the table pages is
below the extension's old figure there, the write-up says by how much and what the misses are; it does not reopen the decision.

## Attribution: every miss gets one cause

Each miss of each reading (the first fleet capture against the first passive run, every channel) gets **exactly one** cause from the closed list below, written into that figure's `misses.json`. `compare_devtools.py` assigns them **mechanically, in this order;
the first that applies is the cause**. The list is step 1's, minus the causes that need the extension (`tree: ...`); with one tree source, the cause that said "the extension agrees where DevTools does not" is replaced by rule 7.

| # | cause | applies when |
|---|---|---|
| 1 | `prompt`, `language`, `history` | `measure.py`'s `classify` names it |
| 2 | `page moved` | the second fleet capture's list in the channel does not have the unit the first has |
| 3 | `quick test` | the unit is the last of `stops` or `typed` of the page, nothing was predicted for it, and this reading's two passive runs differ in that channel |
| 4 | `network/runner` | (macOS) the control predicts the string macOS predicts, and `devtools-linux` predicts another; (the control) it predicts a string other than `devtools-linux`'s |
| 5 | `macos: <field>` | (macOS) the control predicts a string other than macOS's, and `<field>` is what differs |
| 6 | the cause of the same unit in `devtools-linux` | (macOS and the control) all the readings that have the unit predict the same string, so what is wrong is what is wrong on this host |
| 7 | `emulator` | (this host) the extension, in step 1's or step 2's reading (their committed `figure-ext-linux/misses.json`), predicted **this same string** for the same page, channel and fleet string and missed it too: the tree did not decide it |
| 8 | `conversion: <field>` | DevTools predicted another string; `<field>` is what differs (step 1's list of fields); `conversion: node` when nothing was predicted for a list's unit |
| 9 | `events: <kind>` | nothing was predicted for a unit of `stops`, `field` or `typed`; `<kind>` is `focus` (stops, field) or `typed` |
| 10 | `unexplained` | anything else, with a one-line `reason` |

**What rules 8 and 9 say, and do not.** With no second tree source, nothing shows which of the tree's conversion, its events and the emulator is at fault for a miss that the extension never saw. Such a miss is given to the DevTools source's account
(`conversion` or `events`) and **named by what differs**, as the list A11-234 works from; the cause is not a finding that the tree is wrong. Rule 7 is the only evidence of the emulator's fault the script has, and it covers only the 14 pages of steps 1 and 2.
`oracle milestone` and `focus match` are never assigned by the script; a reader may attribute a unit left `unexplained` to one of them, or to any cause of the list, in `attribution-notes.json`, each with a reason and the evidence it was read from. The notes
change no figure and no count of agreed units. **`unexplained` is counted in every table, and every one carries its reason.**

## What is published

The tables and each miss are committed here (`figure-<reading>/`, `comparison.txt`, `comparison.json`), and the write-up is a section of `docs/playwright-middleware-spike.md`. **`supported-versions.json` is not written by this measurement**: the figure it lists for Chromium
156.0.8078.4 is A11-234's held-out one (`agreement-round-1`), the honest figure for pages the emulator had never seen; a figure over pages the emulator was fitted against, measured in the same window, would replace it with a better-looking and less honest one.
This measurement's figure is published as measured, by reading and by group, in the write-up. A11-234's per-release re-measure is what moves the listed figure.

## The files

`rule.md` (this), `pages.json`, `freeze.json`, `boxes.md` and `fleet-readings.json`, `passive-runs.json` (each run's dates and the counts of its runtime), `cost.json` (`summarize_cost.py` over the runs), `ci-run.txt` (the stamp that starts the macOS workflow),
`figure-<reading>/` (`agreement.txt` from `measure.py`, `misses.json` with the causes), `comparison.txt` and `comparison.json` (what `compare_devtools.py` printed), `attribution-notes.json` if a reader wrote any, and the step-2 cost directory (`cost/`).
The fleet's records and the passive reports are third-party pages' data and are not committed: the tables and each miss are, as in A11-208. The macOS and control reports travel in a workflow artifact kept one day and deleted once downloaded.
