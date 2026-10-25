#!/bin/sh
# Build the runtime bundle for one platform (A11-208): everything the Playwright middleware needs to predict NVDA's speech, so that the user needs no Python and no NVDA. The browser is never ours: the middleware runs in the Chromium the team's Playwright installed (A11-230), so the bundle holds no browser and no browser library (check_no_browser.py fails on one).
#
#     middleware/bundle/build.sh <linux-x64|darwin-arm64> <output directory>
#
# It writes <output>/announcement-emulator-bundle-<platform>.tar.gz, its sha256, and <output>/pin-<platform>.json (what the package pins). The revisions are pins.env's. The archive is the same
# bytes for the same inputs (mktar.py), so that CI can build it twice and compare.
#
# Needs: git, curl, tar, python3, base64, a C++ compiler, and sha256sum or shasum.
set -eu
PLATFORM="${1:?platform: linux-x64 or darwin-arm64}"
OUT="${2:?output directory}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
. "$REPO/pins.env"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
W="$(mktemp -d)"; B="$W/bundle"; mkdir -p "$B"
trap 'rm -rf "${W:?}"' EXIT

sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

case "$PLATFORM" in
  linux-x64)    TRIPLE=x86_64-unknown-linux-gnu; PBS_SHA="$PBS_SHA256_LINUX_X64" ;;
  darwin-arm64) TRIPLE=aarch64-apple-darwin;     PBS_SHA="$PBS_SHA256_DARWIN_ARM64" ;;
  *) echo "no bundle for $PLATFORM" >&2; exit 2 ;;
esac

# 1. NVDA's own source at the pinned release, unmodified: the part that runs, the spy synthesizer the emulator speaks through, and the C++ the live-region rules are ported from
git clone -q --filter=blob:none --no-checkout https://github.com/nvaccess/nvda "$W/nvda"
git -C "$W/nvda" checkout -q "$NVDA_REV"
mkdir -p "$B/nvda-src"
git -C "$W/nvda" archive "$NVDA_REV" source tests/system/libraries/SystemTestSpy nvdaHelper/remote/ia2LiveRegions.cpp nvdaHelper/remote/ia2LiveRegions.h nvdaHelper/remote/textFromIAccessible.cpp | tar -x -C "$B/nvda-src"
# 2. the CLDR names, and the overlay of NVDA's source/ whose locale/en/cldr.dic is the pinned one. Copies, not links: nothing in the bundle names a path outside it
git clone -q --filter=blob:none --no-checkout https://github.com/nvaccess/nvda-cldr "$W/cldr"
git -C "$W/cldr" checkout -q "$CLDR_REV"
mkdir -p "$B/cldr-src/locale/en"; cp "$W/cldr/locale/en/cldr.dic" "$B/cldr-src/locale/en/cldr.dic"
cp -R "$B/nvda-src/source" "$B/nvda-appdir"; cp "$B/cldr-src/locale/en/cldr.dic" "$B/nvda-appdir/locale/en/cldr.dic"
# 3. Chromium's Windows accessibility mapping, as read: the source files of milestone $CHROME (source text, not a browser)
mkdir -p "$B/chromium-src"
for p in $CHROMIUM_FILES; do
  curl -fsSL "https://chromium.googlesource.com/chromium/src/+/refs/tags/$CHROME/$p?format=TEXT" | base64 -d > "$B/chromium-src/$(basename "$p")"
done
# 4. a self-contained Python, from python-build-standalone, refused unless it is the pinned build; the packages go straight into it, with no virtualenv
PBS_FILE="cpython-$PYTHON%2B$PBS_RELEASE-$TRIPLE-install_only.tar.gz"
curl -fsSL -o "$W/python.tar.gz" "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_RELEASE/$PBS_FILE"
[ "$(sha256 "$W/python.tar.gz")" = "$PBS_SHA" ] || { echo "python-build-standalone $PBS_RELEASE for $TRIPLE is not the pinned build" >&2; exit 1; }
tar -xzf "$W/python.tar.gz" -C "$B"
# fast-diff-match-patch has no wheel for 3.13 and is built here (so a C++ compiler is needed); setuptools 85 refuses its setup.cfg, so the build uses the one it was measured with
"$B/python/bin/python3" -m pip install --quiet --no-cache-dir --disable-pip-version-check "setuptools==$SETUPTOOLS" wheel
# what the build leaves in the extension it compiles (a build id, the build directory in its debug information) and in the scripts pip writes (the interpreter's absolute path) differs from one build to the next
# and from one place to the next: none is wanted, so the compiler is told to leave it out and the scripts, which nothing here runs, are removed after
export SOURCE_DATE_EPOCH=1767225600 CFLAGS="-g0 -ffile-prefix-map=$W=/build" CXXFLAGS="-g0 -ffile-prefix-map=$W=/build" LDFLAGS=""
[ "$PLATFORM" = linux-x64 ] && export LDFLAGS="-Wl,--build-id=none"      # macOS's linker has no such option (its UUID is not controlled here, so only the linux bundle is checked for reproducibility)
CC="${CC:-cc}" CXX="${CXX:-c++}" "$B/python/bin/python3" -m pip install --quiet --no-cache-dir --disable-pip-version-check --no-build-isolation $PYTHON_PACKAGES      # python-build-standalone was built with clang; the host's compiler is what is there
# the console scripts pip wrote name the interpreter by the path it was built at, and the records of what pip installed hold their hashes; neither is used
find "$B/python/bin" -type f ! -name 'python*' ! -name 'pip*' -delete
find "$B/python/lib" -path '*-info/RECORD' -delete
find "$B/python/bin" -name 'pip*' -delete      # and pip's own scripts, for the same reason
# 5. this repository's runtime: the emulator, the sweep it runs, the companion extension, and the middleware's runtime process
cd "$REPO"
git ls-files --cached --others --exclude-standard -- 'emu/*.py' emu/tables.json 'emu/ext2' emu/langnames q1/ext-id.txt q2/stubs.py q3/sweep.py q3/livepage.py q3/shapes.py q3/nvda-fleet.ini middleware/runtime LICENSE \
  | grep -Ev '^emu/(t[0-9]+|run_cases|extract_cases|gen_tables|boot_(before|objects)[a-z_]*)\.py$|__pycache__|/test_[^/]*\.py$' | tar -cf - -T - | tar -xf - -C "$B"
find "$B" -name __pycache__ -type d -prune -exec rm -rf {} +
cat > "$B/bundle.json" <<JSON
{
  "name": "announcement-emulator-bundle-$PLATFORM",
  "platform": "$PLATFORM",
  "nvda": { "release": "$NVDA_TAG", "commit": "$NVDA_REV" },
  "chromiumTables": "$CHROME",
  "python": "$PYTHON",
  "pythonBuild": "python-build-standalone $PBS_RELEASE",
  "commit": "$(git rev-parse HEAD)"
}
JSON
# 6. the archive
FILE="announcement-emulator-bundle-$PLATFORM.tar.gz"
python3 "$HERE/check_no_browser.py" "$B"      # a browser or a browser library in the bundle is a failed build
python3 "$HERE/mktar.py" "$B" "$OUT/$FILE"
SUM="$(sha256 "$OUT/$FILE")"
echo "$SUM  $FILE" > "$OUT/$FILE.sha256"
printf '{ "platform": "%s", "file": "%s", "sha256": "%s", "bytes": %s }\n' "$PLATFORM" "$FILE" "$SUM" "$(wc -c < "$OUT/$FILE" | tr -d ' ')" > "$OUT/pin-$PLATFORM.json"
echo "$FILE $SUM"
