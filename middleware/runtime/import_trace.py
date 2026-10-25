"""What a run of the runtime read from its bundle (A11-231): the lean bundle holds only that, so a run is traced to decide what it keeps, and traced again to prove nothing is missing.

Off unless ANNOUNCEMENT_EMULATOR_IMPORT_TRACE=<file> is set, and then it costs one audit hook. main.py and replay.py call `install()` before NVDA boots; any other Python process is traced by a
sitecustomize.py that calls it (bundle/trace.sh).

The file gets one line per fact, appended whole (several processes may write the same file):
    file <path>       a module's file, or a file opened, under the bundle's root (nvda-appdir is written as the nvda-src/source it copies)
    missing <name>    an import no finder could satisfy (NVDA wraps optional imports in `except ImportError`, which would hide a module the bundle lacks)
Paths are relative to the root: EMU_DOWNLOADS, else the directory that holds middleware/runtime.
"""
import atexit, os, sys

ENV = 'ANNOUNCEMENT_EMULATOR_IMPORT_TRACE'
APPDIR, SOURCE = 'nvda-appdir', 'nvda-src/source'      # the overlay boot.py gives NVDA as its appDir in a full layout, and the tree it copies


def default_root():
    return os.environ.get('EMU_DOWNLOADS') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def relative(path, root):
    """`path` as a bundle-relative path with forward slashes, or None when it is not under `root`. nvda-appdir/x is nvda-src/source/x, so that a full layout and a lean one name the same file alike."""
    if isinstance(path, bytes): path = os.fsdecode(path)
    if not isinstance(path, str) or not path: return None
    path = os.path.abspath(path)
    if path != root and not path.startswith(root + os.sep): return None
    rel = os.path.relpath(path, root).replace(os.sep, '/')
    if rel == APPDIR or rel.startswith(APPDIR + '/'): rel = SOURCE + rel[len(APPDIR):]
    return rel


class Trace:
    def __init__(self, out, root):
        self.out, self.roots = out, sorted({os.path.abspath(root), os.path.realpath(root)})      # a root may be reached through a link (/tmp is /private/tmp on macOS)
        self.files, self.missing = set(), set()
        self.busy = False      # the hook's own reads are not the run's

    def add(self, into, path):
        if isinstance(path, bytes): path = os.fsdecode(path)
        if not isinstance(path, str) or not path or path.startswith('<'): return      # '<unknown>', '<frozen os>': a name and not a file
        for candidate in (os.path.abspath(path), os.path.realpath(path)):
            rel = next((r for r in (relative(candidate, root) for root in self.roots) if r), None)
            if rel: into.add(rel); return

    def audit(self, event, args):
        if self.busy: return
        self.busy = True
        try:
            if event == 'open':
                if isinstance(args[0], (str, bytes)): self.add(self.files, args[0])
            elif event == 'ctypes.dlopen':
                if isinstance(args[0], str): self.add(self.files, args[0])
        finally: self.busy = False

    def modules(self):
        for module in list(sys.modules.values()):
            spec = getattr(module, '__spec__', None)
            for path in (getattr(module, '__file__', None), getattr(spec, 'origin', None)):
                if isinstance(path, str) and os.path.isabs(path): self.add(self.files, path)

    def flush(self):
        if self.busy: return
        self.busy = True
        try:
            self.modules()
            lines = [f'file {p}' for p in sorted(self.files)] + [f'missing {n}' for n in sorted(self.missing)]
            data = ('\n'.join(lines) + '\n').encode()
            fd = os.open(self.out, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try: os.write(fd, data)
            finally: os.close(fd)
        finally: self.busy = False


class LastFinder:
    """The last finder on sys.meta_path: asked only for what every other finder could not find, which it records and does not find either."""
    def __init__(self, trace): self.trace = trace

    def find_spec(self, name, path=None, target=None):
        self.trace.missing.add(name)
        return None


_active = None


def install(out=None, root=None):
    """Start tracing if `out` (default: the environment's) names a file. Returns the Trace, or None when tracing is off. Calling it again returns the same one."""
    global _active
    out = out or os.environ.get(ENV)
    if not out: return None
    if _active: return _active
    trace = _active = Trace(out, root or default_root())
    trace.modules()      # what the interpreter imported before this ran: site, encodings, the frozen os and io
    sys.addaudithook(trace.audit)
    sys.meta_path.append(LastFinder(trace))
    atexit.register(trace.flush)
    return trace

