Row A11-230, step 2 of 2: each supported Chromium build has a measured agreement rate, and `middleware/supported-versions.json` lists it. Playwright 1.64.0/1.64.1 (Chromium 156.0.8078.4) and Playwright 1.63.0 (Chromium 153.0.8010.12) are measured by A11-229's method for the extension on Linux, DevTools on Linux and DevTools on macOS, against the fleet's NVDA (rule: `middleware/results/playwright-versions/rule.md`, frozen before the first fleet capture; write-up: `middleware/results/playwright-versions/README.md`). The CI rows for those two versions now expect the measured sentence, and the unlisted Playwright 1.62.1 keeps the "agreement not measured for Chromium <build>" wording.

Acceptance (the checks that need no network, no fleet and no browser; the package's own tests need `pnpm install` once):

```bash
set -eu
# step 1 still holds: the launch names no browser of the bundle's and no library path, and the bundle's layout has no chrome and no libs
test -z "$(grep -nE 'LD_LIBRARY_PATH|files\.(chrome|libs)' middleware/src/config.ts)"
test -z "$(grep -nE '^\s+(chrome|libs):' middleware/src/bundle.ts)"
# the bundle build downloads no browser and no libraries for one, and refuses an archive that holds one
test -z "$(grep -nE 'chrome-for-testing|CFT_DIR|apt-get download|dpkg-deb' middleware/bundle/build.sh)"
grep -q 'check_no_browser.py' middleware/bundle/build.sh
grep -q '"supported-versions.json"' middleware/package.json
test -z "$(git grep -nE 'BASELINE_CHROME|BASELINE_LIBS' -- middleware .github)"
grep -q 'npx playwright install \${{ matrix.deps }} chromium' .github/workflows/middleware-spike.yml
for v in 1.64.1 1.63.0 1.62.1; do grep -q "playwright: \"$v\"" .github/workflows/middleware-spike.yml; done
# both builds are listed, each with the three readings, and each figure is in the repository
node -e '
const l = require("./middleware/supported-versions.json");
const want = { "156.0.8078.4": ["1.64.0", "1.64.1"], "153.0.8010.12": ["1.63.0"] };
for (const [build, pw] of Object.entries(want)) {
  const b = l.builds.find((x) => x.chromium === build);
  if (!b || b.playwright.join() !== pw.join()) throw new Error("missing " + build);
  for (const k of ["extension-linux", "devtools-linux", "devtools-macos"]) {
    const f = b.measured[k]; if (!f || !f.units || !(f.agreement > 0)) throw new Error(build + " " + k);
    require("fs").accessSync("./" + f.figure + "agreement.txt"); require("fs").accessSync("./" + f.figure + "misses.json");
  }
}'
# the rule was frozen before the first fleet capture (every capture is dated after the freeze), and the per-version tables are in the write-up
python3 - <<'PY'
import json
f = json.load(open("middleware/results/playwright-versions/freeze.json"))["namedAt"]
caps = json.load(open("middleware/results/playwright-versions/fleet-readings.json"))
assert len(caps) == 12 and all(c["capturedAt"] > f.replace("Z", ".000Z") for c in caps)
PY
grep -q '| 1.63.0 | 153.0.8010.12 | `devtools-macos` |' middleware/results/playwright-versions/README.md
# every miss has one cause of the closed list, and none is left unexplained
python3 - <<'PY'
import glob, json
n = 0
for f in glob.glob("middleware/results/playwright-versions/*/*/misses.json"):
    for m in json.load(open(f))["misses"]:
        assert m["cause"] != "unexplained" and m["cause"]; n += 1
assert n > 0
PY
# the package: lint, types, tests (the list's figures equal their agreement.txt; the CI rows are held to the list)
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
# the measurement's scripts
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
python3 -m unittest discover -s middleware/bundle -t middleware/bundle
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_cdp.py'
python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_fallback.py'
```

Pre-merge proof on both runners: the `demo` job of `.github/workflows/middleware-spike.yml` (Playwright 1.64.1 and 1.63.0 on ubuntu-latest and macos-latest, `--expect-measured` for the default source's runs and for Ubuntu's DevTools run, `--expect-unmeasured` for macOS's third, extension, run, which has no figure; 1.62.1 on ubuntu-latest, `--expect-unmeasured`). `middleware/results/playwright-versions/ci-run.txt` is the stamp that started the macOS and control readings (`.github/workflows/playwright-versions-agreement.yml`).
