#!/bin/bash
# usage: SEED=a,b iter.sh targets... -> prints last frames of first failure
cd "$(dirname "$0")"
python3 autostub.py "$@" 2>&1 | grep -E "^(OK|FAIL|STUBBED|LEDGER)|File \".*nvda-src/source" | tail -${TAILN:-10}
