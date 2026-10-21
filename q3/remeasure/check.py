"""Every check of the re-measure (A11-155) that can run without the fleet or a commit, and the ones that can only run once the fleet has been (reported `pending`, not passed).

    python check.py [--results q3/results/remeasure] [--oracle <dir>] [--doc docs/announcement-emulator-spike.md --base <ref>] [--require-complete]

  readback    every box in history-readback.json carries a `passed` flag equal to its readings (policy value 1, emptied store, clean `after` probe), and the `before`
              positive control read `visited` on at least one box, the readings are in the order of the steps, and at least three boxes pass
  summary     oracle-summary.json (what is committed of the oracle) has the corpus addresses once each, every one stamped by a box that held a clean read-back through the run
  oracle      the fresh oracle holds exactly the corpus addresses, each a good capture stamped by a box that held a clean read-back through the run (`after-run` too), and no announcement in a swept channel carries `visited` unless explain_visited.py shows the emulator, with no history, announces it too (the browser's own mark on a link to the page it is on)
  figures     each misses-*.json's gate.exact/total equals the GATE line of its measure-*.txt
  addresses   nothing under the results directory or in the doc holds an IPv4 literal
  replay      (with --replay) the replay read-back, the archive manifest, the replay stamps on the oracle's records, the per-page join of the servers' logs, and the explanation of the eleven misses (A11-165)
  doc         the diff against the base touches the spike page only by adding one `## Re-measure` section after `## Gate`, or (the base having it) one `### ` subsection at the end of `## Re-measure`
Exit 1 on any failure; with --require-complete, also on anything pending."""
import sys, os, re, json, glob, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readback as rb
import explain_visited
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import corpus_capture

CHANNELS = ('headings', 'landmarks', 'formFields', 'graphics', 'links', 'lists', 'frames', 'tableCells')
IPV4 = re.compile(r'(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w]|\.\d)')
OK, FAIL, PENDING = 'ok', 'FAIL', 'pending'
MIN_BOXES = 3


def read_text(path):
    with open(path, errors='replace') as f: return f.read()


def check_readback(path, control_path=None):
    if not os.path.exists(path): return PENDING, 'no history-readback.json yet'
    data = rb.load(path); boxes = data['workers']; bad = []
    if not boxes: return PENDING, 'no box read back yet'
    if len(rb.cleared_workers(data)) < MIN_BOXES: bad.append(f'fewer than {MIN_BOXES} boxes pass')
    control = rb.control_workers(data) or (rb.control_workers(rb.load(control_path)) if control_path and os.path.exists(control_path) else [])
    if not control: bad.append('no box has a `before` probe that read visited: the probe has not been shown to see history')
    for w, box in sorted(boxes.items()):
        if box.get('passed') != rb.box_passes(box): bad.append(f'{w}: stored `passed` disagrees with its readings')
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{len(rb.cleared_workers(data))} of {len(boxes)} boxes cleared ({len(rb.held_workers(data))} held to the end, {sum(1 for b in boxes.values() if b.get("restored"))} restored): {", ".join(rb.cleared_workers(data))}; the probe saw history on {", ".join(control)}{" (in the run --control-from names)" if control_path and not rb.control_workers(data) else ""}')


def visited_problems(directory, visited, explained_path):
    """`visited` in the oracle is explained or it is a history that was not clean: explain_visited.py's output must account for every one, with the emulator's no-history run as the witness."""
    if not explained_path or not os.path.exists(explained_path): return [f'{visited} announcements carry `visited` and nothing explains them (explain_visited.py): the history was not clean, measure nothing']
    got = rb.read_json(explained_path)
    here = {}
    for f in sorted(glob.glob(os.path.join(directory, '*.json'))):
        cap = rb.read_json(f).get('capture') or {}; hits = [a for _, a in explain_visited.visited_in(cap)]
        if hits: here[cap.get('url')] = {'announcements': hits}
    if {u: v['announcements'] for u, v in got['pages'].items()} != {u: v['announcements'] for u, v in here.items()}: return [f'the explanation is not of this oracle\'s {visited} `visited` announcements (it names other pages or strings): run explain_visited.py again']
    if got['oracleVisitedAnnouncements'] != visited: return [f'{visited} announcements carry `visited` but the explanation covers {got["oracleVisitedAnnouncements"]}: it is stale']
    if got['unexplained']: return [f'{len(got["unexplained"])} of {visited} `visited` announcements are not explained: the history was not clean, measure nothing']
    return []


