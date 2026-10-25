#!/usr/bin/env python3
"""What the runtime bundle weighs, by part and by compression (A11-231). Markdown on stdout, so that CI can write it to the job summary.

    python3 sizes.py table <unpacked bundle> [--archive <file>] [--column <label>=<unpacked directory>]...
    python3 sizes.py formats <unpacked bundle> [--json <file>] [--keep <directory>]
    python3 sizes.py choose <formats json>... [--container <format>=ok|failed]...

`table`: the unpacked size of each part, beside the spike's (A11-208, docs/playwright-middleware-spike.md, Q7) and each --column (another bundle, unpacked: A11-230's, which had no browser). Sizes are the
bytes of the files (what `ls -l` adds up), in MB of 10^6 bytes.
`formats`: packs the bundle as gz, xz and zst with mktar.py, and for each gives the archive's bytes and the median of 3 unpacks by the host's `tar -xf` (the unpack `install` does). --keep leaves the
archives, as bundle.tar.<format>, in a directory (CI unpacks them in a plain ubuntu:24.04 container).
`choose`: the format the bundle ships in. A format is acceptable when, on every platform given, its unpack took UNPACK_SECONDS or less and `tar -xf` unpacked it to the same files, and, where --container
says, a plain ubuntu:24.04 container's tar unpacked it too. The smaller acceptable one of xz and zst wins; gzip is only the baseline.
"""
import argparse, json, os, pathlib, shutil, statistics, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mktar

MB = 1_000_000
UNPACK_SECONDS = 5.0
RUNS = 3
FORMATS = ('gz', 'xz', 'zst')
CHOOSABLE = ('xz', 'zst')
# The spike's bundle (A11-208, Q7): unpacked MB by part, and the archive as tar.gz in MB, for each platform. Its Python was the full install-only build, its NVDA source and a second copy of it as the overlay.
SPIKE = {'Chrome': 400, 'Browser libraries': 11, 'Python': 278, 'NVDA': 149, 'Total': 838, 'Archive': {'linux-x64': 298, 'darwin-arm64': 242}}


def size_of(path):
    """The bytes of the files under `path` (links count as links), or of the one file."""
    path = pathlib.Path(path)
    if not path.exists() and not path.is_symlink(): return 0
    if path.is_file() or path.is_symlink(): return path.lstat().st_size
    return sum(f.lstat().st_size for f in path.rglob('*') if f.is_file() or f.is_symlink())


def parts(root):
    """The bytes of each part of an unpacked bundle."""
    root = pathlib.Path(root)
    lib = next(iter(sorted((root / 'python' / 'lib').glob('python3.*'))), None)
    packages = size_of(lib / 'site-packages') if lib else 0
    python_total = size_of(root / 'python')
    standard_library = (size_of(lib) - packages) if lib else 0
    extension = size_of(root / 'emu' / 'ext2') + size_of(root / 'q1' / 'ext-id.txt')
    runtime = sum(size_of(root / d) for d in ('emu', 'q1', 'q2', 'q3', 'middleware')) - extension
    nvda = sum(size_of(root / d) for d in ('nvda-src', 'nvda-appdir', 'cldr-src'))
    browser = size_of(root / 'chrome')
    libraries = size_of(root / 'libs')
    total = size_of(root)
    interpreter = python_total - standard_library - packages
    rest = total - python_total - nvda - runtime - extension - browser - libraries
    return {'Chrome': browser, 'Browser libraries': libraries, 'Python: interpreter and its libraries': interpreter, 'Python: standard library': standard_library, 'Python: packages': packages,
            'NVDA': nvda, 'Chromium sources': size_of(root / 'chromium-src'), 'Runtime (this repository)': runtime, 'Companion extension': extension, 'The rest': rest - size_of(root / 'chromium-src'), 'Total': total}


def mb(n): return '-' if n is None else f'{n / MB:.1f}'


def table(root, archive=None, columns=()):
    ours = parts(root)
    others = [(label, parts(path)) for label, path in columns]
    python = lambda p: p['Python: interpreter and its libraries'] + p['Python: standard library'] + p['Python: packages']
    header = ['Part (MB unpacked)', 'Spike', *[l for l, _ in others], 'This bundle']
    rows = []

    def add(name, spike, getter):
        rows.append([name, mb(spike * MB if spike is not None else None), *[mb(getter(p)) for _, p in others], mb(getter(ours))])

    add('Chrome', SPIKE['Chrome'], lambda p: p['Chrome']); add('Browser libraries', SPIKE['Browser libraries'], lambda p: p['Browser libraries'])
    add('Python', SPIKE['Python'], python)
    for name in ('Python: interpreter and its libraries', 'Python: standard library', 'Python: packages'): add('&nbsp;&nbsp;' + name.split(': ')[1], None, lambda p, n=name: p[n])
    add('NVDA (source, and the overlay in the spike)', SPIKE['NVDA'], lambda p: p['NVDA']); add('Chromium sources', None, lambda p: p['Chromium sources'])
    add('Runtime (this repository)', None, lambda p: p['Runtime (this repository)']); add('Companion extension', None, lambda p: p['Companion extension']); add('The rest', None, lambda p: p['The rest'])
    add('**Total unpacked**', SPIKE['Total'], lambda p: p['Total'])
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)] + ['| ' + ' | '.join(r) + ' |' for r in rows]
    if archive: out += ['', f'Archive: {os.path.basename(archive)}, {mb(size_of(archive))} MB (the spike: {SPIKE["Archive"]["linux-x64"]} MB on linux-x64 and {SPIKE["Archive"]["darwin-arm64"]} MB on darwin-arm64, as tar.gz).']
    return '\n'.join(out)


