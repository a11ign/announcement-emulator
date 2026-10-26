Row A11-234, step 1 of 2: the middleware's own attributed misses are fixed with tests, and the report can print the measured rate by announcement shape, with its population, date and the fleet's own agreement as the ceiling. The page's focus is matched to the tree's node by the DOM node the browser names (or the name it computed) instead of a name the page script guessed; a link is "same page" by the document's address as of the tree, not the address the buffer was first made with; a page closed while its tree is read no longer renumbers its nodes. `supported-versions.json` has no figures yet, so no run prints a rate until step 2 measures and fills it: with an old entry (no shapes) every report reads as before. Step 2 is the freeze, the held-out measurement, the ceiling and the list's figures.

Acceptance (the package's own tests need `pnpm install` once; the replay tests need the emulator's virtualenv and NVDA's source in `$EMU_DOWNLOADS` and are skipped without them):

```bash
set -eu
# the package: lint, types, tests (the line with population and ceiling, the rate of a shape, a weak shape, a shape never seen, an old entry, check-report's --expect-shape-rates)
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
# the Python that needs neither NVDA nor a browser: matching by DOM node and by computed name, the document's address, the resolver against a fake DevTools socket, the converter kept across a closed page
python3 -W ignore -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_pure.py'
python3 -W ignore -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_cdp.py'
python3 -W ignore -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_axtree.py'
# the recorded sessions of the pages written for each fault, through both tree sources (skipped, and said so, where NVDA's source is not at $EMU_DOWNLOADS)
if [ -n "${EMU_DOWNLOADS:-}" ] && [ -d "$EMU_DOWNLOADS/nvda-src/source" ]; then
  "$EMU_DOWNLOADS/q2/venv/bin/python" -W ignore -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_replay.py'
fi
# the pages, their tests and the recordings are all there
for n in focus-by-node same-page same-page-route frames frames-below-the-fold frames-scrolled-to; do
  test -f "middleware/runtime/fixtures/misses/$n.jsonl.gz" && test -f "middleware/runtime/fixtures/misses/devtools-$n.jsonl.gz"
done
test -f middleware/sample-suite/tests/misses/focus-by-node.spec.ts && test -f middleware/sample-suite/tests/misses/same-page.spec.ts && test -f middleware/sample-suite/tests/misses/frames.spec.ts
```

Row A11-234, step 2 of 2: round one of the agreement loop. The rule (`middleware/results/agreement-round-1/rule.md`) was frozen before the first fleet capture; the held-out pages (the next six by the spike's selection rule) and the six fitted pages were measured in one window against 24 fleet captures (`a11y-worker-14`, `-15`, `-16`, Edge 156.0.4314.42); the fleet against itself is stated as the ceiling beside every figure; every miss has one cause; low-confidence shapes are flagged; `middleware/supported-versions.json` holds the held-out figures, each with its population, the ceiling and the rate by shape; the write-up is `middleware/results/agreement-round-1/README.md`. No target is set.

Acceptance (no network, no fleet and no browser; the package's own tests need `pnpm install` once):

```bash
set -eu
R=middleware/results/agreement-round-1
# the rule was frozen before the first fleet capture, and the held-out pages were chosen without the fitted six and the rejected one
python3 - <<'PY'
import json
R = "middleware/results/agreement-round-1"
f = json.load(open(R + "/freeze.json"))["namedAt"]
caps = json.load(open(R + "/fleet-readings.json"))
assert len(caps) == 24 and all(c["capturedAt"] > f.replace("Z", ".000Z") for c in caps)
assert {c["environment"]["browserVersion"] for c in caps} == {"156.0.4314.42"}
held = {p["address"] for p in json.load(open(R + "/held-out-pages.json"))["sample"]}
fitted = {p["address"] for p in json.load(open("middleware/results/agreement/pages.json"))["sample"]}
assert len(held) == 6 and not (held & fitted)
PY
# the list: both builds, three readings each; every figure is a held-out one with its population, its ceiling and its rates by shape, and its files are in the repository
node -e '
const fs = require("fs");
const l = require("./middleware/supported-versions.json");
for (const build of ["156.0.8078.4", "153.0.8010.12"]) {
  const b = l.builds.find((x) => x.chromium === build); if (!b) throw new Error("missing " + build);
  for (const k of ["extension-linux", "devtools-linux", "devtools-macos"]) {
    const f = b.measured[k];
    if (!f || !f.population?.heldOut || !(f.ceiling?.agreement > 0) || !Object.keys(f.shapes ?? {}).length) throw new Error(build + " " + k);
    for (const n of ["agreement.txt", "misses.json", "rates.json"]) fs.accessSync("./" + f.figure + n);
  }
}'
# every miss has one cause of the closed list (A11-229, A11-230, test blocked, offscreen frame); an unexplained one carries its reason
python3 - <<'PY'
import glob, json
n = 0
for f in glob.glob("middleware/results/agreement-round-1/*/*/*/misses.json"):
    for m in json.load(open(f))["misses"]:
        assert m["cause"] and (m["cause"] != "unexplained" or m["reason"]); n += 1
assert n > 0
PY
# the write-up has the held-out figure, the ceiling and the fitted comparison; the package's README prints the held-out table
grep -q 'the fleet against itself (ceiling)' $R/README.md && grep -q 'A11-230.s figure' $R/README.md
grep -q 'the fleet against itself | date' middleware/README.md
# the package: lint, types, tests (the list's figures equal their agreement.txt, rates.json and the population; the report prints the line and flags a weak shape)
( cd middleware && pnpm install --frozen-lockfile >/dev/null && pnpm run lint && pnpm run typecheck && pnpm test >/dev/null )
# the measurement's scripts: the ceiling, the two causes added, the rates by shape, the low-confidence flag, the movement, the held-out selection
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
python3 -m unittest discover -s middleware/bundle -t middleware/bundle
```
