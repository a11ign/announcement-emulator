"""Which of the Gate's misses the fixes of A11-176 remove, read from a fresh reading of the same pages (NOT HELD OUT: the emulator was fixed against these pages).

    python3 fixed_at_head.py <misses-attributed.json> <A11-166 misses-held-freeze.json> <freeze re-run misses.json> <head re-run misses.json> [<out.json>]

The rows are the Gate's ten misses (`misses-attributed.json`) and the rows of the Gate's own misses on those pages that the fleet spoke with the access key (`Alt plus, m`), which are outside the ten shapes. The oracle of A11-166 is gone, so
the pages are read on the fleet again, and the freeze is run again beside head as the control (`measure.py --json` of each). Each row gets two statuses, by address, channel and the fleet's text (emu/langnames/fixed_misses.py `status_of`):
  at the freeze   `reproduced` (the fresh reading misses it as the Gate did) or `not reproduced` (it does not, so the change cannot be said to have fixed it)
  at head         `fixed`, `still a miss` (with what the emulator says now) or `page not comparable`
Exit 1 unless every row is `reproduced` at the freeze and `fixed` at head."""
import collections, json, os, pathlib, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'emu', 'langnames'))
import fixed_misses

ACCESS_KEY = 'Alt plus, m'


def rows_of(attributed, gate_misses):
    """The ten misses, then the access-key rows of the Gate's misses on the same pages that are not among them."""
    ten = [{'url': m['page'], 'channel': m['channel'], 'expected': m['expected'], 'was': m['predicted'], 'cause': m['evidence'][0]} for m in attributed['misses']]
    pages = {r['url'] for r in ten}; have = {(r['url'], r['channel'], r['expected']) for r in ten}
    keys = [{'url': m['url'], 'channel': m['channel'], 'expected': m['expected'], 'was': m['predicted'], 'cause': 'access key'} for m in gate_misses['misses']
            if m['url'] in pages and ACCESS_KEY in m['expected'] and (m['url'], m['channel'], m['expected']) not in have]
    return ten + keys


def reading_of(misses):
    return {p['url']: p['status'] for p in misses['pages']}, {(m['url'], m['channel'], m['expected']): m for m in misses['misses']}


def statuses(rows, freeze, head):
    """Each row with its status at the freeze re-run and at head."""
    (freeze_pages, freeze_by_key), (head_pages, head_by_key) = reading_of(freeze), reading_of(head)
    out = []
    for row in rows:
        before, now_freeze = fixed_misses.status_of(row, freeze_pages, freeze_by_key)      # `still a miss` at the freeze is the Gate's miss, again
        after, now_head = fixed_misses.status_of(row, head_pages, head_by_key)
        out.append({**row, 'freeze': {'status': 'reproduced' if before == 'still a miss' else 'not reproduced', 'reading': before, 'now': now_freeze}, 'head': {'status': after, 'now': now_head}})
    return out


def all_fixed(rows): return all(r['freeze']['status'] == 'reproduced' and r['head']['status'] == 'fixed' for r in rows)


def main(argv):
    if len(argv) < 4: sys.exit(__doc__)
    attributed, gate, freeze, head = (json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in argv[:4])
    out = statuses(rows_of(attributed, gate), freeze, head)
    print(f"{len(out)} rows: at the freeze {dict(collections.Counter(r['freeze']['status'] for r in out))}; at head {dict(collections.Counter(r['head']['status'] for r in out))}")
    if len(argv) > 4: pathlib.Path(argv[4]).write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return 0 if all_fixed(out) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
