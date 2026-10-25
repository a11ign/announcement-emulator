#!/bin/sh
# The `after-version` command of the release (A11-232, ADR 0001 of that ticket): a11ign/toolchain's release-per-merge.yml runs it in the `version` job, in the repository root, after `changeset version` has moved
# middleware/package.json to the release's version and before the release commit is made. Whatever it writes is in the commit that is tagged and published: so the sums the package pins are the sums of the bundles
# attached to that version's Release, and the Release's notes (the changelog entry) carry the measured agreement.
#
#     RELEASE_FILES=<the downloaded `release-files` artifact> sh middleware/release/after-version.sh
#
# $RELEASE_FILES holds assets/ (the bundles and SHA256SUMS), which release-bundles.yml builds, and pins/ (a pin-<platform>.json for each bundle, which middleware/bundle/build.sh writes).
# It holds a credential for nothing and runs in a job with `contents: read`; a non-zero exit fails the job before any commit, so nothing is tagged or published.
set -eu
: "${RELEASE_FILES:?RELEASE_FILES: the directory of the release-files artifact}"
cd "$(dirname "$0")/../.."
[ -f "$RELEASE_FILES/assets/SHA256SUMS" ] || { echo "$RELEASE_FILES/assets/SHA256SUMS does not exist: no bundle was built" >&2; exit 1; }
ls "$RELEASE_FILES"/pins/pin-*.json >/dev/null 2>&1 || { echo "$RELEASE_FILES/pins has no pin-<platform>.json" >&2; exit 1; }
VERSION="$(node -p "require('./middleware/package.json').version")"
trap 'rm -f middleware/pins.json.new' EXIT
# 1. pins.json names the bundles of this release; a pin whose sum is not the one SHA256SUMS lists for that file is an error, and pins.json is left as it was
node middleware/bundle/write-pins.mjs "$VERSION" --sums "$RELEASE_FILES/assets/SHA256SUMS" "$RELEASE_FILES"/pins/pin-*.json > middleware/pins.json.new
mv middleware/pins.json.new middleware/pins.json
# 2. the measured agreement and the supported Playwright versions, in the changelog entry that becomes the notes
node middleware/src/release-notes.ts "$VERSION"
echo "pinned $VERSION: $(node -p "Object.keys(require('./middleware/pins.json').bundles).join(', ')")"
