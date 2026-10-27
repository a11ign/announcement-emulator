"""What reading the DevTools tree cost in a run of the sample suite (A11-229, step 2): the runtime's own profile (`AE_PROFILE=<file>`, one line for each read of a page's tree) and the run summary the reporter writes
(`test-results/announcement-emulator/run.json`), put into numbers that two runs can be set side by side by.

    python3 summarize_cost.py <out.json> <label>=<run dir> [<label>=<run dir> ...]       <run dir>/{profile.jsonl,run.json}
    python3 summarize_cost.py --table <summary.json> <label> [<label> ...]               a markdown table of the labels, in that order

A read is `full` (the whole AX tree and a DOM snapshot, converted whole) or `incremental` (the nodes that can have changed read again, incremental.py). Its cost is the time the runtime's tree thread took, in ms:
`fetchMs` (the round trips to the browser; for an incremental read the probe, the nodes read again and the commit), `convertMs` (the conversion, or the patch of the node list). `speechMs` is the time the predictor
took to make speech (NVDA's own code, and the emulator's buffer, which is built again for each focus move), `drainMs` what the runtime took at the end of the run to finish what it had been told."""
import json, os, re, sys

FULL, INCREMENTAL = 'full', 'incremental'
LARGE = 1000      # a page of this many nodes or more: where one node changing is to cost a quarter of a full read at most


def load_rows(path):
    with open(path) as f: return [json.loads(line) for line in f if line.strip()]


def mean(values): return sum(values) / len(values) if values else None


def why(reason):
    """Why a read was whole, in words that do not name a node or a count: `stale: Stale a node the page did not have: 325 (read for a <div>...)` is `stale: a node the page did not have: N`."""
    if not reason: return 'before the probe existed'
    text = re.sub(r' \(read for .*\)$', '', str(reason)); stale = text.startswith('stale: ')
    text = re.sub(r'^stale: (Stale )?', '', text)
    text = re.sub(r'\d+', 'N', text)
    return ('stale: ' if stale else '') + text


def reads(rows):
    """The reads of a profile: how many, how they were made, what they cost, and why the full ones were full."""
    full = [r for r in rows if r['how'] == FULL]; incremental = [r for r in rows if r['how'] == INCREMENTAL]
    reasons = {}
    for r in full:
        key = why(r.get('reason')); reasons[key] = reasons.get(key, 0) + 1
    big_full = [r['totalMs'] for r in full if r['nodes'] >= LARGE]; big_incremental = [r['totalMs'] for r in incremental if r['nodes'] >= LARGE]
    return {'count': len(rows), 'full': len(full), 'incremental': len(incremental), 'patched': sum(1 for r in incremental if r.get('patched')),
            'totalMs': round(sum(r['totalMs'] for r in rows)), 'fullMs': round(sum(r['totalMs'] for r in full)), 'incrementalMs': round(sum(r['totalMs'] for r in incremental)),
            'fetchMs': round(sum(r['fetchMs'] for r in rows)), 'convertMs': round(sum(r['convertMs'] for r in rows)),
            'meanFullMs': round(mean([r['totalMs'] for r in full]) or 0, 1), 'meanIncrementalMs': round(mean([r['totalMs'] for r in incremental]) or 0, 1),
            'largePages': {'fullMs': round(mean(big_full) or 0, 1), 'incrementalMs': round(mean(big_incremental) or 0, 1), 'fullReads': len(big_full), 'incrementalReads': len(big_incremental),
                           'incrementalOverFull': round(mean(big_incremental) / mean(big_full), 3) if big_full and big_incremental else None},
            'whyFull': dict(sorted(reasons.items(), key=lambda kv: -kv[1]))}


def run(directory):
    rows = load_rows(os.path.join(directory, 'profile.jsonl')) if os.path.exists(os.path.join(directory, 'profile.jsonl')) else []
    with open(os.path.join(directory, 'run.json')) as f: summary = json.load(f)
    workers = summary['workers']
    return {'wallMs': summary['wallMs'], 'drainMs': summary.get('drainMs'), 'speechMs': sum(w.get('speechMs', 0) for w in workers), 'snapshots': sum(w.get('snapshots', 0) for w in workers),
            'keys': sum(w.get('keys', 0) for w in workers), 'focusEvents': sum(w.get('focusEvents', 0) for w in workers), 'unresolvedFocus': sum(w.get('unresolvedFocus', 0) for w in workers),
            'tests': summary.get('tests'), 'reads': reads(rows)}


def seconds(ms): return f'{ms / 1000:.1f}'


def table(summary, labels):
    """A markdown table of the runs, each in a column."""
    def row(name, f): return f'| {name} | ' + ' | '.join(f(summary[label]) for label in labels) + ' |'
    lines = ['| | ' + ' | '.join(labels) + ' |', '|---|' + '---|' * len(labels),
             row('wall time (s)', lambda r: seconds(r['wallMs'])),
             row('of it, the runtime finishing what it was told after the last test (s)', lambda r: seconds(r['drainMs'] or 0)),
             row('`speechMs`: the predictor making speech (s)', lambda r: seconds(r['speechMs'])),
             row('reads of a tree', lambda r: f"{r['reads']['count']} ({r['reads']['full']} full, {r['reads']['incremental']} incremental)"),
             row('sum of the reads (s)', lambda r: seconds(r['reads']['totalMs'])),
             row('of it, the round trips to the browser (s)', lambda r: seconds(r['reads']['fetchMs'])),
             row('of it, the conversion (s)', lambda r: seconds(r['reads']['convertMs'])),
             row('mean full read (ms)', lambda r: f"{r['reads']['meanFullMs']:.0f}"),
             row('mean incremental read (ms)', lambda r: f"{r['reads']['meanIncrementalMs']:.0f}" if r['reads']['incremental'] else '-'),
             row(f'on pages of {LARGE} nodes or more: incremental over full', lambda r: f"{r['reads']['largePages']['incrementalOverFull']:.2f}" if r['reads']['largePages']['incrementalOverFull'] is not None else '-')]
    return '\n'.join(lines)


def main(argv):
    if argv[:1] == ['--table']:
        with open(argv[1]) as f: print(table(json.load(f), argv[2:]))
        return
    if len(argv) < 2 or any('=' not in a for a in argv[1:]): sys.exit(__doc__)
    out = {label: run(directory) for label, directory in (a.split('=', 1) for a in argv[1:])}
    with open(argv[0], 'w') as f: json.dump(out, f, indent=1); f.write('\n')
    print(f'{len(out)} runs written')


if __name__ == '__main__': main(sys.argv[1:])
