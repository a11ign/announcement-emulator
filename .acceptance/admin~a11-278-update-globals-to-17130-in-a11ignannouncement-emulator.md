Row A11-278: the middleware's `globals` dev dependency moves from 16.5.0 to 17.13.0 (`^17.13.0`), the Dependabot major of #22 re-applied on the current `main`. `middleware/eslint.config.mjs` is unchanged: `globals.node` still applies to every `.ts`/`.mjs` file and `globals.browser` to the two `agreement/dom_check*.mjs` files (globals 17 only splits `audioWorklet` out of `browser`).

Acceptance (needs `pnpm install` once):

```bash
set -eu
cd middleware
# the declared range and the locked version
grep -q '"globals": "\^17.13.0"' package.json
grep -q '^  globals@17.13.0:' pnpm-lock.yaml
pnpm install --frozen-lockfile >/dev/null
# the middleware job's steps: lint (a new no-undef would fail here), types, tests
pnpm run lint && pnpm run typecheck && pnpm test >/dev/null
# the config still gives the two dom_check files both environments, and every other file node only
resolved() { pnpm exec eslint --print-config "$1" | node -e 'const g=JSON.parse(require("fs").readFileSync(0)).languageOptions.globals; console.log("document="+("document" in g)+" process="+("process" in g))'; }
test "$(resolved agreement/dom_check.mjs)" = "document=true process=true"
test "$(resolved agreement/dom_check_structure.mjs)" = "document=true process=true"
test "$(resolved src/install.ts)" = "document=false process=true"
```
