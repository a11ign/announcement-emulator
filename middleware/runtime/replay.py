"""Run the predictor over a session that was recorded (AE_RECORD=<file> when the runtime ran), without a browser:

    python -I replay.py <recording.jsonl[.gz]> [--report-focus] [--no-sweeps]

Prints the records as one JSON list. What the tests of the predictor are made from, and a way to see again what a run was told.
"""
import gzip, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def replay(path, **options):
    path = os.path.abspath(path)      # NVDA's boot changes the working directory
    import predict
    from main import Ordered
    records = []
    predictor = predict.Predictor(records.append, **options)
    ordered = Ordered()
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt') as f:
        for line in f:
            row = json.loads(line)
            if row['k'] == 'page': predictor.on_page_event(row['body'])
            else:
                ordered.add(row['body'], row['arrived'])
                for snap in ordered.ready(row['arrived']): predictor.on_snapshot(snap)
    for snap in ordered.ready(float('inf'), final=True): predictor.on_snapshot(snap)
    stats = predictor.finish()
    return records, stats


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    records, stats = replay(args[0], sweeps='--no-sweeps' not in sys.argv, report_focus='--report-focus' in sys.argv)
    print(json.dumps({'records': records, 'stats': stats}))
