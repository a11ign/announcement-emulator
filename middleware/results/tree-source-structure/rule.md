# The structure measurement: the rule, fixed before the first fleet capture of A11-229's second step

The chairman read step 1 (`middleware/results/tree-source/`, announcement-emulator#13) on 2026-10-25: the extension led DevTools by +0.7 points (82.1% against 81.4%), inside the 1.0-point margin. Before the extension is
removed, one safeguard: step 1's six pages are light on tables and long lists, which is where the extension's extra fields (table indices, set positions) could matter. This measurement runs both sources on
table- and list-heavy real pages and asks whether the extension still leads by no more than the margin.

This file, `candidates.json`, `pages.json`, `select_structure_pages.py`, `dom_check_structure.mjs`, `compare_sources.py` and the objects `freeze.json` names are committed, and `freeze.json` names their git objects, before
any page is captured on the fleet for this step. `agreement/make_freeze.py check freeze.json` fails if any of them has moved since, or if a fleet capture is dated before the freeze.

## What is adopted unchanged

The rule of step 1 (`middleware/results/tree-source/rule.md`), which adopts the Q5 rule of A11-208 (`middleware/results/agreement/rule.md`): the corpus test's walk (Tab until focus comes round, at most 150 stops, Escape twice, type
into the first text field), the channels, units, shapes and matching of `measure.py`, the fleet route (`q3/fleet_capture.mjs --typing-dialog` through `agreement/capture_fleet.py`), the headline figure (every channel, stable
or not, the first fleet capture against the first passive run, `--include-unstable --tolerate-census`), the closed list of causes and the order they are assigned in, and the 1.0-point margin. The only things that differ are
the pages (below), the sample suite's project (`structure`, whose test is the corpus test from its constants on, held equal by `test_structure_walk.py`), and the decision the numbers feed (below). Everything measured here
is *measured* and **not held out**: the emulator has never been fitted to these pages, but it was fitted to the kinds of page the fleet's corpus holds.

## Which pages

`agreement/select_structure_pages.py`, run once on `candidates.json`, gave `pages.json`:

1. The candidates are the 37 addresses of `candidates.json`, named by hand: public pages of the shapes the chairman listed (data tables with headers, long navigation lists, nested lists, a grid, a tree view). The list was
   widened once, after a first look at their DOM counts (no accessibility tree, no fleet record, no emulator and no figure was looked at), because the first pass found data tables with links in their cells only on Wikipedia.
   It was widened a second time after the first freeze (below). It is fixed from here. The six pages of step 1 are left out if they appear.
2. They are put in the order of the SHA-256 of their address, read as a number (the order `select_pages.py` used).
3. Each in turn is opened in a browser (Playwright's Chromium) and its DOM counted, and nothing else (`agreement/dom_check_structure.mjs`). A page with **more than 500 tab stops** is left out (see the first freeze, below). Otherwise it is a **table page** with at least 3 header cells (`th`, `columnheader`,
   `rowheader`), one table (`table`, `grid`, `treegrid`) of at least 40 cells and at least 20 tab stops inside table cells; otherwise a **list page** with at least 20 tab stops inside list items (`li`, `listitem`,
   `treeitem`, `option`, `menuitem`) and a list of at least 20 items or at least 3 nested lists.
4. The first four table pages and the first four list pages are the sample: eight pages. The candidates that failed and those left over are listed in `pages.json` with the reason.

## The first freeze, and why it was replaced

The rule was first frozen at `89ca720fff` (2026-10-25 08:50:50 UTC) without a limit on the size of a page, and its eight pages included four Wikipedia tables of 963 to 1,770 tab stops and the Equality Act 2010's contents (705).
On the first extension run of the four interleaved ones, the middleware predicted **nothing** for those five pages (no load speech and no focus event; the other three pages had 56, 150 and 27 utterances), and a DevTools run
of the small listbox page alone waited 69 s at its end for 59 focus events, so that the same run on pages of that size would have taken hours. Sixteen fleet captures of that sample had been started (fifteen taken) and were
discarded unread. Nothing was compared: no figure, no agreement and no miss of any reading had been computed. The size limit is a limit of what the middleware can predict at all, and it was chosen after seeing that, so
it is stated here; the sample is the first four table pages and the first four list pages of the same ordering under the limit. The pages of the first freeze that remain in the sample are the listbox, Outline of
computer science and the Human Rights Act's contents. The first freeze stays in git history; `freeze.json` is the second.

