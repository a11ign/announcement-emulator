#!/bin/sh
# A dry-run release (A11-232): everything a release does after the bundles are built, on a scratch copy of the working tree, publishing and pushing nothing. Used by release-dry-run.yml, and by anyone before a merge.
#
#     middleware/release/dry-run.sh <release-files directory> <output directory>
#
# <release-files> is the `release-files` artifact of release-bundles.yml (assets/, pins/, report/). In the scratch copy it runs what the release's `version` job runs: `changeset version`, then
# middleware/release/after-version.sh, which writes pins.json and the measured agreement into the changelog entry. It then packs the package as `npm publish` would, and checks that the packed pins.json names the
# same sums as SHA256SUMS. The working tree is never written: the pending changesets stay pending.
#
# Writes to <output>: the packed package (a11ign-announcement-emulator-<version>.tgz), pins.json and notes.md as packed, SHA256SUMS, version, and summary.md (every file with its size and sum, the reproducibility of each
# platform, the pins and the notes), which the workflow shows in the pull request's checks.
# Needs: git, tar, node, pnpm (the repository's packageManager), sha256sum.
set -eu
FILES="$(cd "${1:?the release-files directory}" && pwd)"
mkdir -p "${2:?an output directory}"; OUT="$(cd "$2" && pwd)"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "${W:?}"' EXIT

# what a reviewer reads: every file with its size and sum, the reproducibility of each platform, the package as packed, its pins.json and the notes
summary() {
  echo "## Dry-run release $VERSION"; echo
  echo "Nothing was published, tagged or pushed. This is the release of this branch's changesets on a scratch copy of the working tree."; echo
  echo "### Files the Release would carry"; echo
  echo "| file | bytes | sha256 |"; echo "| --- | --- | --- |"
  for f in "$FILES"/assets/announcement-emulator-bundle-*; do
    case "$f" in *.sha256) continue ;; esac
    echo "| $(basename "$f") | $(wc -c < "$f" | tr -d ' ') | \`$(sha256sum "$f" | cut -d' ' -f1)\` |"
  done
  echo; echo "SHA256SUMS as attached:"; echo '```'; cat "$FILES/assets/SHA256SUMS"; echo '```'; echo
  echo "### Reproducibility (the bundle built twice, compared byte for byte)"; echo
  for f in "$FILES"/report/reproducible-*.json; do node -e 'const r=require(process.argv[1]); console.log(`- ${r.platform}: ${r.reproducible ? "identical" : "DIFFERENT"} (${r.required ? "required" : "reported, not required"})`)' "$f"; done; echo
  echo "### The packed package: $(basename "$PACKED") ($(wc -c < "$PACKED" | tr -d ' ') bytes)"; echo; echo '```'; tar -tzvf "$PACKED" | awk '{print $3, $6}'; echo '```'; echo
  echo "pins.json as packed:"; echo '```json'; cat "$OUT/pins.json"; echo '```'; echo
  echo "### The Release's notes (the changelog entry)"; echo; sed -n "/^## $VERSION\$/,/^## [0-9]/p" "$OUT/CHANGELOG.md" | sed '$ { /^## [0-9]/d }'
}

# the working tree as a repository of its own: `changeset version` reads git, and writes files
git -C "$REPO" ls-files -z --cached --others --exclude-standard | tar --null --ignore-failed-read -cf - -C "$REPO" -T - | tar -xf - -C "$W"
cd "$W"
git init -q -b main && git add -A && git -c user.name=dry-run -c user.email=dry-run@invalid commit -qm "the working tree"
pnpm install --frozen-lockfile >/dev/null
# a release needs a changeset; with none pending the rehearsal brings one, so that there is a version to pin
if ! ls .changeset/*.md 2>/dev/null | grep -qv '/README\.md$'; then
  printf -- '---\n"%s": patch\n---\n\nA rehearsal: no changeset is pending.\n' "$(node -p "require('./middleware/package.json').name")" > .changeset/dry-run.md
  git add -A && git -c user.name=dry-run -c user.email=dry-run@invalid commit -qm "a rehearsal changeset"
fi
pnpm exec changeset version
VERSION="$(node -p "require('./middleware/package.json').version")"
RELEASE_FILES="$FILES" sh middleware/release/after-version.sh

rm -f "$OUT"/*.tgz; (cd middleware && pnpm pack --pack-destination "$OUT" >/dev/null)
PACKED="$(ls "$OUT"/*-"$VERSION".tgz)"
tar -xzOf "$PACKED" package/pins.json > "$OUT/pins.json"
tar -xzOf "$PACKED" package/CHANGELOG.md 2>/dev/null > "$OUT/CHANGELOG.md" || sed -n "/^## $VERSION\$/,\$p" middleware/CHANGELOG.md > "$OUT/CHANGELOG.md"
cp "$FILES/assets/SHA256SUMS" "$OUT/SHA256SUMS"; echo "$VERSION" > "$OUT/version"
# the packed package names exactly the sums the Release will list: every bundle pinned, every pin a bundle
node -e 'const p=require(process.argv[1]); console.log(Object.values(p.bundles).map((b)=>`${b.sha256}  ${b.file}`).sort().join("\n"))' "$OUT/pins.json" > "$W/pinned.txt"
sort "$FILES/assets/SHA256SUMS" | diff - "$W/pinned.txt" || { echo "the packed pins.json and SHA256SUMS name different sums" >&2; exit 1; }
node -e 'const p=require(process.argv[1]); if (p.version !== process.argv[2]) { console.error(`pins.json is for ${p.version}, the package is ${process.argv[2]}`); process.exit(1) }' "$OUT/pins.json" "$VERSION"

summary > "$OUT/summary.md"
echo "dry run of $VERSION: $PACKED; summary in $OUT/summary.md"
