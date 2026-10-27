#!/bin/sh
# This host's passive runs of A11-234 round one, interleaved by page set, tree source and build, as middleware/results/agreement-round-1/rule.md fixes:
# for each of two rounds, for the held-out pages and then the fitted ones: extension 156, extension 153, DevTools 156, DevTools 153.
#
#     middleware/agreement/run_round_readings.sh <out> <held-out pages.json> <fitted pages.json> <build>=<project> <build>=<project> ...
#
# e.g. run_round_readings.sh /x/linux held-out-pages.json pages.json 156.0.8078.4=/x/p1641 153.0.8010.12=/x/p1630. Each `<project>` is a project with its own @playwright/test, the package and the sample suite, after
# `npx playwright install chromium` and `npx announcement-emulator install` (as .github/workflows/agreement-round.yml makes one). Each run writes
# <out>/<set>/<build>/<source>-<n>/{report.json,run.json,times.json}; a run that exists is not run again. The source is forced explicitly for every run, never left to the platform's default, and the corpus test
# reads its pages from CORPUS_PAGES. A run whose workers report another Chromium build than its row names is not kept: it is a reading of another row.
# REMOVED (A11-229, step 3): this ran the companion extension as a tree source, which no longer exists; the variable it sets is ignored, so a run would file DevTools readings under the name `extension`. It stays as the record of how the readings it made were taken.
echo "run_round_readings.sh: the extension tree source was removed (A11-229); this script is the record of the readings it made, and refuses to run" >&2; exit 2
set -u
OUT="${1:?the output directory}"; HELD_OUT="${2:?the held-out pages file}"; FITTED="${3:?the fitted pages file}"; shift 3
[ "$#" -ge 1 ] || { echo "run_round_readings.sh: at least one <build>=<project>" >&2; exit 2; }
HELD_OUT="$(cd "$(dirname "$HELD_OUT")" && pwd)/$(basename "$HELD_OUT")"; FITTED="$(cd "$(dirname "$FITTED")" && pwd)/$(basename "$FITTED")"
START="$(pwd)"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
export ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1
status=0
for n in 1 2; do
  for set in held-out fitted; do
    case "$set" in held-out) pages="$HELD_OUT" ;; fitted) pages="$FITTED" ;; esac
    for source in extension devtools; do
      for spec in "$@"; do
        build="${spec%%=*}"; project="${spec#*=}"
        dest="$OUT/$set/$build/$source-$n"
        [ -f "$dest/report.json" ] && continue
        project="$(cd "$START" && cd "$project" && pwd)" || exit 2
        cd "$project" || exit 2
        started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        CORPUS_PAGES="$pages" ANNOUNCEMENT_EMULATOR_TREE=$source npx playwright test --project=corpus
        finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        if ! node -e 'const w = JSON.parse(require("fs").readFileSync("test-results/announcement-emulator/run.json", "utf8")).workers; process.exit(w.length && w.every((x) => x.startup?.chromium === process.argv[1]) ? 0 : 1)' "$build"; then
          echo "run_round_readings.sh: $set $source-$n of $build ran in another Chromium build (or none): not kept" >&2
          status=1; rm -rf test-results playwright-report; continue
        fi
        mkdir -p "$dest"
        cp test-results/report.json "$dest/report.json"
        cp test-results/announcement-emulator/run.json "$dest/run.json"
        printf '{ "reading": "%s-linux", "set": "%s", "chromium": "%s", "run": %s, "startedAt": "%s", "finishedAt": "%s" }\n' "$source" "$set" "$build" "$n" "$started" "$finished" > "$dest/times.json"
        rm -rf test-results playwright-report
      done
    done
  done
done
exit $status