def record_problems(name, rec, held):
    """What is wrong with one oracle record on its own: its stamp, the box that captured it, whether it is a capture at all."""
    h, cap = rec.get('history'), rec.get('capture') or {}
    if not h or (h.get('policy') or {}).get('value') != 1 or not h.get('storeEmptied') or (h.get('probeAfter') or {}).get('visited') is not False: return [f'{name}: no clean history block']
    problems = [] if rec.get('worker') in held else [f'{name}: captured by {rec.get("worker")}, which did not hold a clean read-back through the run']
    if rec.get('status') != 200 or cap.get('error') or not cap.get('structure'): problems.append(f'{name}: not a capture')
    return problems


def check_oracle(directory, readback_path, corpus_path, explained_path=None):
    files = sorted(glob.glob(os.path.join(directory, '*.json'))) if directory and os.path.isdir(directory) else []
    if not files: return PENDING, 'no fresh oracle yet'
    held = set(rb.held_workers(rb.load(readback_path))); bad = []; visited = 0; urls = set()
    for f in files:
        rec = rb.read_json(f); cap = rec.get('capture') or {}; name = os.path.basename(f)
        swept = explain_visited.visited_in(cap); visited += len(swept); urls.add(rec.get('staticOf') or cap.get('url'))      # a static copy is the record of the address it is a copy of
        if not swept and rb.announced_visited(cap): bad.append(f'{name}: `visited` is spoken in the read-through but in no swept channel')
        bad += record_problems(name, rec, held)
        if rec.get('staticOf') and not str(cap.get('url', '')).endswith(f"/{corpus_capture.slug_of(rec['staticOf'])}/index.html"): bad.append(f'{name}: a copy of {rec["staticOf"]} that was not read at its own address')
    expected = {e if isinstance(e, str) else e['url'] for e in rb.read_json(corpus_path)}
    if len(files) != len(expected): bad.append(f'{len(files)} records for {len(expected)} corpus addresses')
    if urls != expected: bad.append(f'{len(expected - urls)} corpus addresses missing, {len(urls - expected)} not in the corpus')
    if visited: bad += visited_problems(directory, visited, explained_path)
    return (FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')) if bad else (OK, f'{len(files)} records, all stamped, {visited} `visited` announcements, {"all explained" if visited else "none"}')


def check_summary(path, readback_path, corpus_path):
    """oracle-summary.json is what is committed of the oracle (its pages are third-party's): one entry per corpus address, each stamped, each from a box that held."""
    if not os.path.exists(path): return PENDING, 'no oracle summary yet'
    held = set(rb.held_workers(rb.load(readback_path))); entries = rb.read_json(path); bad = []
    for e in entries: bad += record_problems(e['url'], {**e, 'capture': {'structure': {'x': [1]}}}, held)      # `structure` stands in: the summary keeps counts, the status is its own
    expected = {e['url'] for e in rb.read_json(corpus_path)}
    if {e['url'] for e in entries} != expected or len(entries) != len(expected): bad.append(f'the summary is not the {len(expected)} corpus addresses, once each')
    return (FAIL, '; '.join(bad[:5])) if bad else (OK, f'{len(entries)} entries, all stamped by a box that held')


def gate_of(misses_path):
    """The Gate figure a measure.py --json holds, or None for a misses file that is not one (attribute.py's output is a bare list)."""
    data = rb.read_json(misses_path)
    return data.get('gate') if isinstance(data, dict) else None


def thousands(n): return f'{int(n):,}'


def check_figures(results, doc=None):
    pairs = [(m, m.replace('misses-', 'measure-')[:-5] + '.txt') for m in sorted(glob.glob(os.path.join(results, 'misses-*.json'))) if gate_of(m)]
    if not pairs: return PENDING, 'no figures yet'
    bad = []
    for m, t in pairs:
        gate = gate_of(m); line = re.search(r'^GATE: (\d+) of (\d+)', read_text(t) if os.path.exists(t) else '', re.M)
        if not line: bad.append(f'{os.path.basename(t)}: no GATE line')
        elif (int(line[1]), int(line[2])) != (gate['exact'], gate['total']): bad.append(f'{os.path.basename(m)}: {gate["exact"]}/{gate["total"]} but the text says {line[1]}/{line[2]}')
    if doc and os.path.exists(doc):
        page = read_text(doc)
        for m, t in pairs:
            line = re.search(r'^GATE: (\d+) of (\d+)', read_text(t), re.M)
            if f'{thousands(line[1])} of {thousands(line[2])}' not in page: bad.append(f'{os.path.basename(t)}: {thousands(line[1])} of {thousands(line[2])} is not on the page')
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{len(pairs)} figures match their text' + (' and are on the page' if doc else ''))


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


def doc_at(base, doc):
    """The page as the base ref holds it, '' when the base does not have it. `git show` names a path from the repository root, `git diff` from the directory it runs in: the page is named the second way, so it is turned into the first."""
    root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
    done = subprocess.run(['git', 'show', f'{base}:{os.path.relpath(os.path.realpath(doc), os.path.realpath(root))}'], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else ''


def section_end(lines, start):
    """The 1-based line of the next `## ` heading after line `start`, or one past the end of the page."""
    return next((n for n in range(start + 1, len(lines) + 1) if lines[n - 1].startswith('## ')), len(lines) + 1)


def check_doc(doc, base):
    """The diff against the base touches the spike page by adding, and only adding: one `## Re-measure` section after `## Gate` when the base has none, or, once the base has it, exactly one `### ` subsection
    at the end of `## Re-measure` (right before the next `## ` section), the way A11-165's, A11-164's and A11-166's write-ups are added."""
    diff = subprocess.run(['git', 'diff', '-U0', base, '--', doc], capture_output=True, text=True, check=True).stdout
    if not diff: return PENDING, 'the write-up is not written yet' if doc_at(base, doc) else 'the Re-measure section is not written yet'
    body = diff.splitlines()
    removed = [l for l in body if l.startswith('-') and not l.startswith('---')]
    added = [l[1:] for l in body if l.startswith('+') and not l.startswith('+++')]
    first_added_line = [int(n) for n in re.findall(r'^@@ -\d+(?:,\d+)? \+(\d+)', diff, re.M)]
    lines = read_text(doc).splitlines()
    if removed: return FAIL, f'{len(removed)} existing lines changed or removed'
    if any(l.startswith('## Re-measure') for l in doc_at(base, doc).splitlines()):
        if len(first_added_line) != 1: return FAIL, 'not one block added'
        headings = [l for l in added if l.startswith('#')]
        remeasure = next((n for n, l in enumerate(lines, 1) if l.startswith('## Re-measure')), None)
        start = first_added_line[0]; end = section_end(lines, remeasure)
        trailing_blank = all(not l.strip() for l in lines[start - 1 + len(added):end - 1])
        if len(headings) != 1 or not headings[0].startswith('### ') or headings[0].startswith('#### ') or next(l for l in added if l.strip()) != headings[0]:
            return FAIL, 'not exactly one new `### ` subsection (it must open the added block, with no other heading in it)'
        if not (remeasure < start and start - 1 + len(added) <= end - 1 and trailing_blank): return FAIL, 'the new subsection is not at the end of `## Re-measure`'
        return OK, f'one subsection ({headings[0][4:]}), {len(added)} lines added at the end of `## Re-measure`, nothing else touched'
    gate_line = next((n for n, l in enumerate(lines, 1) if l.startswith('## Gate')), None)
    one_section_after_gate = len(first_added_line) == 1 and [l for l in added if l.startswith('## ')] == ['## Re-measure'] and gate_line is not None and first_added_line[0] > gate_line
    one_section_after_gate = one_section_after_gate and ends_before_a_section(doc, first_added_line[0] + len(added))
    if not one_section_after_gate: return FAIL, 'not one `## Re-measure` section added after `## Gate`'
    return OK, f'one section, {len(added)} lines added after `## Gate`, nothing else touched'


def replay_readback_module():
    """q3/replay's read-back module, imported when a replay run is checked, so the checks of a live run need nothing of q3/replay."""
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'replay'))
    import replay_readback
    return replay_readback


