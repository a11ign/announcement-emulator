# The boxes the agreement was captured on, and what changed under the rule

`rule.md` named `a11y-worker-13`, `-14` and `-16`: at the read-only `pnpm run fleet:status` of 2026-10-24 ~14:30 UTC they were the three boxes on Edge 155.0.4283.62 and Windows 26300.9711 (the emulator's milestone), code hash `25bb45d9b38d7a62`.
Two things had changed by the time the captures were taken (15:40 to 16:08 UTC), neither of them this ticket's doing, and the fleet is frozen (A11-205), so nothing was converged:

1. `a11y-worker-13` read code hash `47dcd71db00697b3` (as `-5` and `-6` had), so it was left out. The captures are on `a11y-worker-14` and `-16`, which agree on the code hash, Windows build and browser.
2. **Edge on those boxes was 156.0.4314.42, not 155.** Each capture's own record says so (`fleet-readings.json`), and `fleet:status` no longer reports a browser difference across the fleet: the three Edge 155 boxes had taken the update to 156.
   So the oracle is one Edge milestone ahead of the emulator's Chrome 155 (the Gate's was the same milestone). Where a number here is lower than the Gate's, that is a candidate cause that this measurement cannot separate from the others.

Each page's two captures are on the two boxes. The requests are the worker's own `/capture`.
