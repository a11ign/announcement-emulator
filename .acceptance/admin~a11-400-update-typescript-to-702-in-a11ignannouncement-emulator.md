A11-400: the middleware's `typescript` moves from 6.0.3 to 7.0.2 (supersedes Dependabot's #42, which left `middleware/pnpm-lock.yaml` on 6.0.3, so `pnpm install --frozen-lockfile` failed). `tsc` and the Rslib declaration build run on 7.0.2. `typescript-eslint` has no TypeScript 7 support (it declares `typescript <6.1.0`, and 7.0.2 ships no compiler API at its main entry; typescript-eslint#12518, #10940), so `.pnpmfile.cjs` gives it a TypeScript 6.0.3 of its own beside the 7, and lint keeps running with no rule, file or job turned off. `exports` named `dist/*.d.mts`, which Rslib has never written for this package (it writes `.d.ts`, and the declarations import `./x.js`); `exports` now names the `.d.ts` files that are built.

Acceptance (no network, no browser; needs `pnpm install --frozen-lockfile` once in `middleware`):

```bash
set -eu
cd middleware
# both installs read the same pnpmfile, so the frozen install passes from the package and from the root
pnpm install --frozen-lockfile
(cd .. && pnpm install --frozen-lockfile)
# tsc reports 7.0.2
pnpm exec tsc --version | grep -x 'Version 7.0.2'
# lint, typecheck and the declaration build pass on TypeScript 7
pnpm run lint
pnpm run typecheck
pnpm run build
# every file `exports` names is in dist
node -e '
const { existsSync } = require("fs");
const exp = require("./package.json").exports;
const targets = Object.values(exp).flatMap((e) => typeof e === "string" ? [e] : Object.values(e));
const missing = targets.filter((t) => !existsSync(t));
if (missing.length) throw new Error("missing: " + missing);
'
# typescript-eslint runs on its own TypeScript 6, and the tests hold all of it
pnpm exec rstest run src/typescript-seven.test.ts
```
