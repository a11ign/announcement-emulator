---
"@a11ign/foresay": patch
---

A release also carries a `linux-arm64` runtime bundle, built on GitHub's arm runners from python-build-standalone's aarch64 build (pinned in `pins.env`), checked for a browser, built twice and compared like the x64 one, pinned in `pins.json`, and installed through the mirror variable in the dry run. `npx foresay install` on an arm64 Linux machine now finds a bundle to download.
