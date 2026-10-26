Closes A11-260

announcement-emulator CI runs only what a change needs. `middleware-spike.yml` runs for a pull request that touches the bundle's inputs, the runtime, the package or the workflow itself (not on a push, the merge queue or `main`), builds the bundle once for each platform and shares it, runs one macOS job on a pull request, and runs both platforms in full nightly, on dispatch and by call. `release-dry-run.yml` rehearses a release for a pull request that changes the release machinery, and nightly. The agreement workflows gain `workflow_dispatch`. `middleware/src/ci-shape.test.ts` holds the shape.

Acceptance:

```bash
set -eu
pnpm --dir middleware install --frozen-lockfile
# the workflow shape: concurrency that cancels a superseded pull request run, path filters, one macOS job in a pull request, one build of the bundle for each platform, the draft condition, and a gate that needs only jobs that always run
pnpm --dir middleware exec rstest run src/ci-shape.test.ts src/release-workflow.test.ts src/supported.test.ts
# the spike's mode job prints the matrices: one macOS row for a pull request, both platforms nightly (four macOS rows in the bundle, trace and demo matrices; the transcripts job reuses the bundle one)
node -e '
const { parse } = require("./middleware/node_modules/yaml"), fs = require("fs"), cp = require("child_process");
const run = parse(fs.readFileSync(".github/workflows/middleware-spike.yml", "utf8")).jobs.mode.steps[0].run;
for (const [event, macos] of [["pull_request", 1], ["schedule", 4]]) {
  const out = `${process.env.TMPDIR || "/tmp"}/mode-${event}.out`; fs.writeFileSync(out, "");
  cp.execFileSync("bash", ["-c", run], { env: { PATH: process.env.PATH, EVENT_NAME: event, GITHUB_OUTPUT: out, GITHUB_STEP_SUMMARY: "/dev/null" } });
  const rows = fs.readFileSync(out, "utf8").trim().split("\n").flatMap((l) => JSON.parse(l.slice(l.indexOf("=") + 1)).include);
  if (rows.filter((r) => r.runner.startsWith("macos")).length !== macos) throw new Error(`${event}: not ${macos} macOS rows`);
}'
( cd middleware && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
```

Measured on GitHub (the table is in the pull request): `gh api repos/a11ign/announcement-emulator/actions/runs/<id>/jobs`, the sum of each job's `completed_at` less its `started_at`, by runner label.