**What the channels can and cannot see.** The walk presses Tab, so a grid or tree that moves focus with the arrow keys (one tab stop, a roving tabindex) is entered once and not walked: the four APG pages show it (1 to 7 tab stops in
cells). The structure sweep's lists (`headings`, `landmarks`, `formFields`, `graphics`, `links`, `lists`, `frames`) have no table channel. A table index or a set position reaches a figure through a Tab stop inside a cell or an
item (the focus phrase) and through the `lists` channel. The write-up says how many units carry such a token in the oracle's string; this measurement does not add a channel.

## The readings

| reading | tree source | where it runs |
|---|---|---|
| `ext-linux` | the extension (`ANNOUNCEMENT_EMULATOR_TREE=extension`) | this host (Linux x64), in Playwright 1.64.1's Chromium |
| `devtools-linux` | the DevTools port (`ANNOUNCEMENT_EMULATOR_TREE=devtools`) | this host |

Each is **two runs** of the `structure` project with `ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1` and the source forced explicitly, interleaved by source (extension, DevTools, extension, DevTools) by
`agreement/run_linux_readings.sh <project> <out> structure`, within about two hours of the fleet captures. The bundle is built from the freeze commit (`middleware/bundle/build.sh linux-x64`) and the package packed from it.
macOS and a control are **not** run: macOS takes DevTools whatever this measurement finds, and the question here is what the extension buys over it. Windows is not measured.

## The fleet

Each page twice, on two different boxes, through `agreement/capture_fleet.py`, read-only: the boxes are chosen with `pnpm run fleet:status` and each worker's `/health`, the largest group that agrees on the worker's code hash, the
Windows build and the browser build. They are recorded in `boxes.md` and `fleet-readings.json`. **The fleet is frozen (A11-205): nothing on any box is changed.** The oracle's Edge may be a milestone ahead of the
browser the runs use; `boxes.md` says so, and `oracle milestone` is a cause available in step 1's list.

## The figure and the decision

For each reading, `measure.py --include-unstable --tolerate-census`, whose second block is the headline, and the same with `--second`. `compare_sources.py --classes pages.json` reports, over the units both readings
compare: the extension's headline minus DevTools's, overall, by channel, by the ten commonest shapes, and **by class of page** (table, list), with the discordant units and every miss attributed to one cause of step 1's list.

**The gate.** Step 3 (remove the extension) goes on only if the extension's lead is **at most 1.0 percentage point overall and at most 1.0 point on each class of page**. Otherwise step 3 stops and reports: the
`conversion:` and `events:` misses of DevTools (the work list `compare_sources.py` prints) name the fields and kinds that make the difference, so that they can be added to DevTools. The gate is applied as written; the
`--second` leads (the spread between two readings of the same pages) are printed beside it and do not move it. A class of page has few units, so a stop on one class alone is possible by chance, and the write-up says so if it
happens; the rule is still applied as written, and the chairman reads it.

Why each class and not only the whole: the whole is dominated by the channels both sources agree on, and a field the extension fills and DevTools does not could hide there. Why 1.0 point: step 1's rule.md (the same
extension source read 80.8% and 81.4% on the same captures in A11-208, and one point is about the movement of the fleet against itself in its least stable channel).

## Attribution

As in step 1: every miss gets exactly one cause from the closed list, in the order given there, written into `figure-<reading>/misses.json`; `unexplained` carries a one-line reason and is counted. A reader's
`attribution-notes.json` may give a cause to a unit left `unexplained` or `no counterpart`; it changes no figure.

## The files

`rule.md` (this), `candidates.json`, `pages.json` (the sample, with the class and the DOM counts), `freeze.json`, `boxes.md` and `fleet-readings.json`, `passive-runs.json`, `figure-<reading>/` (`agreement.txt`, `misses.json`),
`comparison.txt` and `comparison.json`. The fleet's records and the passive reports are third-party pages' data and are not committed: the tables and each miss are, as in A11-208.
