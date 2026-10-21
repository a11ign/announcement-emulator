"""Which of the language misses of an earlier reading are fixed by a later re-score of the same pages: the evidence that the table and the settings fix explain them.

    python3 emu/langnames/fixed_misses.py <earlier misses.json> <later misses.json> [<out.json>]

Both are `q3/measure.py --json` outputs. For each row the earlier reading classed `language` (on the ten shapes or not), the later reading says: `fixed` (its page is comparable in the later reading and the same row, by
address, channel and the fleet's text, is not a miss), `still a miss` (it is, and with what the emulator said), or `page not comparable` (the later reading cannot say). Exit 1 when any row is `still a miss`."""
import collections, json, pathlib, sys


def status_of(row, later_status, later_by_key):
    """(`fixed`, None), (`still a miss`, what the emulator says now) or (`page not comparable`, None)."""
    if later_status.get(row['url']) != 'comparable': return 'page not comparable', None
    still = later_by_key.get((row['url'], row['channel'], row['expected']))
    return ('still a miss', still['predicted']) if still else ('fixed', None)


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    earlier, later = (json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in argv[:2])
    later_status = {p['url']: p['status'] for p in later['pages']}
    later_by_key = {(m['url'], m['channel'], m['expected']): m for m in later['misses']}
    out = []
    for row in (m for m in earlier['misses'] if m['class'] == 'language'):
        status, now = status_of(row, later_status, later_by_key)
        out.append({'url': row['url'], 'channel': row['channel'], 'expected': row['expected'], 'before': row['predicted'], 'status': status, 'now': now})
    counts = collections.Counter(r['status'] for r in out)
    print(f'{len(out)} language rows in {argv[0]}: {dict(counts)}')
    if len(argv) > 2: pathlib.Path(argv[2]).write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return 1 if counts['still a miss'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
