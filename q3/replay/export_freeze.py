"""The emulator as it was at a commit, with the one launch change a replay needs when the commit does not have it (A11-165, A11-166).

    python export_freeze.py <rev> <out dir>

`git archive` writes the tree of `<rev>` (no worktree is added to the repository). A commit from before A11-165 (the spike's freeze, `5fbd726`) has no launch through a proxy, and `emu/session.mjs` there gets the lines this branch's
`emu/session.mjs` has for a replay: with `EMU_PROXY` set Chrome is launched through the proxy and trusts the run's certificate authority by its hash. With it unset the launch is the commit's own, byte for byte (the added list
is empty). A commit that already has that launch (A11-166's freeze is a commit after A11-165) is exported unchanged, byte for byte: nothing is patched. Nothing of the emulator's speech, its tree or its sweep is touched either way:
the figures of a freeze are the emulator's, run behind a proxy. Refuses a tree whose `session.mjs` has neither the launch nor the one line the change is made at."""
import sys, os, subprocess, io, tarfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ANCHOR = "const ch = spawn(chromeBin, ['--headless=new', '--no-sandbox', '--force-renderer-accessibility', `--window-size=${VW},${VH}`, '--user-data-dir=' + PROFILE, '--no-first-run',\n"
REPLAY = ("// A replay (A11-165): the page is read through a proxy that answers every request from a recording, and the run's certificate authority is trusted by its SPKI hash. With EMU_PROXY unset the launch is as it was.\n"
          "if (process.env.EMU_PROXY && !process.env.EMU_PROXY_SPKI) throw new Error('EMU_PROXY needs EMU_PROXY_SPKI, the hash of the certificate authority the proxy signs with');\n"
          "const REPLAY = process.env.EMU_PROXY ? ['--proxy-server=' + process.env.EMU_PROXY, '--ignore-certificate-errors-spki-list=' + process.env.EMU_PROXY_SPKI, '--disable-background-networking'] : [];\n")


def has_launch(session_mjs): return REPLAY in session_mjs and session_mjs.count("'--no-first-run', ...REPLAY,\n") == 1


def patched(session_mjs):
    """`session.mjs` as a replay needs it: unchanged when it already launches through the proxy, else with the launch added at the one line it is made at."""
    if has_launch(session_mjs): return session_mjs
    if session_mjs.count(ANCHOR) != 1: raise SystemExit('emu/session.mjs does not have the one spawn line the replay change is made at')
    return session_mjs.replace(ANCHOR, REPLAY + ANCHOR.replace("'--no-first-run',\n", "'--no-first-run', ...REPLAY,\n"))


def export(rev, out):
    os.makedirs(out, exist_ok=True)
    tar = subprocess.run(['git', '-C', ROOT, 'archive', rev], capture_output=True, check=True).stdout      # the whole tree of the commit, whichever directory this is run from
    with tarfile.open(fileobj=io.BytesIO(tar)) as t: t.extractall(out, filter='data')
    path = os.path.join(out, 'emu', 'session.mjs')
    with open(path) as f: text = f.read()
    with open(path, 'w') as f: f.write(patched(text))


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    export(*sys.argv[1:])
