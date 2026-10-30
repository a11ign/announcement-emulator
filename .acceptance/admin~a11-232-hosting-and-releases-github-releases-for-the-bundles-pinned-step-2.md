Row A11-232, step 2 of 3: `.github/workflows/release.yml` is the publish path (the org's per-merge release workflow, pinned by the full sha of the toolchain merge that added `release-files` and `after-version`), behind the one switch `"private": true`. While the package is private the workflow stops at its `plan` job and builds and publishes nothing. When it is not, `bundles` (release-bundles.yml) and `spike` (middleware-spike.yml, full mode) must pass before `release` publishes under the dist-tag `preview` with the bundles attached. Nothing is published: the package is still `private`. `linux-arm64` is step 3.

Acceptance:

```bash
# no network and no browser; the package's own tests need `pnpm install` once
set -eu
test "$(node -p "require('./middleware/package.json').private")" = true       # still private: release.yml is a dry run
node -e 'const c=require("./.changeset/config.json"); if (c.access !== "public") process.exit(1)'   # the toolchain's publish job re-checks it
test "$(node -p "require('./middleware/package.json').version")" = 0.0.0
node -p "require('./middleware/package.json').repository.url" | grep -q 'github.com/a11ign/announcement-emulator'
for f in middleware/release/*.sh; do sh -n "$f"; test -x "$f"; done
python3 -m unittest discover -s middleware/bundle -t middleware/bundle -p 'test_bundle.py'
grep -Eq 'uses: a11ign/toolchain/.github/workflows/release-per-merge.yml@[0-9a-f]{40}$' .github/workflows/release.yml
grep -q 'dist-tag: preview' .github/workflows/release.yml
pnpm --dir middleware install --frozen-lockfile >/dev/null
pnpm --dir middleware exec dependabot-config --check --root ..
pnpm --dir middleware exec rstest run src/release-workflow.test.ts src/ci-shape.test.ts
```

The dry run of the bundles, the sums and the mirror install is `.github/workflows/release-dry-run.yml`, which a change to `.github/workflows/release*.yml` starts on the pull request; its run summary lists every asset with its size and sum.
