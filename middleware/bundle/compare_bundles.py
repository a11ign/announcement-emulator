#!/usr/bin/env python3
"""The proofs that the lean bundle (A11-231) changes nothing a user sees.

    python3 compare_bundles.py replay <layout> [<layout>] [--trace <file>] [--fixtures <dir>] [--jobs <n>]
    python3 compare_bundles.py misses --full <layout> --lean <layout> --full-trace <file> --lean-trace <file>

`replay` runs every recorded session under the fixtures directory, found recursively (*.jsonl.gz), through the layout's own Python and replay.py, with sweeps, without them, and with --report-focus. --trace
(import_trace.py) records the first layout's runs. Given two layouts it compares each pair of outputs byte for byte and fails on any difference, naming the recording, the flags and the first record that differs. The one thing it leaves out of the comparison
is the clock: replay.py also measures how long each step took (`ms` in a record; `speechMs` and `sweepMs` in the stats), and two runs of the same layout differ in those.

`misses` reads the traces (import_trace.py) of one run of the lean bundle and one run of the full layout, and fails on what the lean run wanted and could not find and the full layout has: an import that
no finder could satisfy, a file it opened that is not there. What the full layout lacks too, such as NVDA's Windows-only modules, which q2/stubs.py stands in for, is not a miss.
A trace that missed a module therefore fails here, in CI, and not for a user.
"""
import argparse, concurrent.futures, json, os, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import keep as keep_lists

FIXTURES = HERE.parent / 'runtime' / 'fixtures'
MODES = [(), ('--no-sweeps',), ('--report-focus',)]
CLOCK = {'ms', 'speechMs', 'sweepMs'}      # how long a step took: measured, so never the same twice
TIMEOUT = 300


def recordings(directory):
    return sorted(pathlib.Path(directory).rglob('*.jsonl.gz'))


def replay(layout, recording, flags, trace=None):
    """The output of replay.py over `recording` in the bundle or layout at `layout`, as text."""
    layout = pathlib.Path(layout).resolve()
    env = {**os.environ, 'EMU_DOWNLOADS': str(layout), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}      # as runtime.ts starts it: the run leaves no cache in the bundle
    if trace: env['ANNOUNCEMENT_EMULATOR_IMPORT_TRACE'] = str(trace)
    ran = subprocess.run([str(layout / 'python' / 'bin' / 'python3'), '-I', str(layout / 'middleware' / 'runtime' / 'replay.py'), str(recording), *flags], capture_output=True, text=True, env=env, timeout=TIMEOUT)
    if ran.returncode: raise RuntimeError(f'{layout.name}: replay of {recording.name} {" ".join(flags)} exited {ran.returncode}: {ran.stderr[-1500:]}')
    return ran.stdout


def without_clock(value):
    if isinstance(value, dict): return {k: without_clock(v) for k, v in value.items() if k not in CLOCK}
    if isinstance(value, list): return [without_clock(v) for v in value]
    return value


def transcript(output):
    """The replay's output with the clock left out, as the bytes that are compared."""
    return json.dumps(without_clock(json.loads(output)), ensure_ascii=False, separators=(',', ':'))


def first_difference(a, b):
    """Where two transcripts first differ, in words."""
    x, y = json.loads(a), json.loads(b)
    for index, (p, q) in enumerate(zip(x['records'], y['records'])):
        if p != q:
            fields = [k for k in sorted(set(p) | set(q)) if p.get(k) != q.get(k)]
            return f'record {index} differs in {fields}: {json.dumps({k: p.get(k) for k in fields})[:300]} against {json.dumps({k: q.get(k) for k in fields})[:300]}'
    if len(x['records']) != len(y['records']): return f'{len(x["records"])} records against {len(y["records"])}'
    return f'the stats differ: {x["stats"]} against {y["stats"]}'


def compare_replays(first, second, directory, trace=None, jobs=4):
    """Replay every recording in both layouts; returns the failures, each a line. With one layout, `second` is None and the replays are only run."""
    layouts = [l for l in (first, second) if l]
    traces = [trace, None]      # the first layout's runs are the ones traced: it is the full layout, whose reads decide what the lean one keeps
    work = [(r, flags) for r in recordings(directory) for flags in MODES]
    failures, runs = [], 0

    def one(item):
        recording, flags = item
        return item, [transcript(replay(layout, recording, flags, traces[i])) for i, layout in enumerate(layouts)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(one, item) for item in work]
        for future in futures:
            try: (recording, flags), outputs = future.result()
            except Exception as error: failures.append(str(error)); continue
            runs += 1
            if len(outputs) == 2 and outputs[0] != outputs[1]:
                failures.append(f'{recording.relative_to(directory)} {" ".join(flags) or "(with sweeps)"}: {first_difference(*outputs)}')
    return failures, runs


def exists_in(layout, rel):
    """Whether the layout has a file, counting a standard-library module that ships as its .pyc alone."""
    path = pathlib.Path(layout) / rel
    return path.exists() or os.path.lexists(path) or (rel.endswith('.py') and pathlib.Path(str(path) + 'c').exists())


def misses(full, lean, full_trace, lean_trace):
    """What the lean run wanted that it did not find and the full layout has: (imports, files)."""
    for trace in (full_trace, lean_trace):
        if not os.path.exists(trace): raise SystemExit(f'{trace}: no trace was written (the run did not start, or tracing was off)')
    lean_files, lean_missing = keep_lists.read_trace(lean_trace)
    _, full_missing = keep_lists.read_trace(full_trace)
    imports = sorted(lean_missing - full_missing)
    files = sorted(f for f in lean_files if keep_lists.wanted(f) and not exists_in(lean, f) and exists_in(full, f))
    return imports, files


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='mode', required=True)
    r = sub.add_parser('replay'); r.add_argument('layouts', nargs='+'); r.add_argument('--trace'); r.add_argument('--fixtures', default=str(FIXTURES)); r.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    m = sub.add_parser('misses'); [m.add_argument(f'--{n}', required=True) for n in ('full', 'lean', 'full-trace', 'lean-trace')]
    args = parser.parse_args(argv[1:])
    if args.mode == 'replay':
        if len(args.layouts) > 2: parser.error('one layout to run, or two to compare')
        failures, runs = compare_replays(args.layouts[0], args.layouts[1] if len(args.layouts) == 2 else None, pathlib.Path(args.fixtures), args.trace, args.jobs)
        for line in failures: print(line, file=sys.stderr)
        print(f'{runs} replays over {len(recordings(args.fixtures))} recordings' + (f', {"byte-identical" if not failures else str(len(failures)) + " differ or failed"}' if len(args.layouts) == 2 else ''))
        return 1 if failures else 0
    imports, files = misses(args.full, args.lean, getattr(args, 'full_trace'), getattr(args, 'lean_trace'))
    for name in imports: print(f'import the lean bundle lacks: {name}', file=sys.stderr)
    for name in files: print(f'file the lean bundle lacks: {name}', file=sys.stderr)
    print('no import and no file the lean bundle lacks and the full layout has' if not (imports or files) else f'{len(imports)} imports and {len(files)} files are missing from the lean bundle: run middleware/bundle/trace.sh')
    return 1 if imports or files else 0


if __name__ == '__main__': sys.exit(main(sys.argv))
