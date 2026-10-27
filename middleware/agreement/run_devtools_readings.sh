#!/bin/sh
# This host's two runs of the DevTools measurement, for each of the three projects that walk its 19 pages (A11-229, step 4: middleware/results/devtools-source/rule.md).
#
#     middleware/agreement/run_devtools_readings.sh <project> <out>
#
# `<project>` is a project with @playwright/test, the package and the sample suite, after `npx announcement-emulator install` (as .github/workflows/devtools-source-agreement.yml makes one). Each run writes
# <out>/devtools-<n>/<playwright project>/{report.json,run.json,profile.jsonl,times.json}; a project of a run that exists is not run again. profile.jsonl is the runtime's profile of its tree reads (AE_PROFILE),
# which summarize_cost.py puts into the cost table; it only appends a line to a file and changes no prediction. merge_reports.py puts the three reports of a run together for measure.py.
# The DevTools port is the only tree source, so there is no source to set.
set -u
PROJECT="${1:?the project directory}"
OUT="${2:?the output directory}"
cd "$PROJECT" || exit 2
export ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1
status=0
for n in 1 2; do
  for suite in corpus structure large; do
    dest="$OUT/devtools-$n/$suite"
    [ -f "$dest/report.json" ] && continue
    rm -f "$PWD/profile.jsonl"
    started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    AE_PROFILE="$PWD/profile.jsonl" npx playwright test --project="$suite"
    finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if [ ! -f test-results/report.json ] || [ ! -f test-results/announcement-emulator/run.json ]; then
      echo "run_devtools_readings.sh: devtools-$n $suite left no report: not kept" >&2; status=1; continue
    fi
    mkdir -p "$dest"
    cp test-results/report.json "$dest/report.json"
    cp test-results/announcement-emulator/run.json "$dest/run.json"
    [ -f profile.jsonl ] && mv profile.jsonl "$dest/profile.jsonl"
    printf '{ "reading": "devtools-linux", "project": "%s", "run": %s, "startedAt": "%s", "finishedAt": "%s" }\n' "$suite" "$n" "$started" "$finished" > "$dest/times.json"
    rm -rf test-results playwright-report
  done
done
exit $status