def unpack_once(archive, into):
    start = time.perf_counter()
    ran = subprocess.run(['tar', '-xf', archive, '-C', into], capture_output=True, text=True)
    return time.perf_counter() - start, ran.returncode == 0


def measure(bundle, formats=FORMATS, keep=None):
    """Each format's archive bytes and median unpack time with the host's tar. A format whose tooling the host lacks is left out."""
    out = []
    with tempfile.TemporaryDirectory() as work:
        for fmt in formats:
            if fmt == 'zst' and not shutil.which('zstd'): continue
            archive = os.path.join(work, f'bundle.tar.{fmt}')
            start = time.perf_counter(); mktar.make(str(bundle), archive); packed = time.perf_counter() - start
            times, same = [], True
            for _ in range(RUNS):
                target = os.path.join(work, 'unpacked'); os.makedirs(target)
                seconds, ok = unpack_once(archive, target)
                times.append(seconds); same = same and ok and size_of(target) == size_of(bundle)
                shutil.rmtree(target)
            if keep: os.makedirs(keep, exist_ok=True); shutil.copyfile(archive, os.path.join(keep, f'bundle.tar.{fmt}'))
            out.append({'format': fmt, 'bytes': os.path.getsize(archive), 'unpackSeconds': round(statistics.median(times), 3), 'packSeconds': round(packed, 1), 'tarUnpacksIt': same})
    return out


def acceptable(platforms, containers=None):
    """The formats every platform's measurements and the container check accept: {format: reason it was refused or None}."""
    verdicts = {}
    for fmt in FORMATS:
        reason = None
        for platform, measurements in platforms.items():
            m = next((x for x in measurements if x['format'] == fmt), None)
            if m is None: reason = f'not measured on {platform}'
            elif m['unpackSeconds'] > UNPACK_SECONDS: reason = f'{m["unpackSeconds"]} s to unpack on {platform}, over {UNPACK_SECONDS} s'
            elif not m['tarUnpacksIt']: reason = f"the host's tar did not unpack it on {platform}"
            if reason: break
        if reason is None and containers and containers.get(fmt) == 'failed': reason = "a plain ubuntu:24.04 container's tar did not unpack it"
        verdicts[fmt] = reason
    return verdicts


def choose(platforms, containers=None):
    """(the format to ship in, the markdown table that shows why)."""
    verdicts = acceptable(platforms, containers)
    total = lambda fmt: sum(next(x['bytes'] for x in ms if x['format'] == fmt) for ms in platforms.values() if any(x['format'] == fmt for x in ms))
    winners = [f for f in CHOOSABLE if verdicts[f] is None]
    winner = min(winners, key=total) if winners else None
    names = list(platforms)
    lines = ['| format | ' + ' | '.join(f'{p} MB | {p} unpack s' for p in names) + ' | accepted |', '|' + '---|' * (2 + 2 * len(names))]
    for fmt in FORMATS:
        cells = []
        for p in names:
            m = next((x for x in platforms[p] if x['format'] == fmt), None)
            cells += [mb(m['bytes']) if m else '-', str(m['unpackSeconds']) if m else '-']
        verdict = ('baseline only' if fmt not in CHOOSABLE else ('**ships**' if fmt == winner else 'yes, larger') if verdicts[fmt] is None else f'no: {verdicts[fmt]}')
        lines.append(f'| {fmt} | ' + ' | '.join(cells) + f' | {verdict} |')
    return winner, '\n'.join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='mode', required=True)
    t = sub.add_parser('table'); t.add_argument('bundle'); t.add_argument('--archive'); t.add_argument('--column', action='append', default=[])
    f = sub.add_parser('formats'); f.add_argument('bundle'); f.add_argument('--json'); f.add_argument('--keep')
    c = sub.add_parser('choose'); c.add_argument('files', nargs='+'); c.add_argument('--container', action='append', default=[])
    args = parser.parse_args(argv[1:])
    if args.mode == 'table':
        print(table(args.bundle, args.archive, [tuple(x.split('=', 1)) for x in args.column]))
    elif args.mode == 'formats':
        measurements = measure(args.bundle, keep=args.keep)
        if args.json: pathlib.Path(args.json).write_text(json.dumps(measurements, indent=1))
        print('| format | archive MB | unpack s (median of 3, tar -xf) | pack s |\n|---|---|---|---|')
        for m in measurements: print(f'| {m["format"]} | {mb(m["bytes"])} | {m["unpackSeconds"]} | {m["packSeconds"]} |')
    else:
        platforms = {pathlib.Path(p).stem: json.loads(pathlib.Path(p).read_text()) for p in args.files}
        winner, text = choose(platforms, dict(x.split('=', 1) for x in args.container))
        print(text); print(f'\nships: {winner}')
        return 0 if winner else 1
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv))
