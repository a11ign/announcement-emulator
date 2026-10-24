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
