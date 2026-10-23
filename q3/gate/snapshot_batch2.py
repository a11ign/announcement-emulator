"""The addresses of A11-170's batch 2, as data (A11-166): a snapshot of the lab's real-page corpus entries marked `batch: 2`, read at one lab commit.

    python snapshot_batch2.py <lab checkout> <lab commit> <out.json>
    python snapshot_batch2.py --run-list <batch2 snapshot.json> <q3/results/corpus.json> <out.json>

The lab (a11ign/lab, private, never published) is read with `git show <commit>:src/training/real-page-corpus.mjs`; nothing of its code is imported (ADR 0045 is about code), and the checkout is not changed. The snapshot records the
lab commit, the sha256 of the file as read, and each address with its split from q3/split.py (a function of the address) and the sitemap it was drawn from. `q3/results/corpus.json` is the same kind of snapshot of the earlier corpus.

`--run-list` makes the list a replay run records and captures: the 120 batch-2 addresses (both halves) and the 60 held addresses of the earlier corpus, each with its `set` (`batch2` or `old60`), its split and its role."""
import sys, os, re, json, hashlib, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, Q3)
from split import split_of

LAB_FILE = 'src/training/real-page-corpus.mjs'
ARRAY = re.compile(r'^export const BATCH_2_PAGES\b.*$')
ENTRY = re.compile(r'^\s*\{\s*url:\s*"([^"]+)",\s*batch:\s*2\b(.*)$')
DRAWN_FROM = re.compile(r'drawnFrom:\s*"([^"]+)"')


def batch_two_entries(text):
    """(address, drawn-from sitemap) of each line of the BATCH_2_PAGES array that is marked `batch: 2`, in file order. Entries of the lab's other arrays are not read."""
    lines = text.splitlines(); start = next((n for n, l in enumerate(lines) if ARRAY.match(l)), None)
    if start is None: raise SystemExit('the lab file has no BATCH_2_PAGES array')
    out = []
    for line in lines[start + 1:]:
        if line.startswith(']'): break
        m = ENTRY.match(line)
        if m: out.append((m.group(1), (DRAWN_FROM.search(m.group(2)) or [None, None])[1]))
    return out


def snapshot(lab_commit, file_text):
    pages = batch_two_entries(file_text)
    if len({u for u, _ in pages}) != len(pages): raise SystemExit('an address is in batch 2 twice')
    return {'source': {'repo': 'a11ign/lab', 'commit': lab_commit, 'file': LAB_FILE, 'sha256': hashlib.sha256(file_text.encode()).hexdigest(), 'marked': 'batch: 2'},
            'pages': [{'url': u, 'split': split_of(u), 'drawnFrom': d} for u, d in pages]}


def run_list(batch2, corpus):
    """The addresses one replay run records and captures, batch 2 first."""
    return [{'url': p['url'], 'set': 'batch2', 'split': split_of(p['url']), 'role': None} for p in batch2['pages']] + \
           [{'url': e['url'], 'set': 'old60', 'split': split_of(e['url']), 'role': e.get('role')} for e in corpus if split_of(e['url']) == 'held']


def lab_file_at(checkout, commit):
    full = subprocess.run(['git', '-C', checkout, 'rev-parse', '--verify', commit + '^{commit}'], capture_output=True, text=True, check=True).stdout.strip()
    return full, subprocess.run(['git', '-C', checkout, 'show', f'{full}:{LAB_FILE}'], capture_output=True, text=True, check=True).stdout


def write(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=1, ensure_ascii=False); f.write('\n')


if __name__ == '__main__':
    argv = sys.argv[1:]
    if len(argv) == 4 and argv[0] == '--run-list':
        with open(argv[1]) as f: batch2 = json.load(f)
        with open(argv[2]) as f: corpus = json.load(f)
        write(argv[3], run_list(batch2, corpus))
    elif len(argv) == 3: write(argv[2], snapshot(*lab_file_at(argv[0], argv[1])))
    else: sys.exit(__doc__)
