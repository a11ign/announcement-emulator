# Agreement per supported Chromium build (A11-230 step 2)

Predicted speech against the fleet's NVDA, for each Chromium build the supported-versions list names, by the method of A11-229 and A11-208 (`rule.md`, frozen at 2026-10-25T07:53:20Z before the first fleet capture).
Everything here is a **measured** prediction of NVDA's speech, not evidence (ADR 0047), and **not held out**: the emulator was fitted against these six pages in A11-155 to A11-176.
It is a preview: there is no margin and no target, and every measured build is listed.

## The headline per reading

Every channel, stable or not, the first fleet capture against the first passive run (`measure.py --include-unstable --tolerate-census`, the second block). In brackets, the same with the second capture against the second run.

| Playwright | Chromium | reading | agreed | units | rate | second reading |
|---|---|---|---|---|---|---|
| 1.64.0, 1.64.1 | 156.0.8078.4 | `extension-linux` | 871 | 1072 | 81.2% | 82.4% |
| 1.64.0, 1.64.1 | 156.0.8078.4 | `devtools-linux` | 860 | 1072 | 80.2% | 80.5% |
| 1.64.0, 1.64.1 | 156.0.8078.4 | `devtools-macos` | 817 | 960 | 85.1% | 79.7% |
| 1.63.0 | 153.0.8010.12 | `extension-linux` | 895 | 1072 | 83.5% | 81.9% |
| 1.63.0 | 153.0.8010.12 | `devtools-linux` | 871 | 1072 | 81.2% | 71.1% |
| 1.63.0 | 153.0.8010.12 | `devtools-macos` | 806 | 960 | 84.0% | 82.9% |

Control (not listed): `devtools-ubuntu-ci` reads 84.0% (806 of 960) in 156 and 80.9% (777 of 960) in 153.

**Read the units before comparing rates.** The Linux readings compare five pages (1072 units). The macOS and control readings compare four (960 units): on the `macos-latest` and `ubuntu-latest` runners `tfl.gov.uk` answered
with a bot-check page ("Just a moment") instead of the journey planner, so the page is not comparable there, and `check-for-flooding.service.gov.uk` is not comparable anywhere (its title and its heading and link counts moved between the
fleet's captures and the runs). A macOS rate is therefore a rate over other units than a Linux rate, and the two are not a difference between operating systems. `comparison.txt` has the readings side by side by channel and by the ten commonest shapes,
each beside the fleet against itself.

## What the extension buys, per build

The extension's headline minus DevTools-on-Linux's, over the 1072 units both compare (reported only; this ticket applies no rule to it).

| Chromium | extension | DevTools | lead | discordant (ext only / DevTools only) | the same lead from the second readings |
|---|---|---|---|---|---|
| 156.0.8078.4 | 871 (81.2%) | 860 (80.2%) | +1.0 points | 19 / 8 | +1.8 |
| 153.0.8010.12 | 895 (83.5%) | 871 (81.2%) | +2.2 points | 28 / 4 | +10.8 |

The second readings of 153 differ widely from the first (DevTools 71.1% against 81.2%), so the movement of the measurement between two readings of the same pages is larger than either lead.

## Why the misses miss

Every miss has one cause (`misses.json` beside each `agreement.txt`); **no miss is `unexplained`**. Counts, by build and reading (`comparison.txt` has them by shape):

| reading | 156.0.8078.4 | 153.0.8010.12 |
|---|---|---|
| `extension-linux` | emulator 173, history 19, tree 8, page moved 1 | emulator 154, history 19, tree 4 |
| `devtools-linux` | emulator 173, history 19, conversion 16, page moved 4 | emulator 154, history 19, conversion 25, events 1, page moved 2 |
| `devtools-macos` | emulator 103, history 18, macos 12, conversion 7, network/runner 2, chromium build 1 | emulator 92, macos 30, history 18, conversion 7, network/runner 5, page moved 1, chromium build 1 |
| `devtools-ubuntu-ci` | emulator 112, history 18, network/runner 16, conversion 7, page moved 1 | emulator 115, network/runner 27, history 18, conversion 16, page moved 5, events 1, chromium build 1 |

Most misses are `emulator`: both tree sources, and both builds, miss the unit, so they are the emulator's and the same in either browser. The cause this ticket added, `chromium build`, applies to a unit where the two builds predict
different strings, each steadily across its own two runs: it is rare (3 misses in the eight readings: one each in the two listed macOS readings and one in the 153 control). The builds do predict another string for 53 (extension) and 25 (DevTools) of the 1072 Linux units that both compare, and the oracle agrees with exactly one
of the builds on 30 and 15 of them; most of those differences are not steady between a build's own two runs, so the rule does not call them the build's.

## The oracle's milestone

The fleet's Edge is **156.0.4314.42** (`boxes.md`): the same milestone as Playwright 1.64's Chromium 156.0.8078.4, and three behind it for 153.0.8010.12. The emulator's mapping tables are Chromium 155's. `oracle milestone` is a cause only a
reader can assign, and none was assigned: no miss was left for a reader to attribute.

## The boxes, the dates, and what was done

`boxes.md`, `fleet-readings.json` (every capture's date and environment: all between 07:57 and 08:17 UTC on 2026-10-25, after the freeze), `passive-runs.json` (the 16 runs, each with the Chromium build and the tree source its
workers reported; none fell back to another source). This host's eight runs were made between 07:54 and 08:25 UTC, interleaved by build and by source; the macOS and control runs between 07:56 and 08:04 UTC. The fleet was only read.

Three things `make_freeze.py check` names have moved since the freeze (`freeze.json` is left as it was): `middleware/src/supported.test.ts`, `middleware/agreement/compare_builds.py` and, because `middleware/src` is one of the objects, that tree
(`supported.test.ts` is in it). No agreed count, unit or cause depends on them:

- `supported.test.ts` compared a listed rate to `agreement.txt` exactly; the list keeps the rate `agreement.txt` prints (a tenth of a percent), so it now compares to within 0.0005.
- `compare_builds.py`'s `fill_list` was changed with it to write that printed rate (871 of 1072 is 81.25%, which `agreement.txt` prints as 81.2% and a naive rounding of the fraction would print as 81.3%). Its `main` was then split into named
  steps and its comparison of the two builds ordered newest first. Every file under this directory was regenerated by the final script and is byte-identical to the one made before the split.
- `.github/workflows/playwright-versions-agreement.yml` was not edited after the freeze for the measurement, but it is guarded after it (below).

The freeze, `rule.md` and `ci-run.txt` name commit `5bf6c5b8a8` of the branch; if the pull request is squash-merged, that commit is reachable only from the pull request's history.
The workflow starts on a push that touches `ci-run.txt`, and is skipped on the default branch, so merging does not run it again and leave third-party pages' predicted speech in an artifact nobody downloads.
