#!/bin/sh
# measure.py for each reading, and for its second capture against its second run, as middleware/results/tree-source/rule.md fixes (A11-229).
#
#     middleware/agreement/measure_readings.sh <fleet dir> <work dir> <reading>=<report 1>,<report 2> ...
#
# e.g. ext-linux=/x/linux/extension-1/report.json,/x/linux/extension-2/report.json. For each reading it writes <work>/<reading>/ and <work>/<reading>-second/ (agreement.txt and agreement.json);
# middleware/agreement/compare_sources.py reads them. Every channel is compared, stable or not, and a page whose title is the same but whose heading or link count differs by one is compared.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
FLEET="${1:?the fleet capture directory}"; WORK="${2:?the work directory}"; shift 2
PAGES="$HERE/../results/agreement/pages.json"
for spec in "$@"; do
  reading="${spec%%=*}"; reports="${spec#*=}"
  r1="${reports%%,*}"; r2="${reports#*,}"
  python3 "$HERE/measure.py" --fleet "$FLEET" --pages "$PAGES" --passive "$r1" "$r2" --include-unstable --tolerate-census --out "$WORK/$reading" > /dev/null
  python3 "$HERE/measure.py" --fleet "$FLEET" --pages "$PAGES" --passive "$r1" "$r2" --include-unstable --tolerate-census --second --out "$WORK/$reading-second" > /dev/null
  echo "$reading: $(grep '^all channels' "$WORK/$reading/agreement.txt" | tail -1)"
done
