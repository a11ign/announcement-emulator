A11-353. Records the chairman's three release decisions in `docs/release-decisions.md` (the name Foresay, licence option A, NV Access Move) and applies them: the middleware package is `@a11ign/foresay`, Apache-2.0, with a `LICENSE` and a `NOTICE`; the runtime bundle declares `GPL-3.0-or-later` and ships the GPL text and a `NOTICES` file; a test proves the packed tarball holds no file of the runtime; the READMEs use the §1 wording. The package stays private (nothing is published). ADR 0047 is amended in the `a11ign` pull request.

Acceptance (needs no network; `pnpm install` in `middleware/` first):

```bash
set -eu
d=docs/release-decisions.md
# the decisions are recorded
decisions="$(awk '/^## Decisions/{f=1;next} /^## 1\./{f=0} f' "$d")"
printf '%s\n' "$decisions" | grep -q '@a11ign/foresay'
printf '%s\n' "$decisions" | grep -q 'Option A'
printf '%s\n' "$decisions" | grep -q '\*\*Move\*\*'
printf '%s\n' "$decisions" | grep -q 'first non-preview release'
# the package: name, licence, files
cd middleware
test "$(node -p "require('./package.json').name")" = "@a11ign/foresay"
test "$(node -p "require('./package.json').license")" = "Apache-2.0"
test "$(node -p "require('./package.json').private")" = "true"
grep -q 'Apache License' LICENSE && test -f NOTICE
npm pack --dry-run --json --ignore-scripts | node -e '
  const files = JSON.parse(require("fs").readFileSync(0, "utf8"))[0].files.map((f) => f.path);
  for (const must of ["LICENSE", "NOTICE", "package.json"]) if (!files.includes(must)) throw new Error("missing " + must);
  const bad = files.filter((f) => /^(runtime|bundle|emu|q[123])\//.test(f) || /\.pyc?$/.test(f));
  if (bad.length) throw new Error("runtime files in the tarball: " + bad);'
# the runtime bundle: licence declared, notices shipped
grep -q '"license": "GPL-3.0-or-later"' bundle/build.sh
grep -q 'cp "$HERE/NOTICES" "$B/NOTICES"' bundle/build.sh
grep -q 'GPL-3.0-or-later' bundle/NOTICES
# the tests that prove it
pnpm exec rstest run src/package-files.test.ts
cd .. && python3 -m unittest discover -s middleware/bundle -t middleware/bundle
```
