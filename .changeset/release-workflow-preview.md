---
"@a11ign/foresay": patch
---

A push to `main` releases the package through the org's per-merge release workflow (`.github/workflows/release.yml`): the bundles are built twice and compared, the full spike runs, the sums are pinned in the release commit, and the package is published to npm by trusted publishing under the dist-tag `preview`, with the bundles and `SHA256SUMS` attached to the GitHub Release. While the package is `"private": true` the workflow stops at its first job with a dry-run message and nothing is built or published. The README says what a release does and what the npm side needs. Dependabot also watches the root workspace's `@changesets/cli`.
