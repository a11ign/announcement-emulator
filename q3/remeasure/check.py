"""Every check of the re-measure (A11-155) that can run without the fleet or a commit, and the ones that can only run once the fleet has been (reported `pending`, not passed).

    python check.py [--results q3/results/remeasure] [--oracle <dir>] [--doc docs/announcement-emulator-spike.md --base <ref>] [--require-complete]

  readback    every worker in history-readback.json that is named as used has a policy value of 1, an emptied store, a clean `after` probe, and the `before` positive control
              (on at least the first box) read `visited`
  oracle      every record in the fresh oracle has a `history` block from a passing worker, and no announcement in any swept channel carries the `visited` token (count 0)
  figures     each misses-*.json's gate.exact/total equals the GATE line of its measure-*.txt
  addresses   nothing under the results directory or in the doc holds an IPv4 literal
  doc         the diff against the base touches the spike page only by adding one `## Re-measure` section after `## Gate`
Exit 1 on any failure; with --require-complete, also on anything pending."""
import sys, os, re, json, glob, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readback as rb

CHANNELS = ('headings', 'landmarks', 'formFields', 'graphics', 'links', 'lists', 'frames', 'tableCells')
IPV4 = re.compile(r'(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w]|\.\d)')
OK, FAIL, PENDING = 'ok', 'FAIL', 'pending'


def read_text(path):
    with open(path, errors='replace') as f: return f.read()


def check_readback(path):
    if not os.path.exists(path): return PENDING, 'no history-readback.json yet'
    data = rb.load(path); boxes = data['workers']; bad = []
    if not boxes: return PENDING, 'no box read back yet'
    for w, box in sorted(boxes.items()):
        if box.get('passed') != rb.box_passes(box): bad.append(f'{w}: stored `passed` disagrees with its readings')
    before = [w for w, b in boxes.items() if 'before' in b]
    if not before: bad.append('no `before` reading on any box: the probe has not been shown to see history')
    for w in before:
        if not rb.stage_passes('before', boxes[w]['before']): bad.append(f'{w}: the `before` probe did not read visited, so the probe cannot see history')
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{len(rb.passed_workers(data))} of {len(boxes)} boxes pass: {", ".join(rb.passed_workers(data))}')


def visited_count(rec):
    structure = (rec.get('capture') or {}).get('structure') or {}
    return sum('visited' in rb.tokens(a) for ch in CHANNELS for a in structure.get(ch) or [])


def check_oracle(directory, readback_path):
    files = sorted(glob.glob(os.path.join(directory, '*.json'))) if directory and os.path.isdir(directory) else []
    if not files: return PENDING, 'no fresh oracle yet'
    passed = set(rb.passed_workers(rb.load(readback_path))); bad = []; visited = 0
    for f in files:
        rec = rb.read_json(f); h = rec.get('history'); name = os.path.basename(f)
        if not h or (h.get('policy') or {}).get('value') != 1 or not h.get('storeEmptied'): bad.append(f'{name}: no history block')
        elif rec.get('worker') not in passed: bad.append(f'{name}: captured by {rec.get("worker")}, which has no passing read-back')
        visited += visited_count(rec)
    if visited: bad.append(f'{visited} announcements carry `visited`: the history was not clean, measure nothing')
    return (FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')) if bad else (OK, f'{len(files)} records, all stamped, visited count 0')


def check_figures(results):
    pairs = [(m, m.replace('misses-', 'measure-')[:-5] + '.txt') for m in sorted(glob.glob(os.path.join(results, 'misses-*.json')))]
    if not pairs: return PENDING, 'no figures yet'
    bad = []
    for m, t in pairs:
        gate = rb.read_json(m)['gate']; line = re.search(r'^GATE: (\d+) of (\d+)', read_text(t) if os.path.exists(t) else '', re.M)
        if not line: bad.append(f'{os.path.basename(t)}: no GATE line')
        elif (int(line[1]), int(line[2])) != (gate['exact'], gate['total']): bad.append(f'{os.path.basename(m)}: {gate["exact"]}/{gate["total"]} but the text says {line[1]}/{line[2]}')
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{len(pairs)} figures match their text')


def check_addresses(paths):
    hits = []
    for p in paths:
        files = [f for f in glob.glob(os.path.join(p, '**', '*'), recursive=True) if os.path.isfile(f)] if os.path.isdir(p) else [p] if os.path.exists(p) else []
        for f in files:
            for n, line in enumerate(read_text(f).splitlines(), 1):
                if IPV4.search(line): hits.append(f'{f}:{n}')
    return (FAIL, 'IPv4 literal at ' + ', '.join(hits[:5])) if hits else (OK, 'no IPv4 literal')


def check_doc(doc, base):
    diff = subprocess.run(['git', 'diff', '-U0', base, '--', doc], capture_output=True, text=True, check=True).stdout
    if not diff: return PENDING, 'the Re-measure section is not written yet'
    removed = [l for l in diff.splitlines() if l.startswith('-') and not l.startswith('---')]
    hunks = re.findall(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', diff, re.M)
    lines = read_text(doc).splitlines()
    gate = next((i + 1 for i, l in enumerate(lines) if l.startswith('## Gate')), None)
    first = next((int(s) for s, _ in hunks), None)
    added = [l[1:] for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]
    sections = [l for l in added if l.startswith('## ')]
    if removed: return FAIL, f'{len(removed)} existing lines changed or removed'
    if len(hunks) != 1 or sections != ['## Re-measure'] or gate is None or first <= gate: return FAIL, 'not one `## Re-measure` section added after `## Gate`'
    return OK, f'one section, {len(added)} lines added after `## Gate`, nothing else touched'


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--results', default='q3/results/remeasure'); ap.add_argument('--oracle'); ap.add_argument('--doc', default='docs/announcement-emulator-spike.md')
    ap.add_argument('--base', default='origin/main'); ap.add_argument('--require-complete', action='store_true'); a = ap.parse_args(argv)
    readback = os.path.join(a.results, 'history-readback.json')
    results = [('readback', check_readback(readback)), ('oracle', check_oracle(a.oracle, readback)), ('figures', check_figures(a.results)),
               ('addresses', check_addresses([a.results, a.doc])), ('doc', check_doc(a.doc, a.base))]
    for name, (state, msg) in results: print(f'{state:>8}  {name}: {msg}')
    states = {s for _, (s, _) in results}
    sys.exit(1 if FAIL in states or (a.require_complete and PENDING in states) else 0)


if __name__ == '__main__': main(sys.argv[1:])
