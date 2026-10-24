A11-237. announcement-emulator gets the org's standard merge flow: `.github/workflows/ci.yml` with the required `gate` job (the middleware's build, lint, typecheck and rstest suite, and the Python suites that run without the fleet), `.github/workflows/auto-arm.yml` with its Octo STS policy `.github/chainguard/auto-arm.sts.yaml` (`workflows: write`, A11-203), and the exact `merge-queue-main` ruleset in `.github/rulesets/merge-queue-main.json`, which the chairman applies (the workers' App has no admin here). Nothing here releases.

Acceptance (run from the branch's checkout; needs `jq` and `python3` with PyYAML; the last line needs the pull request number in `$PR` and network):

```bash
set -eu
r=.github/rulesets/merge-queue-main.json
jq -e . "$r" >/dev/null
# the ruleset: exactly these five rules, one approving review, `gate` required from GitHub Actions (15368), no bypass
test "$(jq -c '[.rules[].type]|sort' "$r")" = '["deletion","merge_queue","non_fast_forward","pull_request","required_status_checks"]'
test "$(jq '.rules[]|select(.type=="pull_request").parameters.required_approving_review_count' "$r")" = 1
test "$(jq -c '.rules[]|select(.type=="required_status_checks").parameters.required_status_checks' "$r")" = '[{"context":"gate","integration_id":15368}]'
test "$(jq -c .bypass_actors "$r")" = '[]'
test "$(jq -r .enforcement "$r")" = active
test "$(jq -c .conditions.ref_name.include "$r")" = '["refs/heads/main"]'
# the arm bot's policy: this repository's immutable ids, bound to main's copy, with workflows: write
p=.github/chainguard/auto-arm.sts.yaml
grep -q '^subject_pattern: repo:a11ign@320310787/announcement-emulator@1423581964:' "$p"
grep -q '^  workflows: write$' "$p"
grep -q 'auto-arm\\.yml@refs/heads/main' "$p"
# the three files parse, and ci.yml's gate waits for both jobs and runs on the merge queue
python3 - <<'PY'
import yaml
for f in (".github/workflows/ci.yml", ".github/workflows/auto-arm.yml", ".github/chainguard/auto-arm.sts.yaml"):
    yaml.safe_load(open(f))
ci = yaml.safe_load(open(".github/workflows/ci.yml"))
on = ci.get("on", ci.get(True))
assert "merge_group" in on and "pull_request" in on
assert sorted(ci["jobs"]["gate"]["needs"]) == ["middleware", "python"]
PY
# `gate` is green on the pull request
gh pr checks "$PR" --repo a11ign/announcement-emulator | grep -E '^gate\s+pass'
```

Measured on the pull request's first `ci` run (2026-10-24): `middleware` passed in 24 s, `python` in 23 s and `gate` in 4 s. On a plain runner every Python directory ran and none was left out; the suites that need NVDA's source, the emulator's virtualenv, Chrome or the fleet skip themselves with their reason.
