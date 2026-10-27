Row A11-342, announcement-emulator half: one push no longer starts two `ci` runs of a head. `ci.yml` listened to `edited` as well as `synchronize`; a worker pushes and then edits the pull request's body, so the push and the edit each started a run (a11ign/announcement-emulator#32 at `8b3d0ba9`, 2026-10-27 02:26:05: runs 40438392487 and 40438392613; the same at 02:14:30 and 02:14:46), the concurrency group `ci-<number>` cancelled one, and the cancelled `gate` held the merge of an approved, armed pull request. `edited` is removed from `ci.yml`'s `pull_request` types: nothing in the workflow reads the body.

Acceptance (no network, no browser; the package's tests need `pnpm install` once in `middleware`):

```bash
set -eu
# ci.yml starts a pull request's run on opened, synchronize and reopened only, as parsed YAML (a comment that mentions `edited` does not count)
node -e '
const { parse } = require("./middleware/node_modules/yaml");
const ci = parse(require("fs").readFileSync(".github/workflows/ci.yml", "utf8"));
const types = ci.on.pull_request.types.slice().sort().join();
if (types !== "opened,reopened,synchronize") throw new Error("ci.yml pull_request types: " + types);
if (!("merge_group" in ci.on)) throw new Error("the merge queue lost its run");
'
# and the shape test holds it, so an `edited` put back fails CI
(cd middleware && pnpm exec rstest run src/ci-shape.test.ts)
```
