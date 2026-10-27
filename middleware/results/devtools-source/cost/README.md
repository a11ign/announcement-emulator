# What reading the DevTools tree costs, before and after (A11-229, step 2)

The chairman's work list (the ticket's Decisions, "Step 2's stop is a work list, not a veto") ends with "DevTools's cost. Read the tree incrementally, not the whole tree at each event. Today it is 3.5 to 3.7 times slower, and pages with 700 to 1,770
tab stops produce no prediction." This is step 2 of the plan (four steps): the profile first, then the change, then the same runs on the same host.

All runs are on one host (the agents' Linux host, Playwright 1.64.1's Chromium 156.0.8078.4, two workers, `ANNOUNCEMENT_EMULATOR_TREE=devtools`, `ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1`) in one sitting, the *before* run and the *after* run of each project one
after the other: `before` is `origin/main` (7ab4945) with one line added, the profile (`AE_PROFILE=<file>` writes one line for each read of a page's tree: the round trips to the browser, the conversion, the whole read); `after` is this branch.
`summary.json` is `agreement/summarize_cost.py` over the runs' `profile.jsonl` and `run.json` (kept here); the tables below are `summarize_cost.py --table`. The pages are third-party and move, so a rerun is not the same page.

## What the profile found

**Reading the tree is not what the time of the `structure` run was made of.** Before: 27 reads of a tree took 12.6 s of the run's 407.9 s, and the predictor took 528.0 s
(`speechMs`, two workers added). A recorded walk of one page (Beaufort scale, 3,733 nodes, 150 stops) replayed under `cProfile` spent 603 of its 660 s in `emu/standin.py` `_relation_ids`, called from `_aria_details` and `_aria_error` for
every node of the tree at each focus move (441,672 calls for 131 buffers): a node that names no `details` or `errormessage` of its own was looked for in the lists of every other node. That is quadratic in the tree, and it is the emulator's, not the
tree source's, so the extension's runs paid it too; it is why the same walk took 415 to 450 s in step 2's runs and a tenth of that after.

| a buffer built from the tree of a Wikipedia page (`standin.Builder(root).build()`, no NVDA) | before | after |
|---|---|---|
| 3,733 nodes | 4.62 s | 0.09 s |
| 8,000 nodes | 20.98 s | 0.19 s |

(`origin/main`'s `emu/standin.py` and this branch's, the same node list, measured once on this host. `middleware/runtime/test_relations.py` holds the reverse relations to the scan's answers and counts the passes.)

The reads themselves were also dearer than they needed to be, and are now cheaper: a full read of the 16,657 nodes of a Wikipedia table cost 520 ms of the browser building its AX tree, 290 ms of the DOM snapshot, and 740 ms of conversion in this runtime
(the same table converts in 560 ms now); the DOM snapshot no longer asks for rects nothing reads (295 ms to 182 ms on that page).

## The change

`middleware/runtime/incremental.py` keeps, for each page, what the last full read gave, and asks the page, through a probe the listener installs, whether anything but the focus, a form control's value or an element's `title`, `class`, `style` or
`data-*` could have changed since. If not, the AX nodes that can have changed are read again (`Accessibility.getPartialAXTree`, `getChildAXNodes`) and the node list is brought up to date by `Converter.patch` instead of made again. Anything else is a
full read. Its docstring says what is read again and what is not seen; the PR body lists the decisions.

## After: the plan's measurement (the `structure` project)

| | structure-before | structure-after |
|---|---|---|
| wall time (s) | 407.9 | 85.8 |
| of it, the runtime finishing what it was told after the last test (s) | 385.2 | 65.7 |
| `speechMs`: the predictor making speech (s) | 528.0 | 66.8 |
| reads of a tree | 27 (27 full, 0 incremental) | 18 (18 full, 0 incremental) |
| sum of the reads (s) | 12.6 | 10.8 |
| of it, the round trips to the browser (s) | 7.9 | 6.5 |
| of it, the conversion (s) | 4.6 | 2.9 |
| mean full read (ms) | 466 | 598 |
| mean incremental read (ms) | - | - |
| on pages of 1000 nodes or more: incremental over full | - | - |

The structure walk is the plan's measurement. The wall time went from 407.9 s to 85.8 s and `speechMs` from 528.0 s to 66.8 s: that is the emulator's search, not the reads. **The sum of the reads fell by 14% (12.6 s to 10.8 s), not by half: the target is missed here.** The walk presses Tab as fast as Playwright can, so the runtime is told of the whole walk before it has read a page twice; all 18 reads were whole (a page load, its settling read, a mutation), the incremental path was never taken, and a whole read is a little dearer than it was (the probe, and the second read a document just come is given): 466 ms to 598 ms. The tables of the next section are where the reads are what the run is made of.

## After: the same pages at the pace of a test that waits for the page (the `paced` project)

The structure walk presses Tab as fast as Playwright can, so the runtime reads each page a few times for a hundred keys. A test that asserts after each key has the page read between nearly every key, and this is where the reads are what the run is made of.

| | paced-before | paced-after |
|---|---|---|
| wall time (s) | 198.7 | 95.2 |
| of it, the runtime finishing what it was told after the last test (s) | 126.5 | 24.0 |
| `speechMs`: the predictor making speech (s) | 243.4 | 38.5 |
| reads of a tree | 256 (256 full, 0 incremental) | 416 (126 full, 290 incremental) |
| sum of the reads (s) | 64.4 | 54.4 |
| of it, the round trips to the browser (s) | 33.0 | 23.3 |
| of it, the conversion (s) | 31.1 | 19.1 |
| mean full read (ms) | 251 | 309 |
| mean incremental read (ms) | - | 53 |
| on pages of 1000 nodes or more: incremental over full | - | 0.23 |

290 of the 416 reads were incremental (259 of them by `patch`); an incremental read took 53 ms on average against 309 ms for a whole one. On pages of 1000 nodes or more a one-node change (the focus moving) cost 79 ms against 350 ms, **0.23 of a whole read (152 incremental and 105 whole reads of such pages): the target is a quarter, and this meets it.** The run makes 416 reads where it made 256: a read that is quick does not keep the next note waiting, so the page is read as often as it changes. The predicted speech of the two runs, utterance by utterance in order, is the same for 98.6% of the utterances of `structure` and 93.7% of `paced` (the rest is where the two runs' pages moved differently; the pages are third-party). The sum of the reads fell by 16% (64.4 s to 54.4 s), not by half, though the run reads the page almost twice as often; the wall time fell from 198.7 s to 95.2 s, which is the emulator's search again (`speechMs` 243.4 s to 38.5 s).

## After: the five pages that produced no prediction (the `large` project)

Each of the five pages now has its page load and the speech of its walked stops. In the run measured: Equality Act 2010 contents 151 focus moves; Web_Content_Accessibility_Guidelines 143 focus moves; List_of_largest_cities 148 focus moves; List_of_countries_and_dependencies_by_population 149 focus moves; List_of_sovereign_states 148 focus moves. The run took 477.3 s, 457.5 s of it after the last test, and `speechMs` was 366.7 s: what is left is the emulator's, one rebuild of the NVDA buffer for each focus move, which is the length of the page. **Before, the middleware predicted nothing for these pages** (step 2's runs: no load speech, no focus event). It was not run again on them at the base: the buffer of an 8,000-node tree took 21 s to build there and the search is quadratic, so about 80 s at 16,000 nodes for each of 150 focus moves.

Two things were found with this project and are fixed here. A page of 16,000 nodes takes four seconds to read whole beside the predictor's work, and a test that walks it lasts seven: the first read began while the page was loading, gave a tree the predictor does not speak from, and the page was closed before the second read was over. In four of seven runs of the project one to three pages had no prediction. The first read of a page of 3,000 elements or more now waits for the page to load (at most 4 s), and the predictor does not start speech or a sweep while a page's first tree is being read (at most 6 s): the next three runs had all five pages in each. `tests/large` keeps the corpus walk's steps; one of its tests (the Equality Act's contents) fails at the walk's last step, as the same page does in the `structure` project at the base (`toHaveValue` on a field that is not an input), and that failure is not this ticket's.

| | large-after |
|---|---|
| wall time (s) | 477.3 |
| of it, the runtime finishing what it was told after the last test (s) | 457.5 |
| `speechMs`: the predictor making speech (s) | 366.7 |
| reads of a tree | 10 (10 full, 0 incremental) |
| sum of the reads (s) | 21.4 |
| of it, the round trips to the browser (s) | 8.7 |
| of it, the conversion (s) | 8.4 |
| mean full read (ms) | 2141 |
| mean incremental read (ms) | - |
| on pages of 1000 nodes or more: incremental over full | - |

## Why a read is whole

| why a read was whole | reads (the three runs above) |
|---|---|
| a page that keeps changing | 29 |
| layout | 27 |
| loadComplete | 17 |
| mutation | 15 |
| settling | 12 |
| first | 12 |
| a page that was read without the probe | 9 |
| a frame changed | 8 |
| an element that is gone | 7 |
| stale: the structure of the tree changed | 7 |
| stale: text is drawn where it was not | 4 |
| keyframe | 3 |
| frames | 2 |
| document | 2 |

`first`, `document` and `loadComplete` are a page that has just come; `settling` is the second whole read a document is given to see that the browser's tree has stopped changing; `layout` and `mutation` are a box, `display` or `visibility` that changed or an element, text or an attribute other than `title`, `class`, `style` and `data-*`; `a page that keeps changing` is a read made without the probe, and `a page that was read without the probe` the read after it; `a frame changed` and `frames` are a frame whose probe, or whose number, is not what it was; `an element that is gone` is a `class`, `title` or `style` change on an element that was then removed; `keyframe` is the 25th incremental read in a row; `stale: ...` is a node the reader was not told of or a tree that changed shape where it may not.

## Whether an incremental read equals a whole one (`ANNOUNCEMENT_EMULATOR_VERIFY=1`)

One sitting, the sample suite's projects one after the other, each incremental read followed by a read from scratch of the same page. These counts are from the log of that sitting, not kept as files here.

| project | incremental reads | equal to a whole read | page changed while checked (compared with nothing) | differing |
|---|---|---|---|---|
| fixtures | 18 | 12 | 6 | 0 |
| contexts | 3 | 2 | 1 | 0 |
| misses | 8 | 2 | 6 | 0 |
| fields | 3 | 3 | 0 | 0 |
| paced | 181 | 146 | 35 | 0 |
| structure | 0 | - | - | 0 |
| corpus | 3 | 1 | 2 | 0 |
| large | 0 | - | - | 0 |

216 incremental reads, 166 equal to a whole read, 50 not compared, none different. The runtime logs held `BrokenPipeError`s from `Resolution` (code that is not this step's, writing to a browser that the test had just closed). The `corpus` project's TfL test fails with and without this step (a 180 s timeout, run alone against the base bundle and this branch's); the legislation tests of `structure` fail at the base with `toHaveValue` on a field that is not an input, and `large`'s Equality Act test fails the same way at the walk's last step.

## What this step does not do

- **The 3.5 to 3.7 times between the extension and DevTools is not explained by this step.** The extension side could not be run on this host, and step 2's recorded 415 to 450 s for the walk of one page were taken on another day. What this step shows is that the emulator's search, which both sources pay, was most of the run (above); the step 4 measurement is the one to say what is left.
- **The emulator's rebuild of its NVDA buffer for each focus move** is O(nodes) and is now what the runs are made of: the `large` pages cost 0.6 to 0.9 s per stop at 16,000 to 20,000 nodes (`speechMs` above). It is outside this ticket (A11-234 is handed it), and it is why a run of the `large` project takes five minutes after its tests have ended.
- **A whole read is a little dearer** than before for the page that has just come (the probe and the second, settling read), and for a page that changes on nearly every read: it is read without the probe after four whole reads in a row.
- **What an incremental read does not see** (the look of elements outside the focus chain that a rule restyles, text a pseudo-element generates, a click listener added by script, a closed shadow tree, a node the browser makes late with no event) is in `middleware/runtime/incremental.py`'s docstring. `verify` compares everything the converter makes.
- **Snapshots are coalesced differently**: a quick read does not keep the next note waiting, so a page that changes `title`, `class`, `style` or `data-*` many times a second is read, and the predictor told, as often as that.

## To measure again

```sh
# a project with the package, the sample suite and ANNOUNCEMENT_EMULATOR_BUNDLE naming a bundle whose runtime is the one to measure
ANNOUNCEMENT_EMULATOR_TREE=devtools ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1 AE_PROFILE=$PWD/profile.jsonl npx playwright test --project=structure   # or paced, or large
cp test-results/announcement-emulator/run.json .
python3 middleware/agreement/summarize_cost.py summary.json <label>=<the directory with profile.jsonl and run.json> ...
python3 middleware/agreement/summarize_cost.py --table summary.json <label> ...
# after the large project: exits 1 and names a page that has no load speech or fewer than 100 focus moves
python3 middleware/agreement/check_predictions.py test-results/report.json middleware/sample-suite/tests/large/pages.json
```

With `ANNOUNCEMENT_EMULATOR_VERIFY=1` the runtime reads each page from scratch after every incremental read and records where the two differ (a `verify` record in the run's records, `treeReads.differing` in `run.json`).
