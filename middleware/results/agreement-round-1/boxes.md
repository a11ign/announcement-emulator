# The boxes the agreement was captured on (A11-234 step 2, round one)

`rule.md` was frozen at 2026-10-25T10:43:56Z (`freeze.json`, commit `f7ccc453d1`). The fleet captures are dated 2026-10-25T10:46:52Z to 2026-10-25T11:25:32Z (`fleet-readings.json`, each with its own date and
environment): every one is after the freeze (`make_freeze.py check --fleet`: "nothing the figure is made by has moved since f7ccc453d1, and every fleet capture is after the freeze").

**The boxes.** The read-only `pnpm run fleet:status` of 2026-10-25 (read after the captures; the fleet is frozen, A11-205, and nothing on any box was changed) reports the same three groups as A11-230 step 2 did:
twelve boxes on the worker code hash `25bb45d9b38d7a62` (`a11y-worker-2, -3, -4, -7, -8, -9, -10, -11, -12, -14, -15, -16`), `-5` on another code hash and Windows 22631, and `-6` and `-13` on a third.
The captures are on **`a11y-worker-14`, `-15` and `-16`**, which are in the largest group (the same three boxes A11-230 used). `fleet:status` still reports the fleet as off its manifest ("fleet SPLIT: 3 different code hashes",
"INCONSISTENT" on Windows 22631 against 26300 and on the display adapter); that is a finding about the manifest and not about these captures, which carry their own record of what they ran on:

| | |
|---|---|
| captures | 24 (12 pages × 2), 8 on each of `a11y-worker-14`, `-15`, `-16`; each page's two captures are on two different boxes (`capture_fleet.py`) |
| Edge (`browserVersion`) | **156.0.4314.42** on all 24 |
| Windows | Microsoft Windows 11 Pro 10.0.26300, build 26300.9711 on all 24 |
| NVDA | 2026.1.1 on all 24 |
| worker code | `25bb45d9b38d7a62` on all 24 |

**Does the fleet now run one Edge version?** Yes. A read-only GET of `/health` on all fifteen workers on 2026-10-25 (after the captures; the same channel `fleet:status` uses, nothing sent to a box) reads Edge **156.0.4314.42** on every one,
including the three off the group (`-5`, `-6`, `-13`), and NVDA 2026.1.1 on every one. The fleet is still not one image: `-5` is on Windows 22631.6199 and worker code `8f07fd23dc694ef3`, `-6` and `-13` on worker code `47dcd71db00697b3`.
Those three were left out, not converged. (A11-183 and A11-205 asked whether the fleet runs one Edge version; for Edge it does.)

**The oracle's milestone.** The oracle's Edge is **156**. Playwright 1.64.x's Chromium is **156.0.8078.4**: the same milestone. Playwright 1.63.0's Chromium is **153.0.8010.12**: three milestones behind it, so `oracle milestone`
is a candidate cause for 153 against the oracle and not for 156 (`round.py` applies it only to a unit left `unexplained` or `no counterpart` in `attribution-notes.json`; no reader's notes were written this round, so it is applied to none).

**The pages.** The twelve pages were each captured twice. One capture is not usable: the first capture of `www.w3.org/WAI/tutorials/images/functional/` landed on a console window (its title reads
"c windows system 32 cmd exe", 2 lines of speech), so the page is not the same on both sides and is not counted in any reading (5 of 6 held-out pages). No capture was repeated: the rule fixes one pair per page, and a
re-capture after the figures are seen would be a choice made against them. The other pages that a reading does not count (TfL behind a "just a moment" check on the macOS and `ubuntu-latest` runners, and one more
held-out page, `mygov.scot`, on the `ubuntu-latest` rows and the 153 macOS row) are named in each `agreement.txt` under "not comparable".

**The passive runs.** `passive-runs.json` holds each of the 32 runs (16 on this host, 8 on macOS, 8 on `ubuntu-latest`): its reading, set, Chromium build, tree source and why, start and end, and the number of tests and flags.
This host's run order is `run_round_readings.sh`'s. The macOS and `ubuntu-latest` jobs are workflow run 40185994994 (2026-10-25T10:44:16Z to 10:58:04Z, both jobs succeeded); their artifacts were downloaded and deleted, and
only the tables and each miss are committed.
