# The boxes the agreement was captured on (A11-230 step 2)

`rule.md` was frozen at 2026-10-25T07:53:20Z (`freeze.json`, commit `5bf6c5b8a8`). At the read-only `pnpm run fleet:status` of 2026-10-25 ~07:48 UTC the largest group that agrees on the worker's code hash (`25bb45d9b38d7a62`),
the Windows build (`26300.9711`), the browser (Edge `156.0.4314.42`) and NVDA (`2026.1.1`) was twelve boxes (`a11y-worker-2, -3, -4, -7, -8, -9, -10, -11, -12, -14, -15, -16`). `-5` (Windows 22631), `-6` and `-13` (another code hash)
are off the group and were left out. The fleet is frozen (A11-205): nothing on any box was changed, and `fleet:status` still reports it as off its manifest. That is a finding about the manifest and not about these captures:
the three boxes used agree with each other on everything the record carries.

The captures are on `a11y-worker-14`, `-15` and `-16`, whose `/health` read the same code hash, Windows build, Edge and NVDA at 07:53 UTC, immediately before the captures. The requests are the worker's own `/capture`, from this host
(the workers answer there; the control plane was not needed). Each page's two captures are on two different boxes (`capture_fleet.py`), taken between 07:57 and 08:17 UTC; `fleet-readings.json` holds each capture's own date and environment.
Every capture is after the freeze (`make_freeze.py check --fleet`).

**The oracle's milestone.** The oracle's Edge is **156** (156.0.4314.42). The emulator's mapping tables are Chromium 155's (`pins.env`). Playwright 1.64.x's Chromium is **156.0.8078.4**: the same milestone as the oracle.
Playwright 1.63.0's Chromium is **153.0.8010.12**: three milestones behind it. The plan of A11-230 read the fleet's Edge as 155 from `pins.env`; the fleet had taken the update to 156 (as A11-229's boxes note says), so
`oracle milestone` is a candidate cause for 153 against the oracle, and not for 156.
