"""Name the freeze of the agreement measurement (A11-208), before any fleet capture for this ticket is taken, and check afterwards that nothing it names has moved.

    python3 make_freeze.py name  <out.json> [--commit HEAD] [--also <path> ...]   write freeze.json: the commit, the time, and the git object of each thing the measure is made of, and of each extra path named
    python3 make_freeze.py check <freeze.json> [--fleet <dir>] [--head <rev>]   fail if any of those objects differs at HEAD (or `--head`), or if a fleet capture is older than the freeze

The same discipline as q3/gate/make_freeze.py (A11-166): the runtime, the extension, the sweep, the sample suite's corpus test, the page list and its rule, and the scripts the figure is made by
are fixed first, so a figure cannot have been fitted to the pages' misses. Anything the figure is made by that is changed afterwards makes `check` fail, and is listed.

A later measurement (A11-229, the tree sources) names what it adds to the figure with `--also`: its own rule, its comparison script, its workflow. The freeze file holds them with the rest, so `check` needs no flag."""
import argparse, datetime, glob, json, os, subprocess, sys

OBJECTS = ['emu', 'middleware/runtime', 'middleware/src', 'middleware/agreement/measure.py', 'middleware/agreement/select_pages.py', 'middleware/agreement/capture_fleet.py', 'middleware/agreement/dom_check.mjs',
           'middleware/sample-suite/tests/corpus', 'middleware/results/agreement/rule.md', 'middleware/results/agreement/pages.json', 'q3/sweep.py', 'q3/livepage.py', 'q3/shapes.py', 'q3/fleet_capture.mjs', 'pins.env']


def git(*args, repo='.'): return subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, check=True).stdout.strip()


def name(repo, commit, now=None, extra=()):
    full = git('rev-parse', '--verify', commit + '^{commit}', repo=repo)
    return {'commit': full, 'subject': git('show', '-s', '--format=%s', full, repo=repo), 'committedAt': git('show', '-s', '--format=%cI', full, repo=repo),
            'namedAt': (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'objects': {path: git('rev-parse', '--verify', f'{full}:{path}', repo=repo) for path in [*OBJECTS, *(p for p in extra if p not in OBJECTS)]}}


def moved(freeze, repo='.', head='HEAD'):
    """The named things whose git object at `head` is not the one in the freeze."""
    return [p for p, obj in freeze['objects'].items() if git('rev-parse', '--verify', f'{head}:{p}', repo=repo) != obj]


def early(freeze, fleet_dir):
    """The fleet captures dated before the freeze was named."""
    out = []
    for f in sorted(glob.glob(os.path.join(fleet_dir, '*.json'))):
        with open(f) as h: at = json.load(h).get('capturedAt')
        if not at or at < freeze['namedAt'].replace('Z', '.000Z'): out.append(os.path.basename(f))
    return out


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('command', choices=['name', 'check']); ap.add_argument('file'); ap.add_argument('--commit', default='HEAD'); ap.add_argument('--fleet'); ap.add_argument('--also', action='append', default=[], metavar='PATH', help='a path to name beside the standard objects (repeatable); `name` only'); ap.add_argument('--repo', default='.'); ap.add_argument('--head', default='HEAD', help='the commit to check against the freeze: the freeze commit itself, after later commits changed what it names')
    a = ap.parse_args(argv)
    if a.also and a.command != 'name': ap.error('--also names objects when the freeze is written; `check` reads them from the freeze file')
    if a.command == 'name':
        freeze = name(a.repo, a.commit, extra=a.also)
        with open(a.file, 'w') as f: json.dump(freeze, f, indent=1); f.write('\n')
        print(f'freeze {freeze["commit"][:10]} named {freeze["namedAt"]}')
        return 0
    with open(a.file) as f: freeze = json.load(f)
    problems = [f'{p} has changed since the freeze' for p in moved(freeze, a.repo, a.head)]
    if a.fleet: problems += [f'{f} was captured before the freeze was named' for f in early(freeze, a.fleet)]
    print('\n'.join(problems) if problems else f'ok: nothing the figure is made by has moved since {freeze["commit"][:10]}'
          + (', and every fleet capture is after the freeze' if a.fleet else ''))
    return 1 if problems else 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
