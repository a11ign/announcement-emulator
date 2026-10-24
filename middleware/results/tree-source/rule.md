# The tree-source measurement: the rule, fixed before the first fleet capture of A11-229

A11-229 asks what the companion extension's tree buys over the DevTools port's tree, measured against the fleet. This file, `compare_sources.py`, `.github/workflows/tree-source-agreement.yml` and the objects `freeze.json` names are
committed, and `freeze.json` names their git objects, before any page is captured on the fleet for this ticket. `agreement/make_freeze.py check freeze.json` fails if any of them has moved since, or if a
fleet capture is dated before the freeze.

## What is adopted unchanged

The Q5 rule of A11-208 (`middleware/results/agreement/rule.md`) is adopted as it stands: the same six pages (`middleware/results/agreement/pages.json`), the corpus project of the sample suite
(`middleware/sample-suite/tests/corpus`), the same channels, units, shapes and matching (`middleware/agreement/measure.py`), the same fleet route (`q3/fleet_capture.mjs --typing-dialog`, through
`agreement/capture_fleet.py`), the same runtime, extension and sweep. `measure.py` gains two things before the freeze, and neither changes a figure: a refusal of a set of passive runs that mixes tree sources, and `--second`.
The pages are **not held out** (the emulator was fitted against them in A11-155 to A11-176). Everything measured here is *measured* and **not held out**.

## The readings

| reading | tree source | where it runs |
|---|---|---|
| `ext-linux` | the extension (`ANNOUNCEMENT_EMULATOR_TREE=extension`) | this host (Linux x64), bundle Chrome for Testing 155 |
| `devtools-linux` | the DevTools port (`ANNOUNCEMENT_EMULATOR_TREE=devtools`) | this host |
| `devtools-macos` | the DevTools port | a `macos-latest` GitHub runner (`tree-source-agreement.yml`, job `macos`) |
| `devtools-ubuntu-ci` | the DevTools port | an `ubuntu-latest` GitHub runner, in the same workflow run as the macOS job: **a control**, reported and used for attribution only |

Each reading is **two runs** of `corpus` with `ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1` and the source forced explicitly (never left to the default of the platform). On this host the four runs are interleaved by source
(extension, DevTools, extension, DevTools), so that a change of the pages or the network between the runs falls on both sources. The macOS and ubuntu-latest jobs each run theirs twice in one job. All the runs are made
within about two hours of the fleet captures, and the workflow run is started (by committing `ci-run.txt`) inside that window. Windows is not measured: it keeps the extension default without a figure.

## The fleet

The same captures for every reading: each of the six pages twice, on two different boxes, through `agreement/capture_fleet.py`. The boxes are chosen with a read-only `fleet:status` and `/health` readings: the largest
group that agrees on the worker's code hash, the Windows build and the browser build. They are recorded in `boxes.md` and `fleet-readings.json` with each capture's own environment. **The fleet is frozen (A11-205):
nothing on any box is changed.** The oracle's Edge may be a milestone ahead of the emulator's Chrome 155, as it was in A11-208; if so `boxes.md` says so and `oracle milestone` is a cause available below.

## The figure

For each reading, `measure.py --include-unstable --tolerate-census`, whose second block is the **headline**: **every channel, stable or not, the first fleet capture against the first passive run** (the row the Q5
write-up says to compare, because which channels are stable moves with the run). Beside it, the same with `--second` (the second capture against the second run), which is that reading's spread between two readings of the same pages.
The figure is reported by channel and by the ten commonest announcement shapes, beside the fleet against itself.

## What the extension buys

**The extension's headline minus DevTools-on-Linux's headline, in percentage points, over the units both readings compare** (the units are the same oracle strings, so a unit missing from one reading's comparable pages is left
out of both; `compare_sources.py` prints the counts). Reported overall, by channel and by shape (the ten commonest of the paired units), with the discordant units (the extension agrees and DevTools does not, and the other way round).
The noise is reported beside it: the same lead from the `--second` readings, and the difference between the two leads. The noise is reported and **does not move the rule afterwards**.
macOS and the control are not inputs: macOS takes DevTools whatever the outcome.

## The margin and the recommendation

**The margin is 1.0 percentage point.** `compare_sources.py` applies it and nothing else:

- if the extension's lead is **at most 1.0 point**, the recommendation is **to drop the extension**: one path is cheaper to keep, and what the extension buys is inside the movement of the measurement;
- otherwise the recommendation is **to keep both**, as the chairman decided (DevTools the baseline and the macOS source, the extension the default on Linux and Windows).

The margin decides **only a recommendation**. This ticket removes nothing, and the chairman reads the recommendation and decides.

**Why 1.0 point.**

