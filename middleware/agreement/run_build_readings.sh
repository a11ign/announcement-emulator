#!/bin/sh
# This host's four passive runs of A11-230 step 2, interleaved by build, as middleware/results/playwright-versions/rule.md fixes: DevTools 156, DevTools 153, then the same two again.
# (The rule's eight runs also had the companion extension, which A11-229 removed: the DevTools port is the only tree source, and there is no source to choose.)
#
#     middleware/agreement/run_build_readings.sh <out> <build>=<project> <build>=<project> ...
#
# e.g. run_build_readings.sh /x/linux 156.0.8078.4=/x/p1641 153.0.8010.12=/x/p1630. Each `<project>` is a project with its own @playwright/test, the package and the sample suite, after
# `npx playwright install chromium` and `npx announcement-emulator install` (as .github/workflows/playwright-versions-agreement.yml makes one). Each run writes
# <out>/<build>/devtools-<n>/{report.json,run.json,times.json}; a run that exists is not run again.
# A run whose workers report another Chromium build than its row names is not kept: it is a reading of another row.
set -u
OUT="${1:?the output directory}"; shift
[ "$#" -ge 1 ] || { echo "run_build_readings.sh: at least one <build>=<project>" >&2; exit 2; }
mkdir -p "$OUT"
export ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1
status=0
for n in 1 2; do
  for spec in "$@"; do
    build="${spec%%=*}"; project="${spec#*=}"
    dest="$OUT/$build/devtools-$n"
    [ -f "$dest/report.json" ] && continue
    cd "$project" || exit 2
    started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    npx playwright test --project=corpus
    finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if ! node -e 'const w = JSON.parse(require("fs").readFileSync("test-results/announcement-emulator/run.json", "utf8")).workers; process.exit(w.length && w.every((x) => x.startup?.chromium === process.argv[1]) ? 0 : 1)' "$build"; then
      echo "run_build_readings.sh: devtools-$n of $build ran in another Chromium build (or none): not kept" >&2
      status=1; rm -rf test-results playwright-report; continue
    fi
    mkdir -p "$dest"
    cp test-results/report.json "$dest/report.json"
    cp test-results/announcement-emulator/run.json "$dest/run.json"
    printf '{ "reading": "devtools-linux", "chromium": "%s", "run": %s, "startedAt": "%s", "finishedAt": "%s" }\n' "$build" "$n" "$started" "$finished" > "$dest/times.json"
    rm -rf test-results playwright-report
  done
done
exit $status