CLASSES = ('method', 'emulator bug', 'Windows-only')
EXPECTED_MISSES = 11


def check_replay_readback(path):
    """Every box in replay-readback.json carries flags equal to its readings, at least three boxes passed (read the marker of the archive-only page, behind the proxy, with the certificate in the store), and what a box
    that was restored shows: the values and the certificate gone, the probe no longer reaching the archive, the box `ready`."""
    if not os.path.exists(path): return PENDING, 'no replay-readback.json yet'
    rrb = replay_readback_module(); data = rrb.load(path); boxes = data['workers']
    if not boxes: return PENDING, 'no box read back yet'
    bad = []
    cleared = sorted(w for w, b in boxes.items() if rrb.box_passes({**b, 'restored': None}))
    if len(cleared) < MIN_BOXES: bad.append(f'fewer than {MIN_BOXES} boxes pass')
    for w, b in sorted(boxes.items()):
        if (b.get('passed'), b.get('heldRun'), b.get('restoredOk')) != (rrb.box_passes(b), rrb.box_held(b), rrb.box_restored(b)): bad.append(f'{w}: stored flags disagree with its readings')
    if bad: return FAIL, '; '.join(bad)
    return OK, f'{len(cleared)} of {len(boxes)} boxes read the archive-only page behind the replay server ({len(rrb.held_workers(data))} held to the end, {len(rrb.restored_workers(data))} restored and read back)'


