"""Q2 harness: import NVDA's own Python on Linux, stubbing only what is missing, and keep a ledger of every stub."""
import sys, types, importlib, importlib.abc, importlib.machinery, ctypes, os
LEDGER = []

class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith('__') and name.endswith('__'): raise AttributeError(name)
        return _make(f'{cls.__name__}.{name}')
    def __call__(cls, *a, **k): return object.__new__(cls) if False else super().__call__()
    def __getitem__(cls, i): return cls
    def __iter__(cls): return iter(())
    def __or__(cls, o): return cls
    def __ror__(cls, o): return cls
    def __bool__(cls): return True
    def __int__(cls): return 0
    def __index__(cls): return 0
    def __hash__(cls): return id(cls)

def _make(name):
    class Stub(metaclass=_Meta):
        def __init__(self, *a, **k): pass
        def __getattr__(self, n):
            if n.startswith('__') and n.endswith('__'): raise AttributeError(n)
            return _make(f'{type(self).__name__}.{n}')
        def __call__(self, *a, **k): return self
        def __iter__(self): return iter(())
        def __getitem__(self, i): return self
        def __bool__(self): return False
        def __int__(self): return 0
        def __index__(self): return 0
        def __or__(self, o): return self
        __ror__ = __or__
    Stub.__name__ = name; Stub.__qualname__ = name
    return Stub

class StubModule(types.ModuleType):
    __path__ = []
    def __getattr__(self, n):
        if n.startswith('__') and n.endswith('__'): raise AttributeError(n)
        v = _make(f'{self.__name__}.{n}'); setattr(self, n, v); return v

class StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, names): self.names = set(names)
    def find_spec(self, fullname, path, target=None):
        if fullname.split('.')[0] in self.names or fullname in self.names:
            LEDGER.append(fullname)
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
    def create_module(self, spec): return StubModule(spec.name)
    def exec_module(self, module): pass

def install(names):
    sys.meta_path.insert(0, StubFinder(names))
    # ctypes Windows surface that does not exist on Linux
    for n in ('windll', 'oledll', 'WinDLL', 'OleDLL', 'WINFUNCTYPE', 'WinError', 'FormatError', 'GetLastError', 'HRESULT', 'GetLastError', 'get_last_error', 'set_last_error'):
        if not hasattr(ctypes, n): setattr(ctypes, n, _make('ctypes.' + n)); LEDGER.append('ctypes.' + n)
