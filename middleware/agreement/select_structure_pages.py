"""Which pages the structure measurement runs on (A11-229, step 2), by a rule that is a function of the pages' DOM and of nothing the emulator or the fleet said about them.

    python3 select_structure_pages.py <candidates.json> <out.json> [--count 4] [--chrome <executable>]

The rule, fixed and committed before any fleet capture for it (results/tree-source-structure/rule.md):
  1. candidates are the addresses of `candidates.json`, less the six pages of the Q5 sample (results/agreement/pages.json);
  2. they are put in the order of the SHA-256 of their address, read as a number (the order select_pages.py uses);
  3. each in turn is opened in a browser and its DOM counted (dom_check_structure.mjs, and nothing else); a page with more than 500 tab stops is left out (the middleware predicted nothing on pages of 700 and more);
     otherwise it is a `table` page when it has at least 3 header cells, a table of at least 40 cells and at least 20 tab stops inside table cells, and otherwise a `list` page when it has at least 20 tab stops
     inside list items and a list of at least 20 items or at least 3 nested lists;
  4. the first `count` of each class, in that order, are the sample.
Pages that cannot be opened, or that are neither, are listed with the reason."""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MIN_HEADERS, MIN_TABLE, MIN_STOPS_IN_CELLS = 3, 40, 20
MIN_STOPS_IN_ITEMS, MIN_LIST, MIN_NESTED = 20, 20, 3
MAX_TAB_STOPS = 500


def load(path):
    with open(path) as f: return json.load(f)


def order(addresses): return sorted(addresses, key=lambda u: int(hashlib.sha256(u.encode()).hexdigest(), 16))


def classify(counts):
    """'table', 'list' or None: what the page is for this measurement, from its DOM counts."""
    if counts['tabStops'] > MAX_TAB_STOPS: return None
    if counts['headerCells'] >= MIN_HEADERS and counts['largestTable'] >= MIN_TABLE and counts['tabStopsInCells'] >= MIN_STOPS_IN_CELLS: return 'table'
    if counts['tabStopsInItems'] >= MIN_STOPS_IN_ITEMS and (counts['largestList'] >= MIN_LIST or counts['nestedLists'] >= MIN_NESTED): return 'list'
    return None


def select(urls, check, count=4):
    """(kept, rejected): the first `count` pages of each class in the order of `urls`; `check(url)` returns the DOM counts or raises."""
    kept, rejected, taken = [], [], {'table': 0, 'list': 0}
    for url in urls:
        if all(n >= count for n in taken.values()): break
        try: counts = check(url)
        except Exception as e: rejected.append({'url': url, 'why': f'not opened: {str(e)[:120]}'}); continue
        kind = classify(counts)
        if kind is None: rejected.append({'url': url, **counts, 'why': 'neither a table page nor a list page by the rule, or more than %d tab stops' % MAX_TAB_STOPS})
        elif taken[kind] >= count: rejected.append({'url': url, **counts, 'class': kind, 'why': f'the first {count} {kind} pages were already kept'})
        else: taken[kind] += 1; kept.append({'url': url, 'address': url, 'class': kind, **counts})
    return kept, rejected


def main(argv):
    candidates_file, out = argv[0], argv[1]
    count = int(argv[argv.index('--count') + 1]) if '--count' in argv else 4
    chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
    used = {p['url'] for p in load(os.path.join(ROOT, 'middleware/results/agreement/pages.json'))['sample']}
    urls = order([c['url'] for c in load(candidates_file)['candidates'] if c['url'] not in used])

    def check(url):
        r = subprocess.run(['node', os.path.join(HERE, 'dom_check_structure.mjs'), url, *([chrome] if chrome else [])], capture_output=True, text=True, timeout=180, cwd=os.path.join(ROOT, 'middleware'))
        if r.returncode: raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'failed')
        return {k: v for k, v in json.loads(r.stdout).items() if k != 'address'}
    kept, rejected = select(urls, check, count)
    with open(out, 'w') as f: json.dump({'rule': 'results/tree-source-structure/rule.md', 'candidates': len(urls), 'sample': kept, 'rejected': rejected}, f, indent=1); f.write('\n')
    print(f'{len(kept)} pages kept ({sum(p["class"] == "table" for p in kept)} table, {sum(p["class"] == "list" for p in kept)} list), {len(rejected)} rejected, of {len(urls)} candidates')


if __name__ == '__main__': main(sys.argv[1:])
