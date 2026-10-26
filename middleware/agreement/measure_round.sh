#!/bin/sh
# measure.py for each reading of one page set, for its second capture against its second run, and the pages whose corpus test did not finish, as middleware/results/agreement-round-1/rule.md fixes (A11-234).
#
#     middleware/agreement/measure_round.sh <pages.json> <fleet dir> <work dir> <reading>=<report 1>,<report 2> ...
#
# e.g. ext-linux=/x/linux/held-out/156.0.8078.4/extension-1/report.json,/x/linux/held-out/156.0.8078.4/extension-2/report.json. <pages.json> is the set's own file (held-out-pages.json, or the fitted
# results/agreement/pages.json), <work dir> is <work>/<set>/<build>: for each reading it writes <work dir>/<reading>/ and <work dir>/<reading>-second/ (agreement.txt and agreement.json) and
# <work dir>/<reading>/blocked.json (the pages whose test did not pass in the first run); middleware/agreement/round.py reads them. Every channel is compared, stable or not, and a page whose title is the
# same but whose heading or link count differs by one is compared (A11-229's rule, adopted unchanged).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PAGES="${1:?the pages file of the set}"; FLEET="${2:?the fleet capture directory}"; WORK="${3:?the work directory}"; shift 3
for spec in "$@"; do
  reading="${spec%%=*}"; reports="${spec#*=}"
  r1="${reports%%,*}"; r2="${reports#*,}"
  python3 "$HERE/measure.py" --fleet "$FLEET" --pages "$PAGES" --passive "$r1" "$r2" --include-unstable --tolerate-census --out "$WORK/$reading" > /dev/null
  python3 "$HERE/measure.py" --fleet "$FLEET" --pages "$PAGES" --passive "$r1" "$r2" --include-unstable --tolerate-census --second --out "$WORK/$reading-second" > /dev/null
  python3 "$HERE/round.py" blocked "$r1" > "$WORK/$reading/blocked.json"
  echo "$reading: $(grep '^all channels' "$WORK/$reading/agreement.txt" | tail -1); unfinished: $(cat "$WORK/$reading/blocked.json")"
done
