"""What is committed of the oracle (A11-165): one entry for each record, without the third-party transcript.

    python oracle_summary.py <oracle dir> <out.json>

The keys are those of q3/results/remeasure/oracle-summary.json (address, role, split, worker, status, when it was captured, how many lines the read-through held, how many announcements each channel swept, the title the page
settled on, the environment the worker reported, the `history` block) and the record's `replay` block: the archive it was served from, the run, the number of requests and of unanswered ones, and the box's read-back."""
import sys, os, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'remeasure'))
import readback as rb
from split import split_of


def entry(record):
    cap = record['capture']; env = cap.get('environment') or {}
    return {'url': cap['url'], 'role': record.get('role'), 'split': split_of(cap['url']), 'worker': record['worker'], 'status': record['status'], 'capturedAt': record['capturedAt'],
            'transcriptLines': len(cap.get('transcript') or []), 'swept': {k: len(v) for k, v in sorted((cap.get('structure') or {}).items())}, 'documentReadyTitle': next((e.get('title') for e in cap.get('diagnostics') or [] if e.get('event') == 'documentReady'), None),
            'environment': {k: env.get(k) for k in ('browserVersion', 'windowsBuild', 'provisionRevision', 'workerCode', 'captureProtocol')}, 'history': record['history'], 'replay': record['replay']}


def main(oracle, out):
    entries = [entry(rb.read_json(f)) for f in sorted(glob.glob(os.path.join(oracle, '*.json')))]
    rb.write_json(out, sorted(entries, key=lambda e: e['url']))      # a list, in address order
    print(len(entries), 'entries')


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(*sys.argv[1:])
