#!/bin/sh
# The four runs of this host's two readings, interleaved by tree source (extension, DevTools, extension, DevTools), as middleware/results/tree-source/rule.md fixes (A11-229).
#
#     middleware/agreement/run_linux_readings.sh <project> <out> [<playwright project: corpus>]
#
# `<project>` is a project with @playwright/test, the package and the sample suite, after `npx announcement-emulator install` (as .github/workflows/tree-source-agreement.yml makes one). Each run writes
# <out>/<source>-<n>/{report.json,run.json,times.json}; a run that exists is not run again. The source is forced explicitly for every run, never left to the platform's default.
# REMOVED (A11-229, step 3): this ran the companion extension as a tree source, which no longer exists; the variable it sets is ignored, so a run would file DevTools readings under the name `extension`. It stays as the record of how the readings it made were taken.
echo "run_linux_readings.sh: the extension tree source was removed (A11-229); this script is the record of the readings it made, and refuses to run" >&2; exit 2
set -u
PROJECT="${1:?the project directory}"
OUT="${2:?the output directory}"
PLAYWRIGHT_PROJECT="${3:-corpus}"      # `structure` for the table- and list-heavy pages (A11-229, step 2)
mkdir -p "$OUT"
cd "$PROJECT" || exit 2
export ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1
for step in "extension 1" "devtools 1" "extension 2" "devtools 2"; do
  set -- $step; source=$1; n=$2
  dest="$OUT/$source-$n"
  [ -f "$dest/report.json" ] && continue
  started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  ANNOUNCEMENT_EMULATOR_TREE=$source npx playwright test --project="$PLAYWRIGHT_PROJECT"
  finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  mkdir -p "$dest"
  cp test-results/report.json "$dest/report.json"
  cp test-results/announcement-emulator/run.json "$dest/run.json"
  printf '{ "reading": "%s-linux", "run": %s, "startedAt": "%s", "finishedAt": "%s" }\n' "$([ "$source" = extension ] && echo ext || echo devtools)" "$n" "$started" "$finished" > "$dest/times.json"
  rm -rf test-results playwright-report
done
