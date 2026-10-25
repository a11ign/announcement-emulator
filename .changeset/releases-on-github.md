---
"@a11ign/announcement-emulator": minor
---

`install` downloads the runtime bundle from the GitHub Release of the package's version (`<repository>/releases/download/v<version>/`), checks it against the sha256 `pins.json` names, and takes a mirror from `ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST` (`<host>/v<version>/<file>`). The package is releasable by the org's per-merge release workflow, and a release's notes carry its measured agreement and its supported Playwright versions. The package stays private, so nothing is published.
