"""Every check of the re-measure (A11-155) that can run without the fleet or a commit, and the ones that can only run once the fleet has been (reported `pending`, not passed).

    python check.py [--results q3/results/remeasure] [--oracle <dir>] [--doc docs/announcement-emulator-spike.md --base <ref>] [--require-complete]

  readback    every box in history-readback.json carries a `passed` flag equal to its readings (policy value 1, emptied store, clean `after` probe), and the `before`
              positive control read `visited` on each box, the readings are in the order of the steps, and at least three boxes pass
  oracle      the fresh oracle holds exactly the corpus addresses, each a good capture stamped by a box that held a clean read-back through the run (`after-run` too), and no announcement in any swept channel carries the `visited` token (count 0)
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
MIN_BOXES = 3


def read_text(path):
    with open(path, errors='replace') as f: return f.read()


def check_readback(path):
    if not os.path.exists(path): return PENDING, 'no history-readback.json yet'
    data = rb.load(path); boxes = data['workers']; bad = []
    if not boxes: return PENDING, 'no box read back yet'
    if len(rb.passed_workers(data)) < MIN_BOXES: bad.append(f'fewer than {MIN_BOXES} boxes pass')
    for w, box in sorted(boxes.items()):
        if box.get('passed') != rb.box_passes(box): bad.append(f'{w}: stored `passed` disagrees with its readings')
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{len(rb.passed_workers(data))} of {len(boxes)} boxes pass: {", ".join(rb.passed_workers(data))}')


def check_oracle(directory, readback_path, corpus_path):
    files = sorted(glob.glob(os.path.join(directory, '*.json'))) if directory and os.path.isdir(directory) else []
    if not files: return PENDING, 'no fresh oracle yet'
    held = set(rb.held_workers(rb.load(readback_path))); bad = []; visited = 0; urls = set()
    for f in files:
        rec = rb.read_json(f); h = rec.get('history'); cap = rec.get('capture') or {}; name = os.path.basename(f)
        urls.add(cap.get('url')); visited += rb.announced_visited(cap)
        if not h or (h.get('policy') or {}).get('value') != 1 or not h.get('storeEmptied') or (h.get('probeAfter') or {}).get('visited') is not False: bad.append(f'{name}: no clean history block')
        elif rec.get('worker') not in held: bad.append(f'{name}: captured by {rec.get("worker")}, which did not hold a clean read-back through the run')
        if rec.get('status') != 200 or cap.get('error') or not cap.get('structure'): bad.append(f'{name}: not a capture')
    expected = {e if isinstance(e, str) else e['url'] for e in rb.read_json(corpus_path)}
    if urls != expected: bad.append(f'{len(expected - urls)} corpus addresses missing, {len(urls - expected)} not in the corpus')
    if visited: bad.append(f'{visited} announcements carry `visited`: the history was not clean, measure nothing')
    return (FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')) if bad else (OK, f'{len(files)} records, all stamped, visited count 0')


def gate_of(misses_path):
    """The Gate figure a measure.py --json holds, or None for a misses file that is not one (attribute.py's output is a bare list)."""
    data = rb.read_json(misses_path)
    return data.get('gate') if isinstance(data, dict) else None


def check_figures(results):
    pairs = [(m, m.replace('misses-', 'measure-')[:-5] + '.txt') for m in sorted(glob.glob(os.path.join(results, 'misses-*.json'))) if gate_of(m)]
    if not pairs: return PENDING, 'no figures yet'
    bad = []
    for m, t in pairs:
        gate = gate_of(m); line = re.search(r'^GATE: (\d+) of (\d+)', read_text(t) if os.path.exists(t) else '', re.M)
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


def ends_before_a_section(doc, next_line):
    """The added block is followed by a `## ` heading or the end of the page, so it sits between sections and not inside one."""
    lines = read_text(doc).splitlines()
    return next_line > len(lines) or lines[next_line - 1].startswith('## ')


def check_doc(doc, base):
    diff = subprocess.run(['git', 'diff', '-U0', base, '--', doc], capture_output=True, text=True, check=True).stdout
    if not diff: return PENDING, 'the Re-measure section is not written yet'
    body = diff.splitlines()
    removed = [l for l in body if l.startswith('-') and not l.startswith('---')]
    added = [l[1:] for l in body if l.startswith('+') and not l.startswith('+++')]
    first_added_line = [int(n) for n in re.findall(r'^@@ -\d+(?:,\d+)? \+(\d+)', diff, re.M)]
    gate_line = next((n for n, l in enumerate(read_text(doc).splitlines(), 1) if l.startswith('## Gate')), None)
    if removed: return FAIL, f'{len(removed)} existing lines changed or removed'
    one_section_after_gate = len(first_added_line) == 1 and [l for l in added if l.startswith('## ')] == ['## Re-measure'] and gate_line is not None and first_added_line[0] > gate_line
    one_section_after_gate = one_section_after_gate and ends_before_a_section(doc, first_added_line[0] + len(added))
    if not one_section_after_gate: return FAIL, 'not one `## Re-measure` section added after `## Gate`'
    return OK, f'one section, {len(added)} lines added after `## Gate`, nothing else touched'


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--results', default='q3/results/remeasure'); ap.add_argument('--oracle'); ap.add_argument('--corpus', default='q3/results/corpus.json'); ap.add_argument('--doc', default='docs/announcement-emulator-spike.md')
    ap.add_argument('--base', default='origin/main'); ap.add_argument('--require-complete', action='store_true'); a = ap.parse_args(argv)
    readback = os.path.join(a.results, 'history-readback.json')
    results = [('readback', check_readback(readback)), ('oracle', check_oracle(a.oracle, readback, a.corpus)), ('figures', check_figures(a.results)),
               ('addresses', check_addresses([a.results, a.doc])), ('doc', check_doc(a.doc, a.base))]
    for name, (state, msg) in results: print(f'{state:>8}  {name}: {msg}')
    states = {s for _, (s, _) in results}
    sys.exit(1 if FAIL in states or (a.require_complete and PENDING in states) else 0)


if __name__ == '__main__': main(sys.argv[1:])
