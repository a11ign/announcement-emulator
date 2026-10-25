#!/usr/bin/env python3
"""python3 compare_live.py [--strict] <report.json of a full-layout run> <report.json of a second full-layout run> <report.json of the lean bundle's run>

The live half of "unchanged behaviour" (A11-231): the sample suite's predicted speech and flags for each test, in the lean bundle's run and in the full layout's, from the Playwright JSON reports. A live
browser's timing can move the last event of a quick test, so a difference counts only where two runs of the full layout agree with each other on that test; a test they disagree on is named as unstable
and is not compared. The recorded sessions (compare_bundles.py replay) are the byte-for-byte proof, and compare_bundles.py misses is the check that fails CI; this one reports what the live path that the recordings do
not take (cdp.py, main.py) did. It reports and exits 0, because two runs of the full layout that agree can agree by chance: measured in CI (A11-231), on a runner 9 of 13 tests were unstable between two full runs,
and 2 of the 4 that agreed differed in the lean run, in a quick test whose last event a run caught or missed. --strict makes a difference a failure.
"""
import base64, json, sys


def predictions(report_path):
    """{test title: (the speech as (cause, text) in order, the flags raised)} from a Playwright JSON report."""
    with open(report_path) as f: report = json.load(f)
    out = {}

    def walk(suite):
        for child in suite.get('suites', []): walk(child)
        for spec in suite.get('specs', []):
            for test in spec['tests']:
                for attachment in test['results'][-1].get('attachments', []):
                    if attachment['name'] != 'predicted-nvda-speech.json': continue
                    data = json.loads(base64.b64decode(attachment['body']))
                    out[spec['title']] = ([(u['cause'], u['text']) for u in data['predictedSpeech']], sorted(f['flag'] if isinstance(f, dict) else f for f in data['flags']))

    walk({'suites': report['suites']})
    return out


def compare(full_a, full_b, lean):
    """(the tests the lean run differs on where the full layout agreed with itself, the tests the full layout did not agree with itself on, the number compared)."""
    differ, unstable, compared = [], [], 0
    for title in sorted(set(full_a) | set(full_b) | set(lean)):
        a, b, c = full_a.get(title), full_b.get(title), lean.get(title)
        if a != b: unstable.append(title); continue
        compared += 1
        if a != c: differ.append(title)
    return differ, unstable, compared


def main(argv):
    strict = '--strict' in argv
    argv = [a for a in argv if a != '--strict']
    if len(argv) != 4: print(__doc__, file=sys.stderr); return 2
    full_a, full_b, lean = (predictions(p) for p in argv[1:])
    differ, unstable, compared = compare(full_a, full_b, lean)
    for title in differ: print(f'differs in the lean bundle: {title}\n  full layout: {full_a.get(title)}\n  lean bundle: {lean.get(title)}')
    print(f'{compared} tests compared, {len(differ)} differ; {len(unstable)} not compared because two runs of the full layout disagree' + (f' ({"; ".join(unstable)})' if unstable else ''))
    return 1 if differ and strict else 0


if __name__ == '__main__': sys.exit(main(sys.argv))
