Row A11-231, step 1 of 2: the runtime bundle is lean. Python is python-build-standalone's `install_only_stripped` build; the standard library ships as bytecode, and only the modules a trace of the runtime read; NVDA is one tree of the files the trace read plus `locale/en`, with the pinned CLDR names put over its own file in place (no `nvda-appdir`, no `cldr-src`); the Chromium sources are not shipped (`emu/tables.json` is); the archive is `.tar.xz` (measured against gzip and zstd), which `install` unpacks with `tar -xf`. The companion extension is still in the bundle, because the runtime still loads it (A11-229 removes it; step 2 of this ticket takes it out of the bundle after that).

Acceptance (the checks that need no network and no browser; the package's own tests need `pnpm install` once):

```bash
set -eu
# the Python is the stripped build, pinned by its own checksums, and refused before anything is unpacked when it is another file
grep -q 'install_only_stripped.tar.gz"' middleware/bundle/build.sh
test -z "$(grep -nE -- '-install_only\.tar\.gz' middleware/bundle/build.sh)"
grep -q '^PBS_SHA256_LINUX_X64=d0080766b6b74aeb81e1949ef0d9a20e6c17f7b160fb295a69b936ccb17660be$' pins.env
# the Chromium sources and the second copy of NVDA are not in the lean bundle: lean.py prunes to the keep lists, and the lists name only the two pruned parts
test -s middleware/bundle/keep/linux-x64.txt && test -s middleware/bundle/keep/darwin-arm64.txt && test -s middleware/bundle/keep/nvda-system-tests.txt
test -z "$(grep -vE '^(python|nvda-src)/' middleware/bundle/keep/linux-x64.txt middleware/bundle/keep/darwin-arm64.txt)"
# the unit tests: the pruning rules on a synthetic tree, the bytecode-only rule, one copy of NVDA, the formats (same bytes twice), the choice rule, the transcripts comparison, the miss check, the keep lists
python3 -m unittest discover -s middleware/bundle -t middleware/bundle
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_import_trace.py'
# the package: install unpacks .tar.gz, .tar.xz and .tar.zst with the host's tar
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
```

The proofs the ticket's Done-when asks for run in CI (`.github/workflows/middleware-spike.yml`) on `ubuntu-latest` and `macos-latest`, and can be run on a Linux host with the network, in about five minutes:

```bash
set -eu
out="$(mktemp -d)"
middleware/bundle/build.sh linux-x64 "$out/bundle" --full-dir "$out/full"                    # the lean archive, and the full layout beside it
archive="$(ls "$out"/bundle/announcement-emulator-bundle-linux-x64.tar.* | grep -v '\.sha256$')"
mkdir "$out/lean" && tar -xf "$archive" -C "$out/lean"
python3 middleware/bundle/sizes.py table "$out/lean" --platform linux-x64 --archive "$archive"   # the size, by part, against the spike's and A11-230's
python3 middleware/bundle/compare_bundles.py replay "$out/full" "$out/lean"                  # every recorded session, three ways, byte for byte (the clock left out)
middleware/bundle/build.sh linux-x64 "$out/bundle2"                                          # and again
cmp "$archive" "$out/bundle2/$(basename "$archive")"                                          # the same bytes
```
