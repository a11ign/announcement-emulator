# The boxes the tree-source captures were taken on (A11-229)

Read-only, from the control plane's tooling on this host: `pnpm run fleet:status` and each worker's `/health`, both at about 20:40 UTC on 2026-10-24, before the captures. **Nothing on any box was changed (A11-205).**

15 of 15 workers served `/health`:

- code hash `25bb45d9b38d7a62` on 12 boxes (`a11y-worker-2, -3, -4, -7, -8, -9, -10, -11, -12, -14, -15, -16`), `47dcd71db00697b3` on `-6` and `-13`, `8f07fd23dc694ef3` on `-5`;
- Windows build `26300.9711` on every box but `-5` (`22631.6199`);
- Edge `156.0.4314.42` and NVDA `2026.1.1` on the 13 boxes whose `/health` was read for them (every box but `-5` and `-6`).

The largest group that agrees on code hash, Windows build and browser is the 12 boxes of the first line. The captures used three of them, **`a11y-worker-14`, `-15` and `-16`**, each page twice on two different boxes (`capture_fleet.py`'s plan), at 20:49 to 21:09 UTC, after the freeze (named 20:46:29 UTC). Each capture's own environment is in `fleet-readings.json`: all twelve read Edge 156.0.4314.42, Windows 26300.9711.

**The oracle's Edge is one milestone ahead of the emulator's Chrome for Testing 155** (155.0.8059.84), as it was in A11-208. A figure here that is below the Gate's carries that as a candidate cause that this measurement cannot separate from the others; `oracle milestone` is a cause in `rule.md` and no miss was given it, because no miss carries evidence of a field that differs between the milestones.

The macOS and control readings ran on GitHub-hosted runners (`macos-latest`, ARM64, and `ubuntu-latest`, X64), workflow run 40131350746, at 20:49 to 20:53 UTC. Both runners were served a bot check ("Just a moment") by `tfl.gov.uk` and saw no page, so that page is not comparable in those two readings and they have five pages. Their reports were kept in a one-day workflow artifact, downloaded, and the artifacts deleted.
