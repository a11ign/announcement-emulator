A11-233. `docs/release-decisions.md`: the wording, eight candidate package names (npm unscoped and under `@a11ign/`, GitHub and trademark results, dated 2026-10-24), the licence options for the npm package and the runtime bundle with sources, the NV Access requirement of ADR 0047 with a three-way amendment (keep, drop, move to "before the first non-preview release") and no message to NV Access, and a recommendation for each marked as the worker's. It decides nothing; nothing is published, sent or reserved.

Acceptance (reads the one document; needs no network):

```bash
set -eu
d=docs/release-decisions.md
test -f "$d"
# the candidate table: 8 rows, each of the chairman's six present, no NVDA in a name, a date in each row
rows=$(awk '/^### Candidates/{f=1;next} /^\*\*Taken names/{f=0} f && /^\| [0-9]+ \|/' "$d")
test "$(printf '%s\n' "$rows" | wc -l)" -ge 7
test "$(printf '%s\n' "$rows" | wc -l)" -le 8
for n in Hearsay Earshot Readout Foresay Forehear Echo; do printf '%s\n' "$rows" | grep -q "\*\*$n\*\*"; done
! printf '%s\n' "$rows" | cut -d'|' -f3 | grep -qi nvda
printf '%s\n' "$rows" | while IFS= read -r r; do printf '%s' "$r" | grep -Eq '20[0-9]{2}-[0-9]{2}-[0-9]{2} \|$'; done
# the working name is a comparison, not a candidate
grep -q 'not a candidate and not counted' "$d"
# the wording, the licence and the recommendations
grep -q 'NVDA-compatible' "$d"
grep -q 'based on the NVDA screen reader' "$d"
grep -q 'not legal advice' "$d"
grep -q 'GPL-3.0' "$d" && grep -q 'Apache-2.0' "$d"
test "$(grep -c 'recommendation, not a decision' "$d")" -ge 3
# the NV Access section: the amendment's three options, and no letter and no address
nv=$(awk '/^## 4\. NV Access/{f=1;next} /^## 5\./{f=0} f' "$d")
printf '%s\n' "$nv" | grep -q 'before the first non-preview release'
printf '%s\n' "$nv" | grep -q '^\*\*Keep\.\*\*'
printf '%s\n' "$nv" | grep -q '^\*\*Drop\.\*\*'
! printf '%s\n' "$nv" | grep -q '@'
! printf '%s\n' "$nv" | grep -Eq '^(Dear|Hello|Hi)\b'
# the after-merge handoff names who runs each step: the chairman chooses and sends, a follow-up records
after=$(awk '/^## 6\. After merge/{f=1;next} f' "$d")
printf '%s\n' "$after" | grep -q 'the chairman'
printf '%s\n' "$after" | grep -q 'Send a message to NV Access'
printf '%s\n' "$after" | grep -q 'a follow-up'
# only the document and this file changed
test "$(git diff --name-only origin/main...HEAD | grep -vc -e '^docs/release-decisions.md$' -e '^\.acceptance/')" = 0
```
