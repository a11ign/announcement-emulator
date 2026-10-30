#!/bin/sh
# Decide what the lean bundle keeps (A11-231): run the runtime over everything it is meant to do, with import_trace.py on, and write what it read to keep/<platform>.txt.
#
#     middleware/bundle/trace.sh <linux-x64|darwin-arm64> [--full-dir <dir>] [--traces <dir>] [--no-live]
#     middleware/bundle/trace.sh --system-tests <EMU_DOWNLOADS of setup.sh's layout>          (linux; rewrites keep/nvda-system-tests.txt)
#
# The runs, all in the FULL layout (build.sh --layout-only: what a run could read, nothing pruned):
#   * every recorded session under middleware/runtime/fixtures, recursively, through replay.py: with sweeps, without, and with --report-focus;
#   * the sample suite's offline project (middleware/sample-suite, `fixtures`), live, in Playwright's Chromium, with ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1 (--no-live skips it);
#   * NVDA's Chrome system tests as the emulator runs them (emu/run_cases.py), whose NVDA paths are keep/nvda-system-tests.txt. They need setup.sh's layout (a Chrome and the libraries it needs), so
#     they run on linux, with --system-tests, and their list is committed; every platform's keep list takes it in.
# The corpus and structure projects of the sample suite load live third-party pages and are not run.
#
# PLAYWRIGHT_DEPS=--with-deps installs the browser's system libraries too (Ubuntu runners). --traces keeps the raw traces in <dir> (CI uploads them); keep/<platform>.txt is made from them by keep.py. Commit the result: the lean bundle is built from it, and compare_bundles.py misses fails CI
# on anything a later change makes the runtime read that the list lacks.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SYSTEM_TESTS_LIST="$HERE/keep/nvda-system-tests.txt"

if [ "${1:-}" = "--system-tests" ]; then
  DEV="$(cd "${2:?the downloads directory of setup.sh}" && pwd)"
  T="$(mktemp -d)"; trap 'rm -rf "${T:?}"' EXIT
  mkdir -p "$T/site"
  printf 'import import_trace\nimport_trace.install()\n' > "$T/site/sitecustomize.py"      # every Python process of the run, run_cases.py's one for each test as well
  ( cd "$REPO/emu" && ANNOUNCEMENT_EMULATOR_IMPORT_TRACE="$T/system-tests.txt" EMU_DOWNLOADS="$DEV" PYTHONPATH="$T/site:$REPO/middleware/runtime" "$DEV/q2/venv/bin/python" run_cases.py ) | tail -3
  mkdir -p "$HERE/keep"
  python3 "$HERE/keep.py" "$SYSTEM_TESTS_LIST" --only nvda-src/ "$T/system-tests.txt"
  echo "$SYSTEM_TESTS_LIST: $(wc -l < "$SYSTEM_TESTS_LIST" | tr -d ' ') files"
  exit 0
fi

PLATFORM="${1:?platform: linux-x64 or darwin-arm64}"; shift
FULL_DIR=""; TRACES=""; LIVE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --full-dir) FULL_DIR="${2:?a directory}"; shift 2 ;;
    --traces) TRACES="${2:?a directory}"; shift 2 ;;
    --no-live) LIVE=""; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
W="$(mktemp -d)"; trap 'rm -rf "${W:?}"' EXIT
[ -n "$TRACES" ] || TRACES="$W/traces"
mkdir -p "$TRACES"; TRACES="$(cd "$TRACES" && pwd)"
if [ -z "$FULL_DIR" ]; then FULL_DIR="$W/full"; "$HERE/build.sh" "$PLATFORM" "$W/out" --full-dir "$FULL_DIR" --layout-only; fi
FULL="$(cd "$FULL_DIR" && pwd)"

# 1. every recorded session, as replay.py runs it
python3 "$HERE/compare_bundles.py" replay "$FULL" --trace "$TRACES/replay.txt"

# 2. the sample suite's offline project, live: the package as a team installs it, Playwright's own Chromium, the full layout as the bundle
if [ -n "$LIVE" ]; then
  ( cd "$REPO/middleware" && pnpm install --frozen-lockfile && pnpm run build && npm pack --pack-destination "$W" ) >/dev/null
  cp -R "$REPO/middleware/sample-suite" "$W/project"
  ( cd "$W/project" && npm i -D --silent "$W"/a11ign-foresay-*.tgz "@playwright/test@$(node -p "require('$REPO/middleware/package.json').devDependencies['@playwright/test']")" && npx playwright install ${PLAYWRIGHT_DEPS:-} chromium )      # PLAYWRIGHT_DEPS=--with-deps on a runner that lacks the browser's system libraries
  ( cd "$W/project" && rm -rf test-results && ANNOUNCEMENT_EMULATOR_BUNDLE="$FULL" ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1 ANNOUNCEMENT_EMULATOR_IMPORT_TRACE="$TRACES/live.txt" \
      npx playwright test --project=fixtures ) || echo "the sample suite did not pass: its trace is kept all the same" >&2
fi

# 3. the list: what the runs read, and what NVDA's own system tests read
mkdir -p "$HERE/keep"
python3 "$HERE/keep.py" "$HERE/keep/$PLATFORM.txt" --layout "$FULL" --also "$SYSTEM_TESTS_LIST" "$TRACES"/*.txt
echo "$HERE/keep/$PLATFORM.txt: $(wc -l < "$HERE/keep/$PLATFORM.txt" | tr -d ' ') files"
