"""A tar of a directory, compressed as .gz, .xz or .zst by its name, that is the same bytes whenever it is made from the same files: entries sorted, owners and times fixed, the gzip header without a name
or a time, xz and zstd on one thread.

    python3 mktar.py <directory> <out.tar.gz | out.tar.xz | out.tar.zst>

The runtime bundle is built in CI and its sha256 is pinned in the package that downloads it; if two builds of one commit differ, the pin means nothing. xz is Python's own (preset 9, extreme); zstd is the
`zstd` program at -19 with a 128 MiB window (--long=27, which a decoder takes without being told), whose version `zstd --version` names: the same program makes the same bytes.
"""
import contextlib, gzip, lzma, os, stat, subprocess, sys, tarfile

MTIME = 1767225600      # 2026-01-01T00:00:00Z


def entries(root):
    out = []
    for here, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs + files):
            out.append(os.path.relpath(os.path.join(here, name), root))
    return sorted(out)


def normalise(info):
    info.uid = info.gid = 0; info.uname = info.gname = ''; info.mtime = MTIME
    if info.isdir(): info.mode = 0o755
    elif info.isreg(): info.mode = 0o755 if info.mode & stat.S_IXUSR else 0o644
    return info


@contextlib.contextmanager
def compressed(out):
    """A binary stream whose bytes are written to `out` compressed as its extension says."""
    with open(out, 'wb') as raw:
        if out.endswith('.gz'):
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as stream: yield stream
        elif out.endswith('.xz'):
            with lzma.LZMAFile(raw, 'wb', format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=9 | lzma.PRESET_EXTREME) as stream: yield stream
        elif out.endswith('.zst'):
            process = subprocess.Popen(['zstd', '-q', '-c', '-19', '--long=27', '-T1'], stdin=subprocess.PIPE, stdout=raw)
            try: yield process.stdin
            finally:
                process.stdin.close()
                if process.wait(): raise RuntimeError('zstd failed')
        else: raise ValueError(f'{out}: not .gz, .xz or .zst')


def make(root, out):
    with compressed(out) as stream, tarfile.open(fileobj=stream, mode='w|', format=tarfile.GNU_FORMAT) as tar:
        for rel in entries(root):
            path = os.path.join(root, rel)
            info = normalise(tar.gettarinfo(path, arcname=rel))
            if info.isreg():
                with open(path, 'rb') as f: tar.addfile(info, f)
            else: tar.addfile(info)


if __name__ == '__main__': make(sys.argv[1], sys.argv[2])
