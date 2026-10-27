"""Which pages of a run of the sample suite got a prediction (A11-229, step 2): the `large` project exists for pages of 705 to 1,770 tab stops that the middleware predicted nothing for, and a run of it is only worth
something if every page has the speech of its load and of its walked stops.

    python3 check_predictions.py <test-results/report.json> [<expected pages>]      prints one line for each test, exits 1 if a test has no load speech or fewer than MIN_FOCUS focus moves

The reporter attaches `predicted-nvda-speech.json` to each test; its `predictedSpeech` has one utterance for each cause (`load`, `focus`, `typed`, ...)."""
import base64, collections, json, sys

ATTACHMENT = 'predicted-nvda-speech.json'
MIN_FOCUS = 100         # tests/large walks at most MAX_STOPS = 150 tab stops of a page; a page that was predicted has most of them


def tests(suite):
    """Every (title, result) of a Playwright JSON report, depth first."""
    for spec in suite.get('specs', []):
        for test in spec['tests']:
            for result in test['results']: yield spec['title'], result
    for child in suite.get('suites', []): yield from tests(child)


def counted(result):
    """The utterances of a result by cause, or None if the reporter attached no prediction to it."""
    for attachment in result.get('attachments', []):
        if attachment['name'] == ATTACHMENT:
            speech = json.loads(base64.b64decode(attachment['body']).decode())['predictedSpeech']
            return collections.Counter(u['cause'] for u in speech)
    return None


def predictions(report):
    """One row for each test of a report: its page, its status, and its utterances by cause (zero for all if nothing was attached)."""
    rows = []
    for suite in report['suites']:
        for title, result in tests(suite):
            causes = counted(result) or collections.Counter()
            rows.append({'page': title.split(' of ', 1)[-1], 'status': result['status'], 'load': causes['load'], 'focus': causes['focus'], 'typed': causes['typed']})
    return rows


def unpredicted(rows, expected=()):
    """The pages with no load speech or too few focus moves, and the expected pages that no test ran."""
    missing = [row['page'] for row in rows if not row['load'] or row['focus'] < MIN_FOCUS]
    return missing + [page for page in expected if page not in {row['page'] for row in rows}]


def main(argv):
    if not argv: sys.exit(__doc__)
    with open(argv[0]) as f: rows = predictions(json.load(f))
    expected = [page['address'] for page in json.load(open(argv[1]))] if argv[1:] else []
    for row in rows: print(f"{row['page']}: {row['load']} load, {row['focus']} focus, {row['typed']} typed ({row['status']})")
    missing = unpredicted(rows, expected)
    if missing: sys.exit('no prediction (or fewer than %d focus moves): %s' % (MIN_FOCUS, ', '.join(missing)))


if __name__ == '__main__': main(sys.argv[1:])
