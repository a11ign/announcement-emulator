"""A tar.gz of a directory that is the same bytes whenever it is made from the same files: entries sorted, owners and times fixed, the gzip header without a name or a time.

    python3 mktar.py <directory> <out.tar.gz>

The runtime bundle is built in CI and its sha256 is pinned in the package that downloads it; if two builds of one commit differ, the pin means nothing.
"""
import gzip, os, stat, sys, tarfile

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


def make(root, out):
    with open(out, 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as gz, tarfile.open(fileobj=gz, mode='w', format=tarfile.GNU_FORMAT) as tar:
        for rel in entries(root):
            path = os.path.join(root, rel)
            info = normalise(tar.gettarinfo(path, arcname=rel))
            if info.isreg():
                with open(path, 'rb') as f: tar.addfile(info, f)
            else: tar.addfile(info)


if __name__ == '__main__': make(sys.argv[1], sys.argv[2])
