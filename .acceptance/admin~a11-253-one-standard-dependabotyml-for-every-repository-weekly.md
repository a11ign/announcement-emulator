Refs A11-253

Step 2 of 2 (announcement-emulator): `.github/dependabot.yml` is now the output of `dependabot-config --write` from `@a11ign/toolchain` 0.11.0 (0.10.2 before), not a hand-written file. Every ecosystem runs weekly on Monday at 05:23 UTC, patch and minor updates share one `<ecosystem>-minor-and-patch` group so a major is its own pull request, and the packages frozen by policy are ignored in the npm entry. This repository had no Dependabot config before, so both ecosystems are new here; the npm entry points at `/middleware` through `.github/dependabot-extra.json`, and the `middleware` job of `ci.yml` runs the drift check.

Acceptance:

```bash
(cd middleware && pnpm install --frozen-lockfile)
# the committed file is exactly the template's output (exit 1 and a diff on drift)
(cd middleware && pnpm exec dependabot-config --check --root ..)
# weekly at one fixed time, one group per ecosystem
test "$(grep -c 'interval: weekly' .github/dependabot.yml)" = 2
test "$(grep -c 'time: "05:23"' .github/dependabot.yml)" = 2
grep -q 'npm-minor-and-patch:' .github/dependabot.yml
grep -q 'github-actions-minor-and-patch:' .github/dependabot.yml
# every package frozen by policy is ignored
for name in @a11ign/screenreader-worker @a11ign/screenreader-fleet @guidepup/guidepup @guidepup/setup; do grep -qF "dependency-name: \"$name\"" .github/dependabot.yml; done
```