def check_replay_stamps(directory, manifest_path, replay_readback_path):
    """Every record of a replay oracle carries a `replay` block naming the archive the manifest holds for its address, from a box that held behind the server, with the number the server did not answer."""
    files = sorted(glob.glob(os.path.join(directory, '*.json'))) if directory and os.path.isdir(directory) else []
    if not files or not os.path.exists(manifest_path) or not os.path.exists(replay_readback_path): return PENDING, 'no replay oracle yet'
    rrb = replay_readback_module(); manifest = {p['url']: p for p in rb.read_json(manifest_path)['pages']}; held = set(rrb.held_workers(rrb.load(replay_readback_path))); bad = []
    for f in files:
        rec = rb.read_json(f); block = rec.get('replay'); url = (rec.get('capture') or {}).get('url'); name = os.path.basename(f)
        if not block: bad.append(f'{name}: no replay block'); continue
        if url not in manifest: bad.append(f'{name}: {url} is not in the archive manifest')
        elif block.get('archiveSha256') != manifest[url]['sha256']: bad.append(f'{name}: served from an archive other than the manifest\'s')
        if not isinstance(block.get('unmatched'), int): bad.append(f'{name}: no unmatched-request count')
        if rec.get('worker') not in held: bad.append(f'{name}: captured by {rec.get("worker")}, which did not hold behind the replay server through the run')
    return (FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')) if bad else (OK, f'{len(files)} records, each from the archive the manifest names, by a box that held')


def check_manifest(path, corpus_path):
    """One archive per corpus address, once each, each with a sha256; a page recorded with an error status is served as 200, or the worker could not capture it."""
    if not os.path.exists(path): return PENDING, 'no archive manifest yet'
    pages = rb.read_json(path)['pages']; expected = {e if isinstance(e, str) else e['url'] for e in rb.read_json(corpus_path)}; bad = []
    if sorted(p['url'] for p in pages) != sorted(expected): bad.append(f'the manifest is not the {len(expected)} corpus addresses, once each')
    for p in pages:
        if not re.fullmatch(r'[0-9a-f]{64}', str(p.get('sha256'))): bad.append(f'{p.get("url")}: no sha256')
    if len({p.get('archive') for p in pages}) != len(pages): bad.append('two addresses share an archive file')
    for p in pages:
        if not 200 <= p.get('mainStatus', 200) < 300 and p.get('servedStatus') != 200: bad.append(f'{p.get("url")}: recorded with status {p.get("mainStatus")} and not served as 200, so the worker would refuse it')
    return (FAIL, '; '.join(bad[:5])) if bad else (OK, f'{len(pages)} archives, one per address, each with its sha256')


def check_served(summary_path, manifest_path):
    """The replay servers' logs of each page, joined (join.py): every page has the fleet's log and the emulator's, every one of them served from the archive the manifest names, and no request that the archive did
    not answer on one side was answered on the other, unless the summary names a reason for that page (`explained`, which the write-up carries)."""
    if not os.path.exists(summary_path) or not os.path.exists(manifest_path): return PENDING, 'no per-page request join yet'
    summary = rb.read_json(summary_path)['pages']; manifest = {p['url']: p for p in rb.read_json(manifest_path)['pages']}; bad = []; explained = 0
    if sorted(p['url'] for p in summary) != sorted(manifest): bad.append('the join is not of the manifest\'s addresses, once each')
    for p in summary:
        name = p['slug']
        if p.get('missing'): bad.append(f'{name}: {p["missing"]}'); continue
        sha = manifest[p['url']]['sha256'] if p['url'] in manifest else None
        shas = {p['fleet']['archiveSha256']} | {e['archiveSha256'] for e in p['emulator'].values()}
        if shas != {sha}: bad.append(f'{name}: the two sides were not served the manifest\'s archive')
        if p.get('differences'):
            if p.get('explained'): explained += 1
            else: bad.append(f'{name}: {len(p["differences"])} request(s) answered on one side and not the other, and no explanation')
    if bad: return FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')
    return OK, f'{len(summary)} pages, each side served the manifest\'s archive, no request answered on one side only' + (f' ({explained} differences explained)' if explained else '')


def check_explained(path, results, doc=None):
    """The misses the ticket asks to have explained: exactly EXPECTED_MISSES of them, each classed as method, emulator bug or Windows-only with evidence that is a file under the results (and, in the write-up, named),
    or kept `unexplained` with what was tried; and every one is on the page."""
    if not os.path.exists(path): return PENDING, 'no explanation of the misses yet'
    entries = rb.read_json(path)['misses']; bad = []
    if len(entries) != EXPECTED_MISSES: bad.append(f'{len(entries)} misses explained, {EXPECTED_MISSES} asked')
    page = read_text(doc) if doc and os.path.exists(doc) else None
    for e in entries:
        label = f'{e.get("page", "?")} {e.get("channel", "?")} {str(e.get("expected", ""))[:40]!r}'
        if e.get('class') in CLASSES:
            files = e.get('evidence') or []
            if not files: bad.append(f'{label}: class {e["class"]} with no evidence')
            for f in files:
                if not os.path.exists(os.path.join(results, f)): bad.append(f'{label}: evidence {f} is not under the results')
        elif e.get('class') == 'unexplained':
            if not e.get('tried'): bad.append(f'{label}: unexplained, and no account of what was tried')
        else: bad.append(f'{label}: class {e.get("class")!r} is none of {CLASSES} or unexplained')
        if page is not None and str(e.get('expected', '')) not in page: bad.append(f'{label}: not on the page')
    if bad: return FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')
    counts = {}
    for e in entries: counts[e['class']] = counts.get(e['class'], 0) + 1
    return OK, f'{len(entries)} misses, each classed with evidence: {counts}'


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--results', default='q3/results/remeasure'); ap.add_argument('--oracle'); ap.add_argument('--corpus', default='q3/results/corpus.json'); ap.add_argument('--explained'); ap.add_argument('--control-from', help='another run\'s history-readback.json whose `before` probes show the method (a run that took none of its own)'); ap.add_argument('--doc', default='docs/announcement-emulator-spike.md')
    ap.add_argument('--base', default='origin/main'); ap.add_argument('--require-complete', action='store_true'); ap.add_argument('--replay', action='store_true', help='a scripted-replay run (A11-165): the results hold replay-readback.json, archive-manifest.json, served-identically.json and misses-explained.json, and the oracle\'s records carry a `replay` block'); a = ap.parse_args(argv)
    readback = os.path.join(a.results, 'history-readback.json')
    results = [('readback', check_readback(readback, a.control_from)), ('summary', check_summary(os.path.join(a.results, 'oracle-summary.json'), readback, a.corpus)), ('oracle', check_oracle(a.oracle, readback, a.corpus, a.explained or os.path.join(a.results, 'visited-explained.json'))), ('figures', check_figures(a.results, a.doc)),
               ('addresses', check_addresses([a.results, a.doc])), ('doc', check_doc(a.doc, a.base))]
    if a.replay:
        manifest = os.path.join(a.results, 'archive-manifest.json')
        results += [('replay-readback', check_replay_readback(os.path.join(a.results, 'replay-readback.json'))), ('manifest', check_manifest(manifest, a.corpus)), ('replay-stamps', check_replay_stamps(a.oracle, manifest, os.path.join(a.results, 'replay-readback.json'))),
                    ('served', check_served(os.path.join(a.results, 'served-identically.json'), manifest)), ('explained', check_explained(os.path.join(a.results, 'misses-explained.json'), a.results, a.doc))]
    for name, (state, msg) in results: print(f'{state:>8}  {name}: {msg}')
    states = {s for _, (s, _) in results}
    sys.exit(1 if FAIL in states or (a.require_complete and PENDING in states) else 0)


if __name__ == '__main__': main(sys.argv[1:])
