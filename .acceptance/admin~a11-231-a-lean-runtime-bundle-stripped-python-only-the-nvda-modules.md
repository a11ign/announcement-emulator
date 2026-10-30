Row A11-231, step 2 of 2 (step 1, `a11ign/announcement-emulator#19`, made the bundle lean; its acceptance block is in that pull request's history). The lean runtime bundle can no longer carry a browser extension: `check_no_browser.py`, the one command `build.sh`, the `bundle` job and `release-bundles.yml` run on the bundle, now also fails on `emu/ext2/`, `q1/ext-id.txt`, a `*.crx`, a `manifest.json` that declares `manifest_version` (outside `python/`) and `middleware/runtime/fallback.py` (rules in `middleware/bundle/check_no_extension.py`). The committed keep lists were traced again against the runtime as A11-229 left it, and the README states the guard.

Acceptance (needs no network):

```bash
set -eu
d="$(mktemp -d)"; trap 'rm -rf "${d:?}"' EXIT
# the guard: an extension in a bundle directory fails the check and names the rule; without it the check passes
mkdir -p "$d/bundle/emu/ext2" "$d/bundle/python/bin"
printf '{"manifest_version": 3}' > "$d/bundle/emu/ext2/manifest.json"; : > "$d/bundle/python/bin/python3"
if python3 middleware/bundle/check_no_browser.py "$d/bundle" 2> "$d/err"; then echo "an extension passed"; exit 1; fi
grep -q 'emu/ext2/manifest.json: an extension or its switch (emu/ext2)' "$d/err"
rm -rf "${d:?}/bundle/emu"
python3 middleware/bundle/check_no_browser.py "$d/bundle" | grep -q 'no browser, no browser library and no extension'
# the tests of the guard, and of the rest of the bundle's inputs
python3 -m unittest discover -s middleware/bundle -t middleware/bundle -p 'test_*.py'
# the README states the guard
grep -q 'No browser, no browser library and no extension (`bundle/check_no_browser.py`, with `bundle/check_no_extension.py`)' middleware/README.md
```

The proofs the ticket's Done-when asks for (the size table, the identical transcripts, the reproducibility) run in CI (`.github/workflows/middleware-spike.yml`) on `ubuntu-latest` and `macos-latest`, and can be run on a Linux host with the network, in about five minutes:

```bash
set -eu
out="$(mktemp -d)"
middleware/bundle/build.sh linux-x64 "$out/bundle" --full-dir "$out/full"                    # the lean archive, and the full layout beside it
archive="$(ls "$out"/bundle/announcement-emulator-bundle-linux-x64.tar.* | grep -v '\.sha256$')"
mkdir "$out/lean" && tar -xf "$archive" -C "$out/lean"
python3 middleware/bundle/check_no_browser.py "$archive"                                     # no browser, no browser library and no extension
python3 middleware/bundle/sizes.py table "$out/lean" --platform linux-x64 --archive "$archive"   # the size, by part, against the spike's and A11-230's
python3 middleware/bundle/compare_bundles.py replay "$out/full" "$out/lean"                  # every recorded session, three ways, byte for byte (the clock left out)
middleware/bundle/build.sh linux-x64 "$out/bundle2"                                          # and again
cmp "$archive" "$out/bundle2/$(basename "$archive")"                                          # the same bytes
```
