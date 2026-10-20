#!/bin/sh
# usage: try1.sh <slug> [port]  -- one dev page through the emulator once, then the per-channel differences from the fleet's lists (refuses a held page)
SP=${SP:?}; slug=$1; port=${2:-8801}
py=$HOME/spikes/announcement-emulator-5661/q2/venv/bin/python
url=$($py -c "import json,sys; print(json.load(open('$SP/runs/real-page-corpus/$slug.json'))['capture']['url'])")
$py -c "import sys; sys.path.insert(0,'$(dirname "$0")'); from split import split_of; sys.exit(0 if split_of('$url')=='dev' else 3)" || { echo "held page: refused"; exit 3; }
$py $(dirname "$0")/emulate.py "$url" $SP/try-$slug.json --port $port --history $SP/history-first.json > $SP/logs/try-$slug.log 2>&1
$py $(dirname "$0")/cmp1.py $SP/try-$slug.json $SP/runs/real-page-corpus/$slug.json
