#!/usr/bin/env python3
"""python3 middleware/bundle/keep.py <keep file> [--layout <dir>] [--only <prefix>] [--also <keep file>]... <trace>...

Makes keep/<platform>.txt (A11-231) from the traces runs wrote (import_trace.py): the union of the files they read from the two parts of the bundle that lean.py prunes, python/ and nvda-src/, one
bundle-relative path to a line, sorted. --layout drops a file the full layout at <dir> lacks (a run asks for files that are not there, such as nvda-src/.git/HEAD, and NVDA's own system tests read the
test harness that is not shipped); --only keeps the paths under a prefix; --also adds the lines of another keep file.

Fails when a run read a file of a part the lean bundle does not have (nvda-appdir is nvda-src/source, which import_trace.py has already folded in; cldr-src and chromium-src are not): that is a
run reading what the bundle was to leave out, and the file would be missing for a user.
"""
import argparse, os, sys

PRUNED = ('python/', 'nvda-src/')
NOT_SHIPPED = ('cldr-src/', 'chromium-src/')


def read_trace(path):
    """(the files, the names no finder could find) a trace file holds."""
    files, missing = set(), set()
    with open(path) as f:
        for line in f:
            kind, _, value = line.rstrip('\n').partition(' ')
            if kind == 'file': files.add(value)
            elif kind == 'missing': missing.add(value)
    return files, missing


def wanted(rel):
    """Whether a file a run read is one the lean bundle may need to keep. The caches are made by the interpreter and the .pyc by the compile (lean.py ships the .pyc of a module that is kept)."""
    return rel.startswith(PRUNED) and '/__pycache__/' not in rel and not rel.endswith('.pyc')


def collect(traces, layout=None, only=''):
    """(the sorted keep list, the files read that the lean bundle does not ship)."""
    keep, unshipped = set(), set()
    for path in traces:
        files, _ = read_trace(path)
        keep |= {f for f in files if wanted(f) and f.startswith(only) and (layout is None or os.path.lexists(os.path.join(layout, f)))}
        unshipped |= {f for f in files if f.startswith(NOT_SHIPPED)}
    return sorted(keep), sorted(unshipped)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('out'); parser.add_argument('traces', nargs='+'); parser.add_argument('--layout'); parser.add_argument('--only', default=''); parser.add_argument('--also', action='append', default=[])
    args = parser.parse_args(argv[1:])
    keep, unshipped = collect(args.traces, args.layout, args.only)
    for name in unshipped: print(f'read at run time, and not in the lean bundle: {name}', file=sys.stderr)
    if unshipped: return 1
    for path in args.also:
        with open(path) as f: keep += [l.strip() for l in f if l.strip() and (args.layout is None or os.path.lexists(os.path.join(args.layout, l.strip())))]
    with open(args.out, 'w') as f: f.write('\n'.join(sorted(set(keep))) + '\n')
    print(f'{args.out}: {len(set(keep))} files')
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv))
