#!/bin/sh
# The package of a dry-run release installs its bundle, through the mirror variable (A11-232): the packed package is installed into a scratch project beside @playwright/test, the Release's assets are laid out as
# a mirror (<host>/v<version>/<file>) on a static server on this machine, and `npx announcement-emulator install` and `doctor` run. That is the real http download, the sum check against the packed pins.json and
# the unpack of the real bundle. Used by release-dry-run.yml on each platform, and by anyone before a merge.
#
#     middleware/release/install-check.sh <dry-run output directory> <release-files directory> <log file>
#
# <dry-run output> is what dry-run.sh wrote (the packed package and its version). PLAYWRIGHT_DEPS ("--with-deps" on Ubuntu) is passed to `npx playwright install`. Needs: node, npm, python3, curl.
set -eu
DRY="$(cd "${1:?the dry-run output directory}" && pwd)"
FILES="$(cd "${2:?the release-files directory}" && pwd)"
LOG="${3:?a log file}"; : > "$LOG"; LOG="$(cd "$(dirname "$LOG")" && pwd)/$(basename "$LOG")"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(cat "$DRY/version")"
W="$(mktemp -d)"; trap 'kill "${SERVER:-}" 2>/dev/null || true; rm -rf "${W:?}"' EXIT

mkdir -p "$W/mirror" && cp -R "$FILES/assets" "$W/mirror/v$VERSION"
PORT="${MIRROR_PORT:-$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')}"      # a free port: another job on the machine may hold 8099
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$W/mirror" >/dev/null 2>&1 & SERVER=$!
for _ in $(seq 1 50); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/v$VERSION/SHA256SUMS" && break; sleep 0.2; done
curl -sf -o /dev/null "http://127.0.0.1:$PORT/v$VERSION/SHA256SUMS" || { echo "the mirror did not start" >&2; exit 1; }

# the Playwright the package supports first, so that doctor finds its Chromium on the list
PLAYWRIGHT="$(node -p "const b=require('$REPO/middleware/supported-versions.json').builds[0]; b.playwright[b.playwright.length-1]")"
mkdir "$W/project" && cd "$W/project" && npm init -y >/dev/null
npm i -D "$DRY"/*-"$VERSION".tgz "@playwright/test@$PLAYWRIGHT" >/dev/null
npx playwright install ${PLAYWRIGHT_DEPS:-} chromium >/dev/null
export ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST="http://127.0.0.1:$PORT" ANNOUNCEMENT_EMULATOR_PATH="$W/cache"
# not a pipe to tee: the shell has no pipefail, and a failed install must fail the check
{
  echo "mirror: $ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST/v$VERSION/ (Playwright $PLAYWRIGHT)"
  npx announcement-emulator install
  npx announcement-emulator doctor
} > "$LOG" 2>&1 || { cat "$LOG"; echo "install or doctor failed" >&2; exit 1; }
cat "$LOG"
grep -q 'sha256 [0-9a-f]\{64\} matches the pin' "$LOG" || { echo "install did not check the pin" >&2; exit 1; }
