Row A11-232, step 1 of 3: the bundles are built for a release and attached-ready, the package pins their sums, `install` downloads from the version's GitHub Release (or a mirror), a release's notes carry its measured agreement and its supported Playwright versions, and the repository can be released by the org's per-merge release workflow. Nothing is published: the package is still `private`, and `release.yml` (step 3) and the toolchain's `release-files` / `after-version` inputs (step 2) are not here yet.

Acceptance (the checks that need no network and no browser; the package's own tests need `pnpm install` once):

```bash
set -eu
# the repository is a workspace of the one package the org's release workflow releases, with a changesets config the toolchain's publish job accepts
node -e 'const c=require("./.changeset/config.json"); if (c.access !== "public") process.exit(1)'
test "$(node -p "require('./middleware/package.json').private")" = true       # still private: nothing is published until A11-233 is decided
test "$(node -p "require('./middleware/package.json').version")" = 0.0.0
node -p "require('./middleware/package.json').repository.url" | grep -q 'github.com/a11ign/announcement-emulator'
# the release scripts and the unit tests: install from a fixture release, a refused mismatch, the mirror variable, the notes, after-version.sh refusing a pin the sums lack
for f in middleware/release/*.sh; do sh -n "$f"; test -x "$f"; done
python3 -m unittest discover -s middleware/bundle -t middleware/bundle -p 'test_bundle.py'
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
```

The dry-run release itself (needs the network, about ten minutes, and a Linux host with a C++ compiler; it publishes nothing and writes only to the directories it is given). CI runs it on both platforms as `.github/workflows/release-dry-run.yml`:

```bash
set -eu
out="$(mktemp -d)"
middleware/bundle/build.sh linux-x64 "$out/first" && middleware/bundle/build.sh linux-x64 "$out/second"
cmp "$out"/first/announcement-emulator-bundle-linux-x64.tar.* "$out"/second/announcement-emulator-bundle-linux-x64.tar.*      # reproducible
mkdir "$out/legs" && cp "$out"/first/* "$out/legs/"
printf '{ "platform": "linux-x64", "reproducible": true, "required": true }\n' > "$out/legs/reproducible-linux-x64.json"
middleware/release/gather.sh "$out/legs" "$out/release-files"                            # assets/, SHA256SUMS, pins/
middleware/release/dry-run.sh "$out/release-files" "$out/dry"                             # changeset version + after-version.sh + pack, on a scratch copy
cat "$out/dry/summary.md"                                                                # every file with its size and sum, the packed pins.json, the notes
middleware/release/install-check.sh "$out/dry" "$out/release-files" "$out/install.log"   # the packed package installs the bundle through the mirror variable, and doctor finds it
rm -rf "${out:?}"
```
