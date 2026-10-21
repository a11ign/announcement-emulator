"""Which `visited` announcements of the fresh oracle are the browser's own, not history carried between captures (A11-155).

    python explain_visited.py <oracle_dir> <emu_dir> <out.json>

The oracle was captured on boxes whose Edge saves no history, so a `visited` in it should be 0. It is not quite: a link to the page's OWN address reads `visited` once the browser is on that
page (the plan's zero-count rule did not foresee it). What separates that from history is the emulator, whose Chrome is fresh, has no history model and has visited nothing before the page:
an oracle `visited` announcement is EXPLAINED when the emulator, run on the same page with no history, announces the identical string in the same channel. Anything else is UNEXPLAINED, and is
what a history that was not clean would leave. `<emu_dir>` holds `run_all.py`'s `<slug>.run<k>.json` for (at least) the pages that carry `visited`.
The output lists each announcement with its page, its channel and the worker that captured it; the check (check.py) needs `unexplained` to be empty."""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readback as rb

CHANNELS = ('headings', 'landmarks', 'formFields', 'graphics', 'links', 'lists', 'frames', 'tableCells')


def visited_in(capture):
    """(channel, announcement) of every swept announcement that carries the `visited` token."""
    return [(ch, a) for ch in CHANNELS for a in (capture.get('structure') or {}).get(ch) or [] if 'visited' in rb.tokens(a)]


def emulator_announcements(emu_dir, slug):
    """The swept announcements of the emulator's runs of a page, by channel (the union over its runs), or None when there is no run."""
    runs = [rb.read_json(f) for f in sorted(glob.glob(os.path.join(emu_dir, slug + '.run*.json')))]
    runs = [r for r in runs if 'structure' in r]
    return {ch: {a for r in runs for a in r['structure'].get(ch) or []} for ch in CHANNELS} if runs else None


def explain(oracle_dir, emu_dir):
    found, unexplained, pages = 0, [], {}
    for f in sorted(glob.glob(os.path.join(oracle_dir, '*.json'))):
        rec = rb.read_json(f); cap = rec.get('capture') or {}; hits = visited_in(cap)
        if not hits: continue
        slug = os.path.basename(f)[:-5]; emu = emulator_announcements(emu_dir, slug)
        for ch, a in hits:
            found += 1
            if emu is None or a not in emu[ch]:
                unexplained.append({'url': cap.get('url'), 'worker': rec.get('worker'), 'channel': ch, 'announcement': a, 'why': 'no emulator run' if emu is None else 'the emulator, with no history, does not announce it'})
        pages[cap.get('url')] = {'worker': rec.get('worker'), 'announcements': [a for _, a in hits]}
    return {'oracleVisitedAnnouncements': found, 'explained': found - len(unexplained), 'unexplained': unexplained, 'pages': pages}


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    result = explain(sys.argv[1], sys.argv[2]); rb.write_json(sys.argv[3], result)
    print(f"{result['oracleVisitedAnnouncements']} visited announcements on {len(result['pages'])} pages, {result['explained']} explained by the emulator with no history, {len(result['unexplained'])} unexplained")
    sys.exit(1 if result['unexplained'] else 0)
