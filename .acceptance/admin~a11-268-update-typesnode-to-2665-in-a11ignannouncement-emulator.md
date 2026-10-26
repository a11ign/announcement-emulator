Row A11-268: the middleware's `@types/node` dev dependency moves from 24.19.2 to 26.6.5 (`^26.6.5`), the Dependabot major of #21 re-applied on the current `main`. `engines.node` stays `>=20`. `@types/node` 26 makes `assert.equal`'s message parameter reject `undefined`, so `middleware/src/ci-shape.test.ts` reads the gate's `needs` with `?? []` (the idiom of line 181) and no longer passes a possibly-undefined job name; the test still asserts the same two needs, and that neither has an `if`.

Acceptance (needs `pnpm install` once):

```bash
set -eu
cd middleware
# the declared range, the locked version, and the unchanged Node floor
grep -q '"@types/node": "\^26.6.5"' package.json
grep -q '^  '"'"'@types/node@26.6.5'"'"':' pnpm-lock.yaml
grep -q '"node": ">=20"' package.json
pnpm install --frozen-lockfile >/dev/null
# the middleware job's steps: build, lint, types (fails on main's test file under the new types), tests
pnpm run build >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null
```
