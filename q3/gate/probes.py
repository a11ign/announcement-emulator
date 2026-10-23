"""What the Gate's misses were caused by, tried on a COPY of the frozen emulator (A11-166). Nothing here changes the emulator or its figure: `emulator bug` is named, not fixed, and a probe is how a cause is shown.

    python probes.py variant <export dir> <out dir> <linked|page-left-at-end>     a copy of the export (export_freeze.py) with one named change, and the change as a diff
    python probes.py run <variant dir> <replay run dir> <out dir> <address>...    that copy's q3/emulate.py over each address, read through the page's archive, as run_replayed.py reads it
    python probes.py run-caret-back <export dir> <replay run dir> <out dir> <address>...    the export's own emulate.py, with the sweep's caret put back on the probed control (probe_caret_back.py)

The variants (each is one change, made once, at a line the check finds exactly once):
  linked            emu/standin.py: a node whose role is a link is STATE_SYSTEM_LINKED whatever the AX state `linked` says (Chromium's ax_platform_node_win.cc:8242-8245, "Handle STATE_SYSTEM_LINKED").
  page-left-at-end  q3/sweep.py: load_lazy_content leaves the page scrolled to its end, as NVDA leaves it on the fleet, instead of scrolling back to the top.
A probe's output is the emulator's own record per page (`<slug>.run1.json`); the committed evidence keeps only which fleet announcements it agrees with."""
import sys, os, shutil, difflib, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
ROOT = os.path.dirname(Q3)
sys.path.insert(0, os.path.join(Q3, 'replay')); sys.path.insert(0, Q3); sys.path.insert(0, os.path.join(ROOT, 'emu'))

VARIANTS = {
    'linked': ('emu/standin.py', "        if s.get('linked'): out |= CONST['STATE_SYSTEM_LINKED']\n",
               "        if s.get('linked') or r == 'link': out |= CONST['STATE_SYSTEM_LINKED']      # PROBE: ax_platform_node_win.cc:8242, a kLink is LINKED whatever the kLinked state\n"),
    'page-left-at-end': ('q3/sweep.py', '    d.s.eval("window.scrollTo(0, 0)"); time.sleep(0.5)\n',
                         "    time.sleep(1.5)      # PROBE: the page is left scrolled to its end, as NVDA leaves it on the fleet; its own scroll handlers (a 500 ms rate limit, an IntersectionObserver) run\n"),
}


def make_variant(export_dir, out_dir, name):
    """Copy `export_dir` to `out_dir` and make the named change once. Returns the diff. Refuses a tree that does not have the line the change is made at exactly once."""
    path, old, new = VARIANTS[name]
    with open(os.path.join(export_dir, path)) as f: text = f.read()
    if text.count(old) != 1: raise SystemExit(f'{path} does not have the one line the {name!r} probe is made at')
    shutil.rmtree(out_dir, ignore_errors=True); shutil.copytree(export_dir, out_dir)
    with open(os.path.join(out_dir, path), 'w') as f: f.write(text.replace(old, new))
    return ''.join(difflib.unified_diff(text.splitlines(True), text.replace(old, new).splitlines(True), f'a/{path}', f'b/{path}'))


def run_page(emulate_command, replay_run, url, out, port, timeout=900, extra_env=None):
    """One page, one run, read through its archive by the emulator command given. Returns the output path or None."""
    import corpus_capture as cc, with_replay
    slug = cc.slug_of(url); log = out + '.served.json'
    with_replay.run_under_replay(replay_run, slug + '.flows', [*emulate_command, url, out, '--port', str(port)], log, timeout, extra_env)
    return out if os.path.exists(out) else None


def main(argv):
    from paths import DOWNLOADS
    py = str(DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python')
    if len(argv) >= 4 and argv[0] == 'variant': print(make_variant(argv[1], argv[2], argv[3]))
    elif len(argv) >= 5 and argv[0] in ('run', 'run-caret-back'):
        root, replay_run, out = argv[1:4]; os.makedirs(out, exist_ok=True)
        command = [py, os.path.join(root, 'q3', 'emulate.py')] if argv[0] == 'run' else [py, os.path.join(HERE, 'probe_caret_back.py')]
        env = {'PROBE_ROOT': root} if argv[0] == 'run-caret-back' else None
        import corpus_capture as cc
        for i, url in enumerate(argv[4:]): print(url, run_page(command, replay_run, url, os.path.join(out, cc.slug_of(url) + '.run1.json'), 9870 + 2 * i, extra_env=env), flush=True)
    else: sys.exit(__doc__)


if __name__ == '__main__': main(sys.argv[1:])
