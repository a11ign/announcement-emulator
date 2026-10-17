"""Layer 0/1: load a page in Chrome 155 (headless=new, allowlisted companion extension) and return the web area's chrome.automation nodes."""
import json, os, subprocess, pathlib, tempfile, hashlib
R = pathlib.Path.home() / 'spikes/announcement-emulator-5661'
CHROME = R / 'chrome155/chrome-linux64/chrome'
CACHE = R / 'emu/captures'; CACHE.mkdir(exist_ok=True)

WRAP = """
<head>
<meta charset="UTF-8">
<title>{title}</title>
</head>
<body lang="en" onload="document.getElementById('loadStatus').innerHTML='Test page load complete'">
<p>Before Test Case Marker</p>
<p id="loadStatus">Loading...</p>
{case}
<p>After Test Case Marker</p>
</body>
"""   # ChromeLib._writeTestFile, tests/system/libraries/ChromeLib.py:158-168


def capture(case_html, key):
    out = CACHE / f'{key}.json'
    if out.exists(): return json.loads(out.read_text())
    page = CACHE / f'{key}.html'
    page.write_text(WRAP.format(title='NVDA Browser Test Case', case=case_html))
    raw = CACHE / f'{key}.raw.json'
    env = {**os.environ, 'CHROME': str(CHROME), 'PAGE': str(page)}
    subprocess.run(['node', 'run.mjs', 'allow', str(raw)], cwd=R / 'q1', env=env, check=True, capture_output=True, timeout=120)
    nodes = json.loads(raw.read_text())['got']['desktop-tree']['nodes']
    for i, n in enumerate(nodes):
        if n.get('role') == 'rootWebArea':
            base, sub = n['depth'], [n]
            for m in nodes[i + 1:]:
                if m['depth'] <= base: break
                sub.append(m)
            out.write_text(json.dumps(sub)); raw.unlink()
            return sub
    raise RuntimeError('no web area in capture')
