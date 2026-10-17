"""winUser for the emulator: NVDA's own integer constants (parsed from source/winUser.py, which otherwise binds to user32), and the few
window queries NVDAObjects makes, answered for a single Chrome renderer window. This is layer 0/5 territory: a fixed answer, not a measurement."""
import ast, types, pathlib
SRC = pathlib.Path.home() / 'spikes/announcement-emulator-5661/nvda-src/source/winUser.py'
import stubs
m = stubs.StubModule('winUser')
for node in ast.parse(SRC.read_text()).body:
    if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Constant, ast.UnaryOp)):
        try:
            v = ast.literal_eval(node.value)
            for t in node.targets:
                if isinstance(t, ast.Name) and isinstance(v, (int, str)): setattr(m, t.id, v)
        except Exception: pass
HWND = 0x1000
m.getClassName = lambda w: 'Chrome_RenderWidgetHostHWND'
m.getWindowText = lambda w: ''
m.getControlID = lambda w: 0
m.getWindowThreadProcessID = lambda w: (1, 1)
m.isWindow = lambda w: True
m.isWindowVisible = lambda w: True
m.isWindowEnabled = lambda w: True
m.getForegroundWindow = lambda: HWND
m.getAncestor = lambda w, f: w
m.getWindowStyle = lambda w: 0x10000000
m.getFocus = lambda: HWND
m.user32 = types.SimpleNamespace()
m._cursor = [0, 0]
m.getCursorPos = lambda: tuple(m._cursor)      # NVDA's mouse-click fallback for activating an object (browseMode._activateNVDAObject); no pointer here
m.setCursorPos = lambda x, y: m._cursor.__setitem__(slice(0, 2), [int(x), int(y)])
