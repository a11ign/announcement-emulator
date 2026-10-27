"""Put the Playwright JSON reports of one run's projects together, so that measure.py reads one report for the run (A11-229, step 4).

    python3 merge_reports.py <run dir> <out report.json>        <run dir>/<project>/report.json, as run_devtools_readings.sh writes them

The merged report holds the suites of every project in the order of the project directories' names; a page walked by two projects would be walked twice, and is refused. Nothing else of a report is kept: measure.py reads
the tests' `predicted-nvda-speech.json` attachments and nothing more. It changes no prediction."""
import glob, json, os, re, sys


def specs(suite):
    for s in suite.get('suites', []): yield from specs(s)
    for spec in suite.get('specs', []):
        m = re.match(r'keyboard walk of (\S+)$', spec['title'])
        if m: yield m.group(1)


def merge(paths):
    suites, seen = [], {}
    for path in paths:
        with open(path) as f: report = json.load(f)
        for address in (a for s in report['suites'] for a in specs(s)):
            if address in seen: raise ValueError(f'{address} is walked by {seen[address]} and by {path}')
            seen[address] = path
        suites += report['suites']
    return {'suites': suites}


def main(argv):
    if len(argv) != 2: sys.exit(__doc__)
    paths = sorted(glob.glob(os.path.join(argv[0], '*', 'report.json')))
    if not paths: sys.exit(f'merge_reports.py: no <project>/report.json under {argv[0]}')
    try: merged = merge(paths)
    except ValueError as e: sys.exit(f'merge_reports.py: {e}')
    with open(argv[1], 'w') as f: json.dump(merged, f)
    print(f'{len(paths)} reports merged')


if __name__ == '__main__': main(sys.argv[1:])
