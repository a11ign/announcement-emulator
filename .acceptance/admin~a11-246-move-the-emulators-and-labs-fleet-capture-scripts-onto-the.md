Closes A11-246

The announcement emulator's capture entry points no longer run captures in the caller's shell. `q3/fleet_capture.py` (replacing `q3/fleet_capture.mjs`) is the one client of the fleet job service; `middleware/agreement/capture_fleet.py`, `q3/control_capture.py`, `q3/corpus_capture.py` and `q3/replay/fleet/box.sh` submit a job and print its ID, or with `--wait <duration>` make one foreground `fleet job wait`. `collect` writes the records (names, shape and stamps the pipelines read) from the fetched job's manifest. The runbooks show submit, then wait or declare, then collect. Lab's capture clients are A11-263.

Acceptance:

```bash
# every entry point submits with the right options against a stub `fleet`, and reads a manifest correctly
python3 -m unittest discover -s q3 -t q3 -p test_fleet_capture.py
python3 -m unittest discover -s q3/remeasure -t q3/remeasure -p 'test_*.py'
python3 -m unittest discover -s q3/replay -t q3/replay -p 'test_*.py'
python3 -m unittest discover -s middleware/agreement -t middleware/agreement -p 'test_*.py'
# no entry point has a wait loop, a sleep, a pgrep, a request to a worker or the removed node script, and the .mjs is gone: test_fleet_capture.py's NoShellCaptures asserts each of these (the first command above)
# a live capture (needs `fleet` and a page the boxes can reach; submits one job, prints its ID, then collects it)
# python3 q3/fleet_capture.py capture <box> <address> /tmp/probe.json --label A11-246 --wait 30m   # prints the job ID, then "200 N lines"
```
