"""Generate role/state tables for the stand-in from the real sources (not from memory):
 - Chromium 155.0.8059.84 ax_platform_node_win.cc  (MSAARole, ComputeIA2Role)
 - Chromium third_party/iaccessible2/ia2_api_all.idl (IA2_ROLE_*, IA2_STATE_* values)
 - NVDA release-2026.1.1 source/oleacc.py (ROLE_SYSTEM_*, STATE_SYSTEM_* values)"""
import re, json, ast, pathlib
R = pathlib.Path.home() / 'spikes/announcement-emulator-5661'
cc = (R / 'chromium-src/ax_platform_node_win.cc').read_text().splitlines()

def func_range(sig):
    start = next(i for i, l in enumerate(cc) if sig in l and l.startswith('int'))
    end = next(i for i in range(start + 1, len(cc)) if cc[i] == '}')
    return start, end

def camel(k):  # kHeading -> heading (chrome.automation role string)
    return k[1].lower() + k[2:]

def parse(sig, assign_re):
    s, e = func_range(sig)
    table, pending, cond = {}, [], set()
    for l in cc[s:e]:
        m = re.search(r'case ax::mojom::Role::(k\w+):', l)
        if m: pending.append(m.group(1)); continue
        m = re.search(assign_re, l)
        if m:
            for p in pending: table[camel(p)] = m.group(1)
            pending = []; continue
        if l.strip() in ('break;', 'default:') or l.strip().startswith('return'):
            pending = [] if not l.strip().startswith('return') else pending
            if l.strip().startswith('return'): pending = []
    return table

msaa = parse('AXPlatformNodeWin::MSAARole()', r'return (ROLE_SYSTEM_\w+);')
ia2 = parse('AXPlatformNodeWin::ComputeIA2Role()', r'(?:ia2_role = |return )(IA2_ROLE_\w+|ROLE_SYSTEM_\w+)')

# IA2 constants from the IDL (enum members without '=' are previous+1)
idl = pathlib.Path(R / 'chromium-src/ia2_api_all.idl').read_text()
idl = re.sub(r'/\*.*?\*/', '', idl, flags=re.S); idl = re.sub(r'//[^\n]*', '', idl)
ia2_role_vals = {}
m = re.search(r'enum IA2Role\s*\{(.*?)\}', idl, flags=re.S)
cur = -1
for item in m.group(1).split(','):
    item = item.strip()
    if not item: continue
    if '=' in item:
        n, v = [x.strip() for x in item.split('=')]; cur = int(v, 0)
    else:
        n = item; cur += 1
    ia2_role_vals[n] = cur
ia2_state_vals = {n: int(v, 0) for n, v in re.findall(r'(IA2_STATE_\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)', idl)}
# oleacc constants: plain NAME = int lines
ole = {}
for node in ast.parse((R / 'nvda-src/source/oleacc.py').read_text()).body:
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
        for t in node.targets:
            if isinstance(t, ast.Name): ole[t.id] = node.value.value
out = dict(msaa=msaa, ia2=ia2, ia2_role=ia2_role_vals, ia2_state=ia2_state_vals,
           ole={k: v for k, v in ole.items() if k.startswith(('ROLE_SYSTEM_', 'STATE_SYSTEM_'))})
(pathlib.Path(__file__).parent / 'tables.json').write_text(json.dumps(out, indent=1, sort_keys=True))
print(len(msaa), 'msaa roles;', len(ia2), 'ia2 role overrides;', len(ia2_role_vals), 'IA2 role consts;', len(ia2_state_vals), 'IA2 states;', len(out['ole']), 'oleacc consts')
for k in ('rootWebArea', 'heading', 'paragraph', 'link', 'button', 'checkBox', 'textField', 'staticText', 'labelText', 'inlineTextBox', 'genericContainer'):
    print(k, msaa.get(k), ia2.get(k))
