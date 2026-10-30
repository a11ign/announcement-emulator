Row A11-232, step 3 of 3: `linux-arm64` is the third platform of a release. `build.sh` has the case (python-build-standalone's `aarch64-unknown-linux-gnu` `install_only_stripped` build, refused unless it is the sum `pins.env` pins: the release's own `SHA256SUMS`), `keep/linux-arm64.txt` is the x64 list with the one extension module's platform tag, `release-bundles.yml` builds it on `ubuntu-24.04-arm` twice and requires the bytes to match, `release-dry-run.yml` installs it through the mirror variable, and `middleware-spike.yml` builds, replays (`transcripts`) and traces it on an arm runner in a pull request and in a full run, so a module the list lacks fails there. The spike has no arm `demo` row: no Playwright list is measured on arm. The arm list could not be traced on this x86_64 host; its first trace is the spike's `trace` row on the pull request.

Acceptance:

```bash
# no network and no browser; the package's own tests need `pnpm install` once
grep -q '^PBS_SHA256_LINUX_ARM64=69a30ed26198178732c37b8de0b6b5191479fbacfe526954da776befe38f18e7' pins.env
grep -q 'linux-arm64)  TRIPLE=aarch64-unknown-linux-gnu; PBS_SHA="\$PBS_SHA256_LINUX_ARM64"' middleware/bundle/build.sh
test -f middleware/bundle/keep/linux-arm64.txt
bash -c 'for f in middleware/bundle/build.sh middleware/bundle/trace.sh; do sh -n "$f"; done'
python3 -m unittest discover -s middleware/bundle -t middleware/bundle -p 'test_bundle.py'
pnpm --dir middleware install --frozen-lockfile >/dev/null
pnpm --dir middleware exec rstest run src/release-workflow.test.ts src/ci-shape.test.ts
```

The arm bundle's size, sum, reproducibility and mirror install are the run summary of `.github/workflows/release-dry-run.yml`, which a change to `.github/workflows/release*.yml` starts on the pull request; the arm `trace` and `transcripts` rows are `middleware-spike.yml`'s on the same pull request.

Mutation: removed the arm leg from `release-bundles.yml`, the arm `trace` row from the spike's `mode` job, `PBS_SHA256_LINUX_ARM64` from `pins.env` and the arm case from `build.sh`: three tests of `release-workflow.test.ts` and `ci-shape.test.ts` and four of `test_bundle.py` went red; restored, all pass. Put `sizes.py`'s `--platform` choices back to the two old platforms: the new `test_the_size_command_takes_every_platform_a_bundle_is_built_for` went red.
