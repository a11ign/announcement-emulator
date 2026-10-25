# The boxes the structure captures were taken on (A11-229, step 2)

Read-only, from the control plane's tooling on this host: `pnpm run fleet:status` and each worker's `/health`, both at about 09:30 UTC on 2026-10-25, before the captures. **Nothing on any box was changed (A11-205).**

15 of 15 workers served `/health`. The fleet is the one step 1 found: code hash `25bb45d9b38d7a62` on 12 boxes, `47dcd71db00697b3` on `-6` and `-13`, `8f07fd23dc694ef3` on `-5`; Windows build `26300.9711` on every box but `-5`.
The captures used the same three boxes as step 1, **`a11y-worker-14`, `-15` and `-16`**, each page twice on two different boxes (`capture_fleet.py`'s plan), at 09:38 to 10:08 UTC, after the second freeze (named 09:33:30 UTC).
Each capture's own environment is in `fleet-readings.json`: all sixteen read Edge 156.0.4314.42, Windows 26300.9711, status 200.

**The oracle's Edge (156.0.4314.42) is not the browser the runs used**: both sources ran in Playwright 1.64.1's Chromium 156.0.8078.4 (the middleware runs in the team's Chromium since A11-230), the bundle holding the runtime
only. The milestone is the same as the fleet's; the build is not. `oracle milestone` is a cause available in step 1's list and no miss was given it.

A first capture round of 15 captures was taken (and discarded unread) under the first freeze `89ca720fff`, before the size limit of `rule.md`'s "The first freeze". They are not in `fleet-readings.json`.
