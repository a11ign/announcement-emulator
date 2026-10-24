Row A11-230, step 1 of 2: the Playwright middleware runs in the Chromium the team's Playwright installed. It downloads no browser and bundles none. `supported-versions.json` ships in the package (empty until step 2 measures each build), a report says `agreement not measured for Chromium <build>` for any build that is not listed, `doctor` reports the team's Playwright and Chromium and whether the build is listed, and the sample suite runs on plain `ubuntu-latest` and `macos-latest` runners with only Playwright's own Chromium installed (the `demo` job of `.github/workflows/middleware-spike.yml`, one row for each of Playwright 1.64.1 and 1.63.0 on both, and 1.62.1, which is unlisted, on Ubuntu). The measurement of each build and the list's entries are step 2.

Acceptance (the checks that need no network, no fleet and no browser; the package's own tests need `pnpm install` once):

```bash
set -eu
# the launch names no browser of the bundle's and no library path (middleware/src/config.test.ts holds the launch options to it), and the bundle's layout has no chrome and no libs
test -z "$(grep -nE 'LD_LIBRARY_PATH|files\.(chrome|libs)' middleware/src/config.ts)"
test -z "$(grep -nE '^\s+(chrome|libs):' middleware/src/bundle.ts)"
# the bundle build downloads no browser and no libraries for one, and refuses an archive that holds one
test -z "$(grep -nE 'chrome-for-testing|CFT_DIR|apt-get download|dpkg-deb' middleware/bundle/build.sh)"
grep -q 'check_no_browser.py' middleware/bundle/build.sh
grep -q '"chromiumTables": "\$CHROME"' middleware/bundle/build.sh
# the list ships in the package, with the schema the test holds it to
grep -q '"supported-versions.json"' middleware/package.json
test -f middleware/supported-versions.json
# the sample suite uses no variable that pointed at the bundle's browser
test -z "$(git grep -nE 'BASELINE_CHROME|BASELINE_LIBS' -- middleware .github)"
# the demo job installs only Playwright's browser, for each listed version and one unlisted version
grep -q 'npx playwright install \${{ matrix.deps }} chromium' .github/workflows/middleware-spike.yml
for v in 1.64.1 1.63.0 1.62.1; do grep -q "playwright: \"$v\"" .github/workflows/middleware-spike.yml; done
# the package: lint, types, tests (a supported version's wording, an unsupported version's wording, doctor, the launch options, the tree pick)
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
# the Python tests: the browser's build reaches the report, and the bundle holds no browser
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_cdp.py'
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_fallback.py'
python3 -m unittest discover -s middleware/bundle -t middleware/bundle
```

On a runner with the bundle built (CI does this, and this is the pre-merge proof of "no browser in the bundle" on the real archives): `python3 middleware/bundle/check_no_browser.py <archive>.tar.gz` prints `no browser and no browser library`.
