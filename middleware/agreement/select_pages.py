"""Which corpus pages the agreement measurement runs on (A11-208, question 5), by a rule that is a function of the pages and of nothing the emulator or the fleet said about them.

    python3 select_pages.py <chrome executable> <out.json> [--count 6]

The rule, fixed and committed before any fleet capture for this ticket (results/agreement/rule.md):
  1. candidates are the corpus pages (q3/results/corpus.json) that were comparable in the Gate's freeze run of A11-166: the 60 pages of its `old60` set, less the seven that its figure
     (q3/results/gate/measure-old60-freeze.txt) lists as not comparable, faulted or unstable;
  2. they are put in the order of the SHA-256 of their address, read as a number (the order q3/split.py's even/odd rule is made from), so that the order is a function of the address alone;
  3. each in turn is opened in a browser and kept if its DOM, and only its DOM, has at least ten tab stops and a text field (dom_check.mjs);
  4. the first `count` that are kept are the sample.
Pages that a browser cannot open, or that fail the check, are listed with the reason."""
import hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MIN_TAB_STOPS, MIN_TEXT_FIELDS = 10, 1


def load(path):
    with open(path) as f: return json.load(f)


def candidates(root=ROOT):
    corpus = load(os.path.join(root, 'q3/results/corpus.json'))
    run = load(os.path.join(root, 'q3/results/gate/corpus-run.json'))
    old60 = {r['url'] for r in run if r['set'] == 'old60'}
    with open(os.path.join(root, 'q3/results/gate/measure-old60-freeze.txt')) as f: figure = f.read()
    excluded = set(re.findall(r'^\s+(?:not comparable|emulator fault|unstable): (\S+)', figure, re.M))
    urls = [c['url'] for c in corpus if c['url'] in old60 and c['url'] not in excluded]
    return sorted(urls, key=lambda u: int(hashlib.sha256(u.encode()).hexdigest(), 16)), excluded


def passes(counts): return counts['tabStops'] >= MIN_TAB_STOPS and counts['textFields'] >= MIN_TEXT_FIELDS


def select(urls, check, count=6):
    kept, rejected = [], []
    for url in urls:
        if len(kept) == count: break
        try: counts = check(url)
        except Exception as e: rejected.append({'url': url, 'why': f'not opened: {str(e)[:120]}'}); continue
        (kept if passes(counts) else rejected).append({'url': url, **counts} if passes(counts) else {'url': url, **counts, 'why': 'fewer than %d tab stops or no text field' % MIN_TAB_STOPS})
    return kept, rejected


if __name__ == '__main__':
    chrome, out = sys.argv[1], sys.argv[2]
    count = int(sys.argv[sys.argv.index('--count') + 1]) if '--count' in sys.argv else 6
    urls, excluded = candidates()
    def check(url):
        r = subprocess.run(['node', os.path.join(HERE, 'dom_check.mjs'), url, chrome], capture_output=True, text=True, timeout=120, cwd=os.path.join(ROOT, 'middleware'))
        if r.returncode: raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'failed')
        return json.loads(r.stdout)
    kept, rejected = select(urls, check, count)
    with open(out, 'w') as f: json.dump({'rule': 'results/agreement/rule.md', 'candidates': len(urls), 'excluded': sorted(excluded), 'sample': kept, 'rejected': rejected}, f, indent=1)
    print(f'{len(kept)} pages kept, {len(rejected)} rejected, of {len(urls)} candidates')
