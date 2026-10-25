#!/bin/sh
# Lays the legs of release-bundles.yml out as the `release-files` artifact (A11-232), the contract between the bundles, the release workflow's `release-files` input and middleware/release/after-version.sh:
#
#     assets/announcement-emulator-bundle-<platform>.tar.<format>[.sha256]    what the Release carries
#     assets/SHA256SUMS                                                       every bundle, as `sha256sum` writes it
#     pins/pin-<platform>.json                                                what build.sh wrote: { platform, file, sha256, bytes }
#     report/reproducible-<platform>.json                                     the two builds compared (not attached to the Release)
#
#     middleware/release/gather.sh <directory with every leg's files> <release-files directory>
#
# It fails when a bundle has no pin, a pin has no bundle, or a sum is not the file's.
set -eu
LEGS="$(cd "${1:?the legs directory}" && pwd)"
mkdir -p "${2:?the release-files directory}"; OUT="$(cd "$2" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT/assets" "$OUT/pins" "$OUT/report"
cp "$LEGS"/announcement-emulator-bundle-* "$OUT/assets/"
cp "$LEGS"/pin-*.json "$OUT/pins/"
cp "$LEGS"/reproducible-*.json "$OUT/report/"
cd "$OUT/assets"
ls announcement-emulator-bundle-*.tar.* | grep -v '\.sha256$' | sort | xargs sha256sum > SHA256SUMS
sha256sum -c SHA256SUMS
# every pin is one of the sums, and every bundle is pinned
node "$HERE/../bundle/write-pins.mjs" gather --sums SHA256SUMS "$OUT"/pins/pin-*.json > /dev/null
[ "$(ls "$OUT"/pins | wc -l)" -eq "$(wc -l < SHA256SUMS)" ] || { echo "the bundles and the pins are not the same set" >&2; exit 1; }
cat SHA256SUMS
