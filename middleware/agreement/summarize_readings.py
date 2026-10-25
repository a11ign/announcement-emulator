"""The records of a measurement's own dates and counts (A11-229): what `fleet-readings.json` and `passive-runs.json` hold, written from the fleet captures and the passive runs, so that no number in them is typed.

    python3 summarize_readings.py fleet  <fleet dir> <out.json>
    python3 summarize_readings.py passive <runs dir> <out.json>     <runs dir>/<source>-<n>/{run.json,times.json}, as run_linux_readings.sh writes them

`fleet`: for each capture, its file, the worker that took it, when, the status, the number of transcript lines and focus stops, and the browser and Windows build the capture itself names. Third-party pages' records
are not read further and not copied. `passive`: for each run, its dates and the counts of its runtime (the snapshots, keys, focus events, focus moves that could not be matched, skipped sweeps and lost snapshots),
and the time the runtimes took (`speechMs`, `drainMs`, `wallMs`)."""
import glob, json, os, sys

WORKER_COUNTS = ('snapshots', 'keys', 'focusEvents', 'unresolvedFocus', 'skippedSweeps', 'lostSnapshots', 'speechMs')


def load(path):
    with open(path) as f: return json.load(f)


def fleet(directory):
    out = []
    for path in sorted(glob.glob(os.path.join(directory, '*.json'))):
        record = load(path)
        capture = record.get('capture') or {}
        environment = capture.get('environment') or {}
        out.append({'file': os.path.basename(path), 'worker': record.get('worker'), 'capturedAt': record.get('capturedAt'), 'status': record.get('status'),
                    'transcriptLines': len(capture.get('transcript') or []), 'focusStops': len((capture.get('interaction') or {}).get('focusOrder') or []),
                    'environment': {k: environment.get(k) for k in ('browserVersion', 'windowsVersion', 'windowsBuild', 'nvdaVersion')}})
    return out


def passive(directory):
    out = {}
    for run_dir in sorted(glob.glob(os.path.join(directory, '*-[0-9]'))):
        times, run = load(os.path.join(run_dir, 'times.json')), load(os.path.join(run_dir, 'run.json'))
        out[f"{times['reading']}-run{times['run']}"] = {'startedAt': times['startedAt'], 'finishedAt': times['finishedAt'], 'tests': run['tests'], 'flags': run['flags'], 'wallMs': run['wallMs'], 'drainMs': run['drainMs'],
                                                       'workers': [{k: w[k] for k in WORKER_COUNTS if k in w} for w in run['workers']]}
    return out


def main(argv):
    if len(argv) != 3 or argv[0] not in ('fleet', 'passive'): sys.exit(__doc__)
    data = fleet(argv[1]) if argv[0] == 'fleet' else passive(argv[1])
    with open(argv[2], 'w') as f: json.dump(data, f, indent=1); f.write('\n')
    print(f'{len(data)} {"captures" if argv[0] == "fleet" else "runs"} written')


if __name__ == '__main__': main(sys.argv[1:])
