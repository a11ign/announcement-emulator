Refs A11-279 (step 6 of 7)

The announcement-emulator's middleware tests no longer write to `/tmp`. They left about 100 `ae-*` folders there on every run (about 15,000 on the agents host, which had 19,960 entries in `/tmp` when a 26 s ext4 directory read stalled and the host panicked, 2026-10-25). `middleware/test-setup/private-tmp.mjs` is rstest's `globalSetup`: it makes one short `ae-run-XXXXXX` directory under `A11Y_PRIVATE_TMP_BASE` (else `~/.cache/a11ign/tmp`), points `TMPDIR` at it before the workers fork, and removes it at the end, so every `tmpdir()` in the tests lands there with no test edited. `emu/session.mjs` puts its Chrome profile and the extension copy under `tmpdir()` and removes both when the session ends (also on SIGINT and SIGTERM), and the three `emu/boot*.py` entry points remove their `nvda-cfg-*` directory at exit.

Acceptance:

```bash
set -eu
cd middleware && pnpm install --frozen-lockfile && cd ..
stamp=$(mktemp) && sleep 1
n0=$(ls /tmp | wc -l)
# the new test: the run's TMPDIR is the private directory, tmpdir() lands in it, makeRunTmp and removeRunTmp, and the refusal of anything not ae-run-*
(cd middleware && pnpm exec rstest run test-setup)
# the whole middleware suite passes under the setup, and leaves nothing of its own in /tmp (it left ~100 ae-* folders before)
(cd middleware && pnpm test && pnpm run typecheck && pnpm run lint)
n1=$(ls /tmp | wc -l); test "$n1" -le "$n0"   # /tmp does not grow (it grew by ~100 entries per run before)
test -z "$(find /tmp -maxdepth 1 -newer "$stamp" \( -name 'ae-*' -o -name 'emu-profile-*' -o -name 'nvda-cfg-*' \))"
test -z "$(ls ~/.cache/a11ign/tmp 2>/dev/null | grep '^ae-run-' || true)"   # the run's directory is removed at the end
# the emulator's own entry points
test -z "$(grep -n "'/tmp" emu/session.mjs || true)"
grep -n "tmpdir()" emu/session.mjs
test "$(grep -c 'atexit.register(shutil.rmtree' emu/boot.py emu/boot_before_objects.py emu/boot_objects_try.py | grep -c ':1$')" = 3
```
