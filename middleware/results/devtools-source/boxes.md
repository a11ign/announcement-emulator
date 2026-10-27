# The boxes the captures were taken on (A11-229, step 4)

Read-only, through the fleet job route (`python3 middleware/agreement/capture_fleet.py … --boxes ready --label A11-229`, a fleet job on the control plane that books its boxes). **Nothing on any box was changed (A11-205).**

**The job that is read: `fj-20261027T102953Z-0d28ec`**, submitted 2026-10-27 10:29:53 UTC, finished 10:59:25, 38 of 38 captures, none failed or skipped, after the second freeze (`freeze.json`, 09:56:33 UTC). The 19 pages twice, on two different boxes each.
Its manifest says the boxes agree on every version (`agreement.consistent: true`, 12 boxes compared): worker code `25bb45d9b38d7a62`, Windows `26300.9711`, Edge `156.0.4314.42`, NVDA `2026.1.1`.
The twelve: `a11y-worker-2`, `-3`, `-4`, `-7`, `-8`, `-9`, `-10`, `-11`, `-12`, `-14`, `-15`, `-16`. Each capture's own environment is in `fleet-readings.json`: all 38 read status 200, Edge 156.0.4314.42, Windows 26300.9711, captured 10:32:46 to 10:59:25 UTC.

**The oracle's Edge (156.0.4314.42) is not the browser the runs used**: all 18 passive runs (three projects, two runs, three readings) report Playwright 1.64.1's Chromium 156.0.8078.4 in `run.json` (`passive-runs.json`), the same milestone (156) and not the same build.
`oracle milestone` is a cause of the closed list and no miss was given it.

**Two jobs that are not read.**

1. `fj-20261027T092551Z-24f958`, under the first freeze (`eaf063acdb`): it took four captures on `a11y-worker-5`, whose Windows is 22631 where the other boxes are 26300.9711, so `capture_fleet.py collect` refused to write any record. Never read.
2. `fj-20261027T095256Z-3e3c96`, submitted 09:52:56, cancelled at 15 of 38 captures, before the second freeze was committed (09:56:33). Its records were not collected and never read.

**When the readings were taken, against the captures (10:32 to 10:59 UTC).** The runtime the freeze names is the same git object in both freezes (`rule.md`, "The first freeze, and why it was replaced").

| reading | taken | against the captures |
|---|---|---|
| `devtools-linux` (this host) | 09:26 to 09:55 UTC | 37 to 66 minutes before the first capture |
| `devtools-macos`, `devtools-ubuntu-ci` | started 10:29:57 UTC by `ci-run.txt`, finished about 10:55 | inside the capture window |

All of them are within the two hours of the fleet captures the rule asks for.