1. The same extension source, run again on the same fleet captures, read 80.8% (`middleware/results/agreement/figure-4/`) and 81.4% (`figure-6/`) in A11-208: 0.6 points of movement with nothing changed but the run. A lead that is
   smaller than that cannot be told from the run.
2. On the 1,131 units of the six pages one point is about 11 units, which is less than the movement of the stop channel of the fleet against itself in the same measurement (95.2%, 19 of 393 units).
3. The ticket proposes 1 point as its example.

If this reading's own spread (the two leads) turns out to be larger than the margin, the write-up says so, and the rule is still applied as written.

## Attribution: every miss gets one cause

Each miss of each reading (the first fleet capture against the first passive run, every channel) gets **exactly one** cause from the closed list below, written into that figure's `misses.json` (`cause`, and a
`reason` where the cause is a rule's reading of the data). `compare_sources.py` assigns them **mechanically, in this order; the first that applies is the cause**:

| # | cause | applies when |
|---|---|---|
| 1 | `prompt`, `language`, `history` | `measure.py`'s `classify` names it (the image-description prompt; a language name; a `visited` token only) |
| 2 | `page moved` | the second fleet capture's list in the channel does not have the unit the first has (the two captures differ there) |
| 3 | `quick test` | the unit is the last of `stops` or `typed` of the page, nothing was predicted for it, and this reading's two passive runs differ in that channel (the last event was lost because the page closed) |
| 4 | `network/runner` | (macOS) the control predicts the string macOS predicts, and `devtools-linux` predicts another; (the control) it predicts a string other than `devtools-linux`'s |
| 5 | `macos: <field>` | (macOS) the control predicts a string other than macOS's, and `<field>` is what differs between the two |
| 6 | the cause of the same unit in `devtools-linux` | (macOS and the control) all the readings that have the unit predict the same string, so what is wrong is what is wrong on this host |
| 7 | `emulator` | (this host's two readings) both sources miss the unit |
| 8 | `conversion: <field>` | (DevTools) the extension agrees where DevTools does not, and `<field>` is what differs; `conversion: node` when DevTools predicted nothing for a list's unit |
| 9 | `events: <kind>` | (DevTools) the extension agrees where DevTools predicted nothing for a unit of `stops`, `field` or `typed`; `<kind>` is `focus` (stops, field) or `typed` |
| 10 | `tree: <field>` | (the extension) DevTools agrees where the extension does not; `tree: node` or `tree: focus` or `tree: typed` when the extension predicted nothing |
| 11 | `no counterpart` | `measure.py`'s `classify` says nothing was predicted for the unit, and no rule above applies |
| 12 | `unexplained` | anything else, with a one-line `reason` (the strings, and what the other reading said) |

`<field>` is read from the tokens (comma-separated) that differ between the predicted string and the expected one (or the other reading's), by the first pattern that matches each token:
`clickable`, `visited`, `position in set` (`N of M`), `set size` (`with N items`), `level`, `table index` (`row N`, `column N`, `row`, `column`), `landmark`, `state` (a known state word: selected, checked, not checked,
expanded, collapsed, required, invalid entry, read only, unavailable, pressed, not pressed, has auto complete, editable, opens list, sub Menu, blank), `role` (a known role word), `name` (anything else);
`order` when the same tokens come in another order. When several differ the fields are joined with `+` in alphabetical order.

Two causes can only be read from a person's look at the data, and are never assigned by the script: `oracle milestone` (the fleet's Edge is ahead of the bundle's Chrome 155, and the field is one that differs between
those milestones) and `focus match` (`unresolvedFocus` in the run's summary: the page's focused element could not be matched to a tree node). A reader may attribute a unit that is left `unexplained` or `no counterpart`
to one of them, or to any other cause of the list, in `attribution-notes.json`, each with a reason and the evidence it was read from. The notes change no figure and no count of agreed units; they are a reading of
the misses, made after the figure, and are labelled so in the write-up. **`unexplained` is counted in every table, and every one carries its one-line reason.**

## The files

`rule.md` (this), `compare_sources.py` (applies the margin, the attribution and the tables), `freeze.json` (the objects before the first capture), `boxes.md` and `fleet-readings.json` (the boxes and each capture's own date),
`passive-runs.json` (each run's dates and summary), `ci-run.txt` (the stamp that starts the macOS workflow), `figure-<reading>/` (`agreement.txt` from `measure.py`, `misses.json` with the causes),
`comparison.txt` and `comparison.json` (what `compare_sources.py` printed). The fleet's records and the passive reports are third-party pages' data and are not committed: the tables and each miss are, as in A11-208.
The macOS and control reports travel in a workflow artifact kept one day and deleted once downloaded.
