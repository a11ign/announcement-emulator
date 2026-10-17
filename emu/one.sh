#!/bin/sh
# usage: one.sh TEST  -- run one test in its own process and print every step (PASS/FAIL, expected, actual)
cd "$(dirname "$0")" && timeout 600 ../q2/venv/bin/python run_cases.py --one "$1" 2>&1 | grep '^@@' | python3 -c "
import sys,json
rows=json.loads(sys.stdin.read()[2:]); print(sum(r[3] for r in rows),'/',len(rows))
for k,e,a,ok in rows:
    print('ok  ' if ok else 'MISS', k, '' if ok else repr(e)+'\n          got '+repr(a))"
