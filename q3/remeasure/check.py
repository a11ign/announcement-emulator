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
  with --gate (A11-166, the Gate on new pages), on the results of that run (q3/results/gate), in place of the eleven misses of the replay:
  freeze      freeze.json names a commit that is an ancestor of this one, the `emu/` tree and the harness at this commit are the freeze's, A11-164's table is in it, the freeze was named before it was committed
              and before every capture of the run (each record's `capturedAt`)
  consent     consent-report.json holds every manifest page once, with the sidecar's outcome the manifest holds, and whether either side's capture begins in a cookie or consent surface; the counts are the manifest's
  comparable  comparability.json accounts for every page of the Gate's half: comparable, or one reason of the list
  crosswalk   the misses attribute.py lists (misses-held-freeze-attributed.json) and the attribution (misses-attributed.json) are the same misses, key for key
  explained   every miss of the Gate figure's ten shapes (misses-held-freeze.json) is attributed once, to one class, with evidence under the results (or what was tried, for `unexplained`), and is on the page
  verdict     the verdict sentence on the page is the one the figure and the classes give: at least 98% and every miss `emulator bug` or `Windows-only`
  labels      the earlier pages' figure is labelled "not held out" and the dev half's "dev half", on the page
Exit 1 on any failure; with --require-complete, also on anything pending."""
import sys, os, re, json, glob, argparse, subprocess, datetime
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
GATE_THRESHOLD = 0.98      # ADR 0047, Decision 7: at least 98% exact on the ten commonest shapes
PASSING_CLASSES = ('emulator bug', 'Windows-only')      # the Gate's two classes: a miss of any other class (`method`, `unexplained`) does not pass it
FREEZE_OBJECTS = ('emu', 'q3/emulate.py', 'q3/sweep.py', 'q3/livepage.py', 'q3/shapes.py', 'q3/measure.py', 'q3/attribute.py', 'q3/split.py')      # the emulator, its harness and the rules the figure is measured by
TABLE = 'emu/langnames/language-names.json'      # A11-164's table: it is in the emulator before the freeze


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


def check_manifest(path, corpus_path, require_consent=False):
    """One archive per corpus address, once each, each with a sha256; a page recorded with an error status is served as 200, or the worker could not capture it. With `require_consent` (A11-166) each page also has its consent outcome."""
    if not os.path.exists(path): return PENDING, 'no archive manifest yet'
    pages = rb.read_json(path)['pages']; expected = {e if isinstance(e, str) else e['url'] for e in rb.read_json(corpus_path)}; bad = []
    if sorted(p['url'] for p in pages) != sorted(expected): bad.append(f'the manifest is not the {len(expected)} corpus addresses, once each')
    for p in pages:
        if not re.fullmatch(r'[0-9a-f]{64}', str(p.get('sha256'))): bad.append(f'{p.get("url")}: no sha256')
    if len({p.get('archive') for p in pages}) != len(pages): bad.append('two addresses share an archive file')
    if require_consent:
        for p in pages:
            if p.get('consent') not in ('given', 'no-dialog', 'not-matched'): bad.append(f'{p.get("url")}: no consent outcome (given, no-dialog or not-matched)')
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


def gate_misses(misses):
    """The misses of the Gate figure: those of a measure.py --json on the ten shapes of the figure, not in `frames` (the shape ranking reads the channels of the fleet's script), as attribute.py counts them."""
    top = set(misses['top'])
    return [m for m in misses['misses'] if ' + '.join(m['shape']) in top and m['channel'] != 'frames']


def miss_key(page, channel, i, expected): return (page, channel, i, expected)


def check_explained(path, results, doc=None, misses=None):
    """The misses the ticket asks to have explained, each classed as method, emulator bug or Windows-only with evidence that is a file under the results (and, in the write-up, named), or kept `unexplained` with what was
    tried; and every one is on the page. Without `misses`, exactly EXPECTED_MISSES of them (A11-165's eleven). With `misses` (a measure.py --json, the Gate's), every miss of the Gate figure once, and nothing else."""
    if not os.path.exists(path): return PENDING, 'no explanation of the misses yet'
    entries = rb.read_json(path)['misses']; bad = []
    if misses is None:
        if len(entries) != EXPECTED_MISSES: bad.append(f'{len(entries)} misses explained, {EXPECTED_MISSES} asked')
    else:
        wanted = [miss_key(m['url'], m['channel'], m['i'], m['expected']) for m in gate_misses(misses)]
        given = [miss_key(e.get('page'), e.get('channel'), e.get('i'), e.get('expected')) for e in entries]
        if len(wanted) != misses['gate']['total'] - misses['gate']['exact']: bad.append(f'the Gate figure has {misses["gate"]["total"] - misses["gate"]["exact"]} misses and its misses file lists {len(wanted)} on the ten shapes')
        twice = sorted({k for k in given if given.count(k) > 1}); missing = [k for k in wanted if k not in given]; extra = [k for k in given if k not in wanted]
        if twice: bad.append(f'{len(twice)} misses attributed twice, such as {twice[0][0]} {twice[0][1]}[{twice[0][2]}]')
        if missing: bad.append(f'{len(missing)} misses of the Gate figure are not attributed, such as {missing[0][0]} {missing[0][1]}[{missing[0][2]}]')
        if extra: bad.append(f'{len(extra)} attributions are of no miss of the Gate figure, such as {extra[0][0]} {extra[0][1]}[{extra[0][2]}]')
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


def verdict_of(gate, entries):
    """`passed` or `not passed`, by the spike's rule as the Gate section reads it: at least 98% exact and every miss an emulator bug or Windows-only. A miss of any other class (`method`, `unexplained`) fails the Gate, as `visited` did."""
    return 'passed' if gate['total'] and gate['exact'] / gate['total'] >= GATE_THRESHOLD and all(e.get('class') in PASSING_CLASSES for e in entries) else 'not passed'


def last_subsection(doc):
    """The text of the last `### ` subsection of the page's `## Re-measure` section (the one this run adds), or None."""
    lines = read_text(doc).splitlines(); remeasure = next((n for n, l in enumerate(lines) if l.startswith('## Re-measure')), None)
    if remeasure is None: return None
    end = next((n for n in range(remeasure + 1, len(lines)) if lines[n].startswith('## ')), len(lines))
    starts = [n for n in range(remeasure + 1, end) if lines[n].startswith('### ')]
    return '\n'.join(lines[starts[-1]:end]) if starts else None


def check_verdict(misses_path, attributed_path, doc):
    """The Gate is called passed or not passed, in bold, once, in the new subsection, and it is the call the figure and the classes give."""
    if not os.path.exists(misses_path) or not os.path.exists(attributed_path): return PENDING, 'no Gate figure or attribution yet'
    gate = rb.read_json(misses_path)['gate']; entries = rb.read_json(attributed_path)['misses']; verdict = verdict_of(gate, entries)
    section = last_subsection(doc) if doc and os.path.exists(doc) else None
    if section is None: return PENDING, 'the write-up is not written yet'
    sentences = {v: section.count(f'**The Gate is {v}**') for v in ('passed', 'not passed')}
    if sentences[verdict] != 1 or sentences['passed' if verdict == 'not passed' else 'not passed']: return FAIL, f'the figure ({gate["exact"]} of {gate["total"]}) and the classes give "The Gate is {verdict}", and the subsection says: {sentences}'
    return OK, f'**The Gate is {verdict}**: {gate["exact"]} of {gate["total"]} = {100 * gate["exact"] / gate["total"]:.2f}%, {len(entries)} misses: {", ".join(f"{k} {v}" for k, v in sorted(count_classes(entries).items()))}'


def count_classes(entries):
    counts = {}
    for e in entries: counts[e['class']] = counts.get(e['class'], 0) + 1
    return counts


def git(repo, *args):
    done = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def git_ok(repo, *args): return subprocess.run(['git', '-C', repo, *args], capture_output=True).returncode == 0


def instant(stamp):
    """A timestamp as a moment; one with no zone is read as UTC, so two records can always be compared."""
    at = datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    return at if at.tzinfo else at.replace(tzinfo=datetime.timezone.utc)


def capture_times(oracle_dir, summary_path):
    """When each record of the run was captured: from the oracle's records, or, where the oracle's pages are not at hand (they are third-party's), from the committed summary."""
    files = sorted(glob.glob(os.path.join(oracle_dir, '*.json'))) if oracle_dir and os.path.isdir(oracle_dir) else []
    if files: return [rb.read_json(f).get('capturedAt') for f in files]
    return [e.get('capturedAt') for e in rb.read_json(summary_path)] if os.path.exists(summary_path) else None


def freeze_object_problems(freeze, repo, commit):
    """What differs between the objects the freeze names, the frozen commit's and this branch's head, for the emulator, the harness and the rules the figure is measured by; and A11-164's table."""
    bad = []
    for path in FREEZE_OBJECTS:
        named, then, now = (freeze.get('objects') or {}).get(path), git(repo, 'rev-parse', f'{commit}:{path}'), git(repo, 'rev-parse', f'HEAD:{path}')
        if not named: bad.append(f'{path}: not named in the freeze')
        elif named != then: bad.append(f'{path}: the freeze names {named[:10]} but the frozen commit has {str(then)[:10]}')
        elif named != now: bad.append(f'{path} has changed since the freeze ({named[:10]} then, {str(now)[:10]} now)')
    if git(repo, 'rev-parse', f'{commit}:{TABLE}') is None: bad.append(f'{TABLE} (A11-164) is not in the frozen commit')
    return bad


def freeze_history_problems(freeze, repo, commit):
    """The frozen commit is behind this branch, and contains the commits the freeze says it includes (A11-164's merge)."""
    bad = [] if git_ok(repo, 'merge-base', '--is-ancestor', commit, 'HEAD') else ['the frozen commit is not an ancestor of this one']
    for ticket, merge in sorted((freeze.get('includes') or {}).items()):
        if not git_ok(repo, 'merge-base', '--is-ancestor', merge, commit): bad.append(f'{ticket} ({merge[:10]}) is not in the frozen commit')
    if not (freeze.get('includes') or {}).get('A11-164'): bad.append('the freeze does not say it includes A11-164')
    return bad


def freeze_time_problems(freeze, freeze_path, repo, commit, times):
    """The order of the times: the frozen commit, the naming, the commit of freeze.json, then every capture (`times`, or None when there are no records yet)."""
    named_at = instant(freeze['namedAt']); bad = []
    made = git(repo, 'show', '-s', '--format=%cI', commit)
    if made and instant(made) > named_at: bad.append(f'named at {freeze["namedAt"]}, before its commit was made ({made})')
    added = git(repo, 'log', '--diff-filter=A', '--format=%cI', '--', os.path.relpath(os.path.realpath(freeze_path), os.path.realpath(git(repo, 'rev-parse', '--show-toplevel'))))
    committed = added.splitlines()[-1] if added else None
    if committed and instant(committed) < named_at: bad.append(f'freeze.json was committed ({committed}) before it was named ({freeze["namedAt"]})')
    if times is not None:
        early = [t for t in times if not t or instant(t) <= named_at]
        if early: bad.append(f'{len(early)} of {len(times)} captures were made at or before the freeze was named')
        if committed and any(t and instant(t) <= instant(committed) for t in times): bad.append('a capture was made before freeze.json was committed')
    return bad


def check_freeze(freeze_path, repo, oracle_dir=None, summary_path=None):
    """The freeze: a commit of this branch's history, named before any capture of the run, whose emulator and harness are unchanged at this commit and which has A11-164's table."""
    if not os.path.exists(freeze_path): return PENDING, 'no freeze.json yet'
    freeze = rb.read_json(freeze_path); commit = freeze.get('commit')
    if not commit or not git_ok(repo, 'cat-file', '-e', f'{commit}^{{commit}}'): return FAIL, f'the freeze names {commit!r}, which is not a commit of this repository'
    try: instant(freeze['namedAt'])
    except (KeyError, ValueError): return FAIL, 'the freeze has no namedAt'
    times = capture_times(oracle_dir, summary_path)
    bad = freeze_history_problems(freeze, repo, commit) + freeze_object_problems(freeze, repo, commit) + freeze_time_problems(freeze, freeze_path, repo, commit, times)
    if bad: return FAIL, '; '.join(bad[:5])
    if times is None: return PENDING, f'freeze {commit[:10]} is in order; no capture records to compare with it yet'
    return OK, f'frozen at {commit[:10]}, named {freeze["namedAt"]}; emu/ and the harness are unchanged at this commit; {len(times)} captures, all later'


def check_consent(report_path, manifest_path):
    """The consent report is of the manifest's pages, once each, with the outcome the manifest holds; a page that begins in a cookie or consent surface on either side says which side and where."""
    if not os.path.exists(report_path) or not os.path.exists(manifest_path): return PENDING, 'no consent report yet'
    report = rb.read_json(report_path); manifest = {p['url']: p for p in rb.read_json(manifest_path)['pages']}; bad = []
    pages = report['pages']
    if sorted(p['url'] for p in pages) != sorted(manifest): bad.append('the report is not of the manifest\'s addresses, once each')
    for p in pages:
        m = manifest.get(p['url'])
        if m is None: continue
        if m.get('consent') not in ('given', 'no-dialog', 'not-matched'): bad.append(f'{p["url"]}: the manifest has no consent outcome')
        elif p.get('outcome') != m['consent']: bad.append(f'{p["url"]}: the report says {p.get("outcome")}, the manifest {m["consent"]}')
        for side in ('fleet', 'emulator'):
            if p.get(side) is None: bad.append(f'{p["url"]}: no reading of the {side}')
            elif p[side].get('surface') and not p[side].get('lines'): bad.append(f'{p["url"]}: begins in a surface on the {side} and says no line')
    outcomes = {}
    for m in manifest.values(): outcomes[m.get('consent')] = outcomes.get(m.get('consent'), 0) + 1
    if report.get('outcomes') != outcomes: bad.append(f'the report counts {report.get("outcomes")}, the manifest {outcomes}')
    if bad: return FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')
    surfaced = [p for p in pages if (p['fleet'] or {}).get('surface') or (p['emulator'] or {}).get('surface')]
    return OK, f'{len(pages)} pages, outcomes {outcomes}; {len(surfaced)} begin in or contain a cookie or consent surface on a side'


NOT_COMPARABLE_REASONS = ('title spoken differently', 'consent surface', 'consent not matched', 'two runs disagree', 'census differs', 'document differs', 'timeout', 'emulator fault', 'fleet capture incomplete')


def check_comparable(path, misses_path):
    """comparability.json: every page of the Gate's half is comparable or has one reason from the list, and the comparable count is the figure's."""
    if not os.path.exists(path) or not os.path.exists(misses_path): return PENDING, 'no comparability account yet'
    data = rb.read_json(path); misses = rb.read_json(misses_path); bad = []
    status = {p['url']: p['status'] for p in misses['pages']}
    if sorted(p['url'] for p in data['pages']) != sorted(status): bad.append('the account is not of the Gate figure\'s pages, once each')
    for p in data['pages']:
        if p['comparable'] != (status.get(p['url']) == 'comparable'): bad.append(f'{p["url"]}: the account and measure.py disagree on whether it is comparable')
        if not p['comparable'] and p.get('reason') not in NOT_COMPARABLE_REASONS: bad.append(f'{p["url"]}: not comparable, and its reason {p.get("reason")!r} is none of the list')
        if not p['comparable'] and not p.get('detail'): bad.append(f'{p["url"]}: not comparable, and no detail')
    n = sum(1 for p in data['pages'] if p['comparable'])
    if data.get('comparable') != n or data.get('total') != len(data['pages']): bad.append('the counts are not the pages\'')
    if bad: return FAIL, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else '')
    return OK, f'{n} of {len(data["pages"])} pages comparable; {len(data["pages"]) - n} not, each with a reason'


def check_labels(results, doc):
    """On the page, the old pages' figure is on a line that says `not held out` and the dev half's on one that says `dev half`."""
    page = read_text(doc).splitlines(); bad = []; found = 0
    for name, label in (('measure-old60-freeze.txt', 'not held out'), ('measure-dev-freeze.txt', 'dev half')):
        path = os.path.join(results, name)
        if not os.path.exists(path): continue
        line = re.search(r'^GATE: (\d+) of (\d+)', read_text(path), re.M); found += 1
        if not line: bad.append(f'{name}: no GATE line'); continue
        figure = re.compile(r'(?<![\d,])' + re.escape(f'{thousands(line[1])} of {thousands(line[2])}') + r'(?![\d,])')      # `60 of 60` is not found in `160 of 160`
        rows = [l for l in page if figure.search(l)]
        if not rows: bad.append(f'{name}: {thousands(line[1])} of {thousands(line[2])} is not on the page')
        elif not any(label in l for l in rows): bad.append(f'{name}: {thousands(line[1])} of {thousands(line[2])} is on the page, on no line that says "{label}"')
    if not found: return PENDING, 'no figures to label yet'
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{found} labelled figures')


def check_crosswalk(attributed_path, measure_attributed_path, misses_path):
    """The two lists of the Gate figure's misses are one list: the misses `attribute.py` printed (`misses-held-freeze-attributed.json`, with measure.py's own class for each) and the hand attribution (`misses-attributed.json`), key for key
    (page, channel, place in the list, text), each once. A miss in one and not the other, or twice in either, fails."""
    if not all(os.path.exists(f) for f in (attributed_path, measure_attributed_path, misses_path)): return PENDING, 'no attribution to compare with attribute.py\'s list yet'
    figure = rb.read_json(misses_path); top = set(figure['top'])
    key = lambda page, channel, i, expected: (page, channel, i, expected)
    theirs = [key(m['url'], m['channel'], m['i'], m['expected']) for m in rb.read_json(measure_attributed_path) if ' + '.join(m['shape']) in top and m['channel'] != 'frames']
    ours = [key(e['page'], e['channel'], e['i'], e['expected']) for e in rb.read_json(attributed_path)['misses']]
    bad = []
    if len(set(theirs)) != len(theirs) or len(set(ours)) != len(ours): bad.append('a miss is listed twice')
    for label, only in (('attribute.py lists and the attribution lacks', set(theirs) - set(ours)), ('the attribution has and attribute.py does not list', set(ours) - set(theirs))):
        if only: bad.append(f'{len(only)} {label}, such as {sorted(only)[0][0]} {sorted(only)[0][1]}[{sorted(only)[0][2]}]')
    return (FAIL, '; '.join(bad)) if bad else (OK, f'{len(ours)} misses, the same ones in both lists')


def check_gate_explained(results, explained_path, doc):
    """`explained` for the Gate's run: against the Gate figure's own misses file, and pending (not the old eleven) until that file is there."""
    misses = os.path.join(results, 'misses-held-freeze.json')
    if not os.path.exists(misses): return PENDING, 'no Gate figure yet, so no misses to attribute'
    return check_explained(explained_path, results, doc, rb.read_json(misses))


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--results', default='q3/results/remeasure'); ap.add_argument('--oracle'); ap.add_argument('--corpus', default='q3/results/corpus.json'); ap.add_argument('--explained'); ap.add_argument('--control-from', help='another run\'s history-readback.json whose `before` probes show the method (a run that took none of its own)'); ap.add_argument('--doc', default='docs/announcement-emulator-spike.md')
    ap.add_argument('--base', default='origin/main'); ap.add_argument('--require-complete', action='store_true'); ap.add_argument('--replay', action='store_true', help='a scripted-replay run (A11-165): the results hold replay-readback.json, archive-manifest.json, served-identically.json and misses-explained.json, and the oracle\'s records carry a `replay` block')
    ap.add_argument('--gate', action='store_true', help='the Gate on new pages (A11-166): with --replay, the results hold freeze.json, consent-report.json, comparability.json, misses-held-freeze.json and misses-attributed.json, and the manifest carries each page\'s consent outcome'); ap.add_argument('--repo', default='.'); a = ap.parse_args(argv)
    if a.gate: a.replay = True      # the Gate's run is a replay run: --gate alone would run none of its checks
    readback = os.path.join(a.results, 'history-readback.json')
    results = [('readback', check_readback(readback, a.control_from)), ('summary', check_summary(os.path.join(a.results, 'oracle-summary.json'), readback, a.corpus)), ('oracle', check_oracle(a.oracle, readback, a.corpus, a.explained or os.path.join(a.results, 'visited-explained.json'))), ('figures', check_figures(a.results, a.doc)),
               ('addresses', check_addresses([a.results, a.doc])), ('doc', check_doc(a.doc, a.base))]
    if a.replay:
        manifest = os.path.join(a.results, 'archive-manifest.json'); explained = os.path.join(a.results, 'misses-attributed.json' if a.gate else 'misses-explained.json'); misses = os.path.join(a.results, 'misses-held-freeze.json')
        results += [('replay-readback', check_replay_readback(os.path.join(a.results, 'replay-readback.json'))), ('manifest', check_manifest(manifest, a.corpus, require_consent=a.gate)), ('replay-stamps', check_replay_stamps(a.oracle, manifest, os.path.join(a.results, 'replay-readback.json'))),
                    ('served', check_served(os.path.join(a.results, 'served-identically.json'), manifest)), ('explained', check_gate_explained(a.results, explained, a.doc) if a.gate else check_explained(explained, a.results, a.doc))]
        if a.gate:
            results += [('freeze', check_freeze(os.path.join(a.results, 'freeze.json'), a.repo, a.oracle, os.path.join(a.results, 'oracle-summary.json'))), ('consent', check_consent(os.path.join(a.results, 'consent-report.json'), manifest)),
                        ('comparable', check_comparable(os.path.join(a.results, 'comparability.json'), misses)), ('crosswalk', check_crosswalk(explained, os.path.join(a.results, 'misses-held-freeze-attributed.json'), misses)), ('verdict', check_verdict(misses, explained, a.doc)), ('labels', check_labels(a.results, a.doc))]
    for name, (state, msg) in results: print(f'{state:>8}  {name}: {msg}')
    states = {s for _, (s, _) in results}
    sys.exit(1 if FAIL in states or (a.require_complete and PENDING in states) else 0)


if __name__ == '__main__': main(sys.argv[1:])
