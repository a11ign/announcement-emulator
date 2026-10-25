# Round one of the agreement loop (A11-234 step 2)

The middleware is a **preview, improved every release, with no fixed gate** (the chairman's decision on A11-228, 2026-10-24). Each release prints its measured agreement with the fleet's NVDA by announcement type and
overall, with the population and the date; a round is judged by those figures going up; the fleet's own agreement with itself is measured as the ceiling; a prediction on a weak shape is flagged. This directory is
**round one**: the first figures the loop prints, taken on pages the emulator had not seen. **It sets no target and asks the chairman for none.**

Everything here is a **measured** prediction of NVDA's speech: advisory, never evidence (ADR 0047). Measured 2026-10-25 against captures from `a11y-worker-14`, `-15` and `-16` (Edge 156.0.4314.42, NVDA 2026.1.1; `boxes.md`).
The method is `rule.md`, frozen before the first capture (`freeze.json`, commit `f7ccc453d1`, 2026-10-25T10:43:56Z; the first capture is 10:46:52Z; `make_freeze.py check` passes).

## The figures the list prints (held-out, 2026-10-25)

Six pages the emulator and its fixes had never been run against (`held-out-pages.json`, chosen by the spike's own selection rule before the freeze). Every channel, stable or not, the first fleet capture against the first
passive run. **A listed figure is this column**, with its population and the ceiling beside it. The last column is the second capture against the second run (a check, not the figure; see "Second readings").

| Playwright | Chromium | reading | agreement | units | pages | the fleet against itself (ceiling) | second reading |
|---|---|---|---|---|---|---|---|
| 1.64.0, 1.64.1 | 156.0.8078.4 | extension, Linux | **75.0%** (785 of 1046) | 1046 | 5 of 6 | 99.9% (1045 of 1046) | 59.0% (764 of 1294) |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, Linux | **49.5%** (518 of 1046) | 1046 | 5 of 6 | 99.9% (1045 of 1046) | 57.9% (749 of 1294) |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, macOS | **72.2%** (755 of 1046) | 1046 | 5 of 6 | 99.9% (1045 of 1046) | 57.7% (746 of 1294) |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, ubuntu-latest (control, not listed) | **72.1%** (681 of 945) | 945 | 4 of 6 | 99.9% (944 of 945) | 56.8% (735 of 1294) |
| 1.63.0 | 153.0.8010.12 | extension, Linux | **75.7%** (792 of 1046) | 1046 | 5 of 6 | 99.9% (1045 of 1046) | 47.9% (474 of 989) |
| 1.63.0 | 153.0.8010.12 | DevTools, Linux | **48.7%** (509 of 1046) | 1046 | 5 of 6 | 99.9% (1045 of 1046) | 57.0% (738 of 1294) |
| 1.63.0 | 153.0.8010.12 | DevTools, macOS | **44.6%** (421 of 945) | 945 | 4 of 6 | 99.9% (944 of 945) | 78.2% (1012 of 1294) |
| 1.63.0 | 153.0.8010.12 | DevTools, ubuntu-latest (control, not listed) | **44.3%** (419 of 945) | 945 | 4 of 6 | 99.9% (944 of 945) | 57.2% (740 of 1294) |

* **The ceiling is the fleet against itself** on the same units: the first capture against the second. The fleet agrees with itself on 1045 of the 1046 units, so on these pages the oracle's own noise is not what separates
  the predictions from NVDA: **a prediction at 75% is 25 points below a ceiling of 99.9%**. A rate above the ceiling could not be told from the oracle's noise; none is near it.
* **The population is five of the six pages** on this host, four on the CI runners. `www.w3.org/WAI/tutorials/images/functional/` is not comparable in any reading: the fleet's first capture of it landed on a console window
  (`boxes.md`). On the macOS and `ubuntu-latest` runners `www.mygov.scot/scottish-child-payment` was also not comparable (the runners got a page titled "document" with no headings or links) in the 156 `ubuntu-latest` row and in both 153 rows.
  Rates over different pages are not a difference between operating systems.
* **Five pages is a small population.** The `caselaw.nationalarchives.gov.uk` page alone holds 176 of the extension's 261 misses at 156, and the Sheffield page another 58; the rate moves with a single page.
* **The 49.5% and 48.7% of DevTools on this host are one page.** 320 of the 528 misses of `devtools-linux` at 156 are on `sheffield.ac.uk/postgraduate/taught/courses/2027`, and 261 of them are `conversion: node`: the DevTools tree has no node
  for the unit (194 links, 23 headings, 14 form fields, 13 landmarks, 11 graphics, 7 lists). The same build read through DevTools on macOS and on `ubuntu-latest` has 59 misses on that page, and the extension on this host 58. At 153 all three DevTools readings
  lose the same page the same way (320 misses on it each, 261 `conversion: node`; 44.6% on macOS and 44.3% on `ubuntu-latest` over four pages). The attribution is the rule's and is not changed; **why the DevTools source loses that page's nodes on this host at 156 and on every host at 153 is not investigated this round**
  and is the first thing the next round can look at. It is a finding about one page and one tree source, listed as measured.

## Where the held-out misses are

| page | extension, Linux | DevTools, Linux | DevTools, macOS |
|---|---|---|---|
| caselaw.nationalarchives.gov.uk/search?query= | 176 | 180 | 181 |
| sheffield.ac.uk/postgraduate/taught/courses/2027 | 58 | 320 | 59 |
| www.mygov.scot/scottish-child-payment | 7 | 12 | 29 |
| www.w3.org/WAI/tutorials/forms/grouping/ | 14 | 10 | 17 |
| www.nidirect.gov.uk/information-and-services/motoring/mot-and-vehicle-testing | 6 | 6 | 5 |

Counts of misses (156.0.8078.4). The misses are not spread over the pages: **the two pages that open a cookie banner hold nine in ten of the extension's misses** (176 + 58 of 261). On both, the unit the fleet read first is the
page's own first link (caselaw: "Home Understanding case law Search and browse …"; Sheffield: "Skip to main content, link"), and the passive browser's first stop is the banner's button ("Accept cookies, button" and "Close Cookie Control, button").
The fleet's Edge (an adopted profile) evidently read the page without the banner, and Playwright's clean Chromium shows it. Stops are compared by their order, so one extra stop at the start misaligns the rest, and the form-field and link units
that follow. The closed cause list has no cause for "the passive page was in another state", so these are `emulator` (the rule's: both tree sources miss the unit). That label is true of the rule and misleading for the finding: **the next round's first
question is the consent banner, and whether the middleware should predict a page with it dismissed**. Nothing was changed against these pages (the held-out discipline).

By channel (156.0.8078.4):

| channel | extension, Linux | DevTools, Linux | DevTools, macOS | fleet against itself (extension row) |
|---|---|---|---|---|
| title | 100.0% (5/5) | 100.0% (5/5) | 100.0% (5/5) | 100.0% |
| stops | 59.0% (210/356) | 59.8% (213/356) | 58.4% (208/356) | 100.0% |
| field | 100.0% (4/4) | 75.0% (3/4) | 75.0% (3/4) | 100.0% |
| typed | 100.0% (24/24) | 100.0% (24/24) | 100.0% (24/24) | 100.0% |
| headings | 95.5% (42/44) | 43.2% (19/44) | 95.5% (42/44) | 100.0% |
| landmarks | 98.1% (52/53) | 67.9% (36/53) | 84.9% (45/53) | 100.0% |
| formFields | 42.2% (49/116) | 28.4% (33/116) | 34.5% (40/116) | 100.0% |
| graphics | 100.0% (18/18) | 38.9% (7/18) | 88.9% (16/18) | 100.0% |
| links | 89.7% (347/387) | 39.0% (151/387) | 88.6% (343/387) | 99.7% |
| lists | 87.2% (34/39) | 69.2% (27/39) | 74.4% (29/39) | 100.0% |

By shape, the ten commonest (the fleet against itself beside it; `LOW` is a low-confidence shape):

| shape (the ten commonest) | extension, Linux | DevTools, Linux | DevTools, macOS | the fleet against itself |
|---|---|---|---|---|
| NAME + ROLE + STATE + STATE | 62.6% (169/270) LOW | 61.1% (165/270) | 61.9% (167/270) LOW | 100.0% |
| NAME + ROLE | 90.2% (238/264) | 35.2% (93/264) LOW | 90.5% (239/264) | 100.0% |
| NAME + ROLE + STATE | 31.2% (25/80) LOW | 20.0% (16/80) LOW | 26.2% (21/80) LOW | 100.0% |
| NAME + ROLE + LEVEL | 97.0% (32/33) | 33.3% (11/33) | 97.0% (32/33) | 100.0% |
| NAME | 100.0% (31/31) | 100.0% (31/31) | 100.0% (31/31) | 100.0% |
| NAME + ROLE + ROLE + COUNT + NAME + ROLE | 100.0% (30/30) | 83.3% (25/30) | 93.3% (28/30) | 100.0% |
| NAME + ROLE + STATE + NAME | 69.0% (20/29) | 69.0% (20/29) | 69.0% (20/29) | 100.0% |
| NAME + STATE + ROLE | 100.0% (26/26) | 23.1% (6/26) LOW | 100.0% (26/26) | 100.0% |
| ROLE + COUNT + NAME + ROLE | 72.7% (16/22) | 72.7% (16/22) | 72.7% (16/22) | 100.0% |
| NAME + ROLE + STATE + STATE + STATE | 15.0% (3/20) LOW | 50.0% (10/20) | 20.0% (4/20) LOW | 100.0% |

## The fitted pages (not held out), against A11-230

The six pages the emulator was fitted against, measured in the same window with the same captures. **Not held out**: they overstate what a new page gets (compare 80.8% here with 75.0% above for the same reading, and the
ceilings 94.8% and 99.9%), and they are the like-for-like comparison with A11-230's figures. Movement is called within the 0.6 points of run-to-run movement `rule.md` records.

| Playwright | Chromium | reading | agreement | units | pages | ceiling | A11-230's figure (same pages) | movement | second reading |
|---|---|---|---|---|---|---|---|---|---|
| 1.64.0, 1.64.1 | 156.0.8078.4 | extension, Linux | **80.8%** (920 of 1138) | 1138 | 6 of 6 | 94.8% | 81.2% (871 of 1072) | -0.4 points: **within** | 81.6% (928 of 1137) |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, Linux | **84.6%** (963 of 1138) | 1138 | 6 of 6 | 94.8% | 80.2% (860 of 1072) | +4.4 points: **up** | 76.6% (871 of 1137) |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, macOS | **84.4%** (866 of 1026) | 1026 | 5 of 6 | 94.2% | 85.1% (817 of 960) | -0.7 points: **down** | 83.7% (858 of 1025) |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, ubuntu-latest (control, not listed) | **85.1%** (873 of 1026) | 1026 | 5 of 6 | 94.2% | 84.0% (806 of 960) | +1.1 points: **up** | 83.6% (857 of 1025) |
| 1.63.0 | 153.0.8010.12 | extension, Linux | **79.3%** (902 of 1138) | 1138 | 6 of 6 | 94.8% | 83.5% (895 of 1072) | -4.2 points: **down** | 82.1% (933 of 1137) |
| 1.63.0 | 153.0.8010.12 | DevTools, Linux | **84.3%** (959 of 1138) | 1138 | 6 of 6 | 94.8% | 81.2% (871 of 1072) | +3.0 points: **up** | 83.3% (947 of 1137) |
| 1.63.0 | 153.0.8010.12 | DevTools, macOS | **86.8%** (891 of 1026) | 1026 | 5 of 6 | 94.2% | 84.0% (806 of 960) | +2.9 points: **up** | 85.0% (871 of 1025) |
| 1.63.0 | 153.0.8010.12 | DevTools, ubuntu-latest (control, not listed) | **86.4%** (886 of 1026) | 1026 | 5 of 6 | 94.2% | 80.9% (777 of 960) | +5.4 points: **up** | 86.5% (887 of 1025) |

* **Up on DevTools**: +4.4 and +3.0 points on Linux, +2.9 (macOS, 153), +1.1 and +5.4 (`ubuntu-latest` control). These are the readings step 1 (a11ign/announcement-emulator#11: focus by DOM node, "same page", frames, the report's rates) was meant to move.
* **Within** on the extension at 156 (-0.4); **down** on the extension at 153 (-4.2) and on macOS at 156 (-0.7, 0.1 outside the band). Of the extension's 236 misses at 153, 83 are `tree`, and 75 of those are `tree: node` ("nothing predicted from the extension tree; DevTools predicted it"), 74 of them on `tfl.gov.uk`. Not investigated further this round.
* **The populations differ from A11-230's**: its Linux rows compared five pages (1072 units) and its macOS rows four (960); this round compares six (1138) and five (1026) because `check-for-flooding.service.gov.uk` was comparable this time. A movement is therefore a movement over
  different units, as well as over a different emulator; the shape rows in `round.txt` compare like shapes.
* The `NAME + ROLE + STATE + STATE + POSITION` shape, which A11-230 printed at 8.6%, reads 28.6% to 48.6%; the `NAME + ROLE + LEVEL` shape (headings) is unmoved at about 53% and is the commonest fitted-page shape that the closed list calls `emulator` (38 misses).

By channel (156.0.8078.4, fitted):

| channel | extension, Linux | DevTools, Linux | DevTools, macOS | fleet against itself (extension row) |
|---|---|---|---|---|
| title | 66.7% (4/6) | 100.0% (6/6) | 100.0% (5/5) | 100.0% |
| stops | 71.5% (283/396) | 82.8% (328/396) | 80.2% (311/388) | 92.9% |
| field | 66.7% (2/3) | 66.7% (2/3) | 50.0% (1/2) | 100.0% |
| typed | 66.7% (12/18) | 66.7% (12/18) | 100.0% (12/12) | 100.0% |
| headings | 58.5% (62/106) | 61.3% (65/106) | 57.0% (57/100) | 98.1% |
| landmarks | 97.8% (44/45) | 88.9% (40/45) | 88.9% (32/36) | 84.4% |
| formFields | 74.0% (74/100) | 73.0% (73/100) | 80.5% (70/87) | 96.0% |
| graphics | 57.1% (4/7) | 57.1% (4/7) | 75.0% (3/4) | 57.1% |
| links | 96.0% (361/376) | 94.7% (356/376) | 96.2% (307/319) | 97.3% |
| lists | 93.4% (57/61) | 93.4% (57/61) | 94.3% (50/53) | 91.8% |
| frames | 85.0% (17/20) | 100.0% (20/20) | 90.0% (18/20) | 100.0% |

By shape, the ten commonest (156.0.8078.4, fitted; the fleet against itself is over the macOS row's units):

| shape (the ten commonest) | extension, Linux | DevTools, Linux | DevTools, macOS | the fleet against itself |
|---|---|---|---|---|
| NAME + ROLE | 95.8% (275/287) | 95.5% (274/287) | 98.0% (242/247) | 98.8% |
| NAME + ROLE + STATE + STATE | 86.7% (208/240) | 99.2% (238/240) | 92.9% (221/238) | 95.8% |
| NAME + ROLE + LEVEL | 53.7% (44/82) LOW | 53.7% (44/82) LOW | 52.5% (42/80) LOW | 100.0% |
| NAME + ROLE + STATE | 59.0% (23/39) LOW | 82.1% (32/39) | 82.9% (29/35) | 77.1% |
| NAME + ROLE + STATE + STATE + POSITION | 28.6% (10/35) LOW | 45.7% (16/35) LOW | 48.6% (17/35) LOW | 100.0% |
| NAME + ROLE + STATE + STATE + STATE | 48.3% (14/29) LOW | 20.7% (6/29) LOW | 20.7% (6/29) LOW | 65.5% |
| NAME + STATE + ROLE | 88.5% (23/26) | 88.5% (23/26) | 86.4% (19/22) | 90.9% |
| NAME + NAME + ROLE | 100.0% (22/22) | 100.0% (22/22) | 100.0% (22/22) | 100.0% |
| NAME + ROLE + STATE + NAME | 23.8% (5/21) LOW | 57.1% (12/21) LOW | 75.0% (15/20) | 100.0% |
| ROLE + COUNT + NAME | 100.0% (20/20) | 100.0% (20/20) | 100.0% (19/19) | 100.0% |

## Every miss has one cause

`misses.json` beside each `agreement.txt` has every miss with its one cause and the reason that cause was chosen. The list is A11-229's, in its order, with `chromium build` (A11-230), and two causes added in this round that `rule.md` fixed
before the captures: `test blocked` (the corpus test did not pass in the reading's first run, so nothing was typed: on TfL the modal cookie dialog blocks the click on the first text field; 7 units on each Linux reading, fitted pages) and `offscreen frame`
(the extension's tree has a frame that is not drawn yet and nothing in it, DevTools has it: 3 units at 156, 1 at 153). `unexplained` is counted in every table and carries its reason: **25 units on `devtools-macos` at 156 (held-out, all on `mygov.scot`)**, each with the reason "predicts another string than this host and there is no control reading of the unit" (the control did not compare that page).

Held-out pages (counts of misses):

| cause | 156 ext, Linux | 156 DT, Linux | 156 DT, macOS | 153 ext, Linux | 153 DT, Linux | 153 DT, macOS |
|---|---|---|---|---|---|---|
| emulator | 245 | 245 | 219 | 247 | 246 | 235 |
| conversion |  | 275 | 11 |  | 286 | 281 |
| unexplained |  |  | 25 |  |  |  |
| network/runner |  |  | 19 |  |  | 1 |
| tree | 13 |  |  | 6 |  |  |
| macos |  |  | 11 |  |  | 4 |
| quick test | 3 | 3 | 3 | 1 | 2 | 2 |
| events |  | 4 | 3 |  | 1 |  |
| page moved |  | 1 |  |  | 1 | 1 |
| chromium build |  |  |  |  | 1 |  |
| **all misses** | 261 | 528 | 291 | 254 | 537 | 524 |

Fitted pages (counts of misses):

| cause | 156 ext, Linux | 156 DT, Linux | 156 DT, macOS | 153 ext, Linux | 153 DT, Linux | 153 DT, macOS |
|---|---|---|---|---|---|---|
| emulator | 107 | 107 | 72 | 118 | 117 | 80 |
| tree | 69 |  |  | 83 |  |  |
| history | 22 | 22 | 21 | 21 | 22 | 21 |
| conversion |  | 27 | 10 |  | 22 | 8 |
| page moved | 9 | 8 | 11 | 6 | 8 | 7 |
| macos |  |  | 28 |  |  | 19 |
| test blocked | 7 | 7 |  | 7 | 7 |  |
| network/runner |  |  | 18 |  |  |  |
| events |  | 4 |  |  | 3 |  |
| offscreen frame | 3 |  |  | 1 |  |  |
| chromium build | 1 |  |  |  |  |  |
| **all misses** | 218 | 175 | 160 | 236 | 179 | 135 |

`round.txt` has the causes by shape, and `rates.json` in each figure directory has them for every shape.

## Low-confidence shapes

A shape is low confidence when the upper bound of the Wilson 95% interval of its agreement is **below the reading's overall agreement**, and at least one of its misses has a cause that is not the oracle's or the test's. The flag is printed in the list
(`shapes[...].lowConfidence`) and in the report beside a prediction of that shape; the rule and its reasons are in `rule.md`. On the held-out pages:

9 of 95 shapes are low confidence (held-out, 156.0.8078.4, extension, Linux); the most misses first:

| shape | agreed / units | the fleet against itself | misses by cause |
|---|---|---|---|
| NAME + ROLE + STATE + STATE | 169 / 270 = 62.6% | 100.0% | emulator 99, quick test 2 |
| NAME + ROLE + STATE | 25 / 80 = 31.2% | 100.0% | emulator 53, tree: name 1, quick test 1 |
| NAME + ROLE + STATE + STATE + STATE | 3 / 20 = 15.0% | 100.0% | emulator 10, tree: name 7 |
| NAME + ROLE + NAME | 7 / 15 = 46.7% | 100.0% | emulator 7, tree: name+role+state 1 |
| NAME + ROLE + STATE + STATE + NAME | 2 / 8 = 25.0% | 100.0% | emulator 6 |
| NAME + ROLE + NAME + ROLE + STATE | 0 / 3 = 0.0% | 100.0% | emulator 2, tree: landmark+name+state 1 |
| ROLE + COUNT + NAME + ROLE + NAME | 0 / 3 = 0.0% | 100.0% | emulator 3 |
| NAME + ROLE + NAME + STATE + STATE | 0 / 2 = 0.0% | 100.0% | emulator 2 |
| ROLE + COUNT + NAME + NAME + NAME + ROLE | 0 / 2 = 0.0% | 100.0% | emulator 2 |

13 of 95 shapes are low confidence (held-out, 156.0.8078.4, DevTools, macOS); the most misses first:

| shape | agreed / units | the fleet against itself | misses by cause |
|---|---|---|---|
| NAME + ROLE + STATE + STATE | 167 / 270 = 61.9% | 100.0% | emulator 94, network/runner 3, events: focus 3, quick test 2, unexplained 1 |
| NAME + ROLE + STATE | 21 / 80 = 26.2% | 100.0% | emulator 51, unexplained 3, conversion: name+role+state 1, network/runner 1, macos: name+role+state 1, macos: node 1, quick test 1 |
| NAME + ROLE + STATE + STATE + STATE | 4 / 20 = 20.0% | 100.0% | emulator 9, network/runner 7 |
| NAME + ROLE + NAME | 7 / 15 = 46.7% | 100.0% | emulator 7, conversion: clickable 1 |
| NAME + ROLE + STATE + STATE + STATE + NAME + NAME | 0 / 4 = 0.0% | 100.0% | unexplained 2, network/runner 1, conversion: state 1 |
| NAME + ROLE + STATE + STATE + STATE + NAME | 0 / 3 = 0.0% | 100.0% | network/runner 2, unexplained 1 |
| ROLE + COUNT + NAME + ROLE + NAME | 0 / 3 = 0.0% | 100.0% | emulator 3 |
| NAME + ROLE + NAME + STATE + STATE | 0 / 2 = 0.0% | 100.0% | macos: name 1, macos: node 1 |
| NAME + ROLE + STATE + STATE + POSITION | 0 / 2 = 0.0% | 100.0% | conversion: position in set 1, unexplained 1 |
| ROLE + COUNT + NAME + NAME + NAME + ROLE | 0 / 2 = 0.0% | 100.0% | emulator 2 |
| ROLE + NAME + NAME + NAME + NAME + NAME + NAME + ROLE | 0 / 2 = 0.0% | 100.0% | conversion: name 1, conversion: node 1 |
| ROLE + ROLE + COUNT + NAME + ROLE + NAME + ROLE + NAME + ROLE + NAME + ROLE + NAME + ROLE + NAME | 0 / 2 = 0.0% | 100.0% | unexplained 2 |

`rates.json` has all of them. A shape that is weak only because the oracle was is not flagged, and neither is one whose misses are all the oracle's or the test's.

## Second readings

The column "second reading" is the second fleet capture against the second passive run, `agreement-second.txt` beside each `agreement.txt`. On the fitted pages it is within three points of the first for seven of the eight rows; DevTools on Linux at 156
reads 76.6% against 84.6%. **On the held-out pages the second reading is not the same measure**: it compares six pages (1294 units, the w3.org images page is a real page in the second capture) and reads 57% to 59% at 156; at 153 the extension's second
reading has two pages without a second passive reading (989 units), and DevTools on macOS reads 78.2%. The held-out figure on five pages is the rule's, and the second reading is reported so that the spread between two readings can be seen: it is wide, on five or six pages.

## What this does and does not say

* It says how often the middleware's predicted speech equals the fleet's NVDA, per unit, on these pages, on 2026-10-25, with Chromium 156.0.8078.4 and 153.0.8010.12. It does not say what a page you have not measured gets.
* Five held-out pages and a cookie banner on two of them dominate the figure; a second set of six would move it. The next round measures another six and prints both.
* The fleet runs one Edge version, 156.0.4314.42, on all fifteen workers (`/health`, read after the captures); the captures are on three of them, and three workers are off the group by Windows build or worker code and were left out (`boxes.md`).
* The extension readings are kept as the plan has them; the chairman's later A11-229 decision to drop the extension is held pending step 3 there.
* The macOS workflow was started by committing `ci-run.txt`, as A11-229 and A11-230 did; the first push also started A11-230's own workflow on this branch, which was cancelled.
* Nothing was changed on any box, and the emulator and the tooling were not changed after the freeze.

## The files

* `rule.md`, `freeze.json`, `held-out-pages.json`, `ci-run.txt`: the rule and what was fixed before the first capture.
* `boxes.md`, `fleet-readings.json`, `passive-runs.json`: where the oracle's captures and the passive runs came from.
* `<held-out|fitted>/<build>/<reading>/`: `agreement.txt` (the figure's source), `agreement-second.txt` (copied by hand from the `<reading>-second/agreement.txt` that `measure_round.sh` writes: `round.py`, frozen, does not copy it), `misses.json`, `rates.json`. `middleware/supported-versions.json` is filled from the held-out ones and `supported.test.ts` holds it to them.
* `round.txt`, `round.json`: the tables of every reading, with the movement against A11-230.
* `step-1-misses.md`: step 1's findings on the fitted pages' misses.
* Reproduce: `agreement/run_round_readings.sh` (this host), `.github/workflows/agreement-round.yml` (macOS and the control), `agreement/measure_round.sh`, then `agreement/round.py report --work <dir> --out middleware/results/agreement-round-1 --previous middleware/results/playwright-versions --list middleware/supported-versions.json --dates <build>=<day> ...`.
