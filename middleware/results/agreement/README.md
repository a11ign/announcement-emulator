# Results of the agreement measurement (A11-208, question 5)

What is committed is what the Gate committed: the tables, and each miss with the fleet's string, the prediction and the address. Not the fleet's records and not the passive reports of the pages: they are third-party pages.
`rule.md` is the rule, `freeze.json` the freeze (`agreement/make_freeze.py check freeze.json --head ca8145ad47` passes), `pages.json` the six pages, `boxes.md` the boxes, `fleet-readings.json` and `passive-runs.json` the captures' and runs' own dates and counts.

| figure | what it is |
|---|---|
| `figure-1/` | **taken at the freeze** (`60f001f`), the rules as frozen. Held to the freeze: the runtime had not yet seen the pages' misses. Two of the six pages had no passive reading and are counted in as misses (a status rule added afterwards lists them instead). |
| `figure-2/`, `figure-3/` | after the first corrections (a stop read with the focus on it; a state swept over its last tree; a browser launched again heard as the first). Intermediate; kept because they show what each correction was worth. **Not held out.** |
| `figure-4/` | **the final runtime**, all six pages read. The first block compares the channels that were the same in both fleet captures and both passive runs; the second compares every channel (the first fleet capture against the first passive run). A page whose title is the same and whose heading or link count differs by one is compared (`--tolerate-census`). **Not held out.** |
| `figure-5/` | the same runtime, the census rule as frozen (a count that differs excludes the page): three pages. **Not held out.** |
