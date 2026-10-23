"""Name the freeze of the Gate's re-run (A11-166): the emulator's commit, and the git objects of what it is made of, written before any page of the run is captured.

    python make_freeze.py <commit> <out.json> --includes A11-164=<merge commit> [--repo .]

`freeze.json` holds the commit (full id) and its subject, the time it was named, the commits it must contain (A11-164's merge, whose language table is in the emulator before the freeze), and the git object id at that commit of `emu/` (a
tree) and of the emulator's harness and the rules the figure is measured by (`q3/emulate.py`, `sweep.py`, `livepage.py`, `shapes.py`, `measure.py`, `attribute.py`, `split.py`: blobs). `check.py freeze` compares them with the same
paths at the branch's head: this ticket changes none of them. The emulator is run from `git archive` of the commit (`q3/replay/export_freeze.py`)."""
import sys, os, json, argparse, subprocess, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'remeasure'))
import check


def git(repo, *args): return subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, check=True).stdout.strip()


def freeze_of(repo, commit, includes, now=None):
    full = git(repo, 'rev-parse', '--verify', commit + '^{commit}')
    for ticket, merge in includes.items():
        if subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', merge, full], capture_output=True).returncode: raise SystemExit(f'{ticket} ({merge}) is not in {commit}')
    return {'commit': full, 'subject': git(repo, 'show', '-s', '--format=%s', full), 'committedAt': git(repo, 'show', '-s', '--format=%cI', full),
            'namedAt': (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'), 'includes': {t: git(repo, 'rev-parse', '--verify', m + '^{commit}') for t, m in includes.items()},
            'objects': {path: git(repo, 'rev-parse', '--verify', f'{full}:{path}') for path in check.FREEZE_OBJECTS}}


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('commit'); ap.add_argument('out'); ap.add_argument('--includes', action='append', default=[], help='<ticket>=<commit it merged as>'); ap.add_argument('--repo', default='.'); a = ap.parse_args(argv)
    freeze = freeze_of(a.repo, a.commit, dict(x.split('=', 1) for x in a.includes))
    with open(a.out, 'w') as f: json.dump(freeze, f, indent=1); f.write('\n')
    print(f'freeze {freeze["commit"][:10]} named {freeze["namedAt"]}')


if __name__ == '__main__': main(sys.argv[1:])
