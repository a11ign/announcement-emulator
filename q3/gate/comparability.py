"""Which pages of the Gate's half are comparable, and why each that is not is not (A11-166).

    python comparability.py <misses-held-freeze.json> <consent-report.json> <out.json>

`measure.py` decides whether a page is comparable (both emulator runs agree, the fleet's capture has every channel, the accessibility census and the document are the same on both sides); this puts its status, page by page, under
one reason from the list `check.py comparable` knows, and adds what the consent report says of the page:

  title spoken differently   the only difference is the document's title, which NVDA spoke with a space the page's title has not (`Q 2` for `Q2`, `A 9` for `A9`): the page is the page that was asked for, and measure.py's rule (a title test that
                       drops only the word `dot`) leaves it out; it is kept out here, as the rule is unchanged, and named
  consent surface      either side's capture begins in or contains a cookie or consent surface (the report names the lines)
  consent not matched  the recording found a dialog and no control of the list to activate (consent.py `not-matched`), and the page is not comparable
  two runs disagree    the emulator's two runs differ ("unstable")
  census differs       the fleet's and the emulator's headings or links are not the same count
  document differs     the document's title or its headings are not the same on the two sides
  timeout              the emulator ran past its time (900 s), or a run faulted by it
  emulator fault       the emulator faulted otherwise, or has no run
  fleet capture incomplete   the fleet's record lacks a swept channel

A page that is comparable is counted as comparable even where the report says a side began in or contained a surface: its misses, if any, are in the Gate figure and are attributed. `comparableInASurface` counts them, and `comparableInASurfaceForOneSideOnly`
those where only one side was shown the dialog."""
import sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(Q3, 'remeasure'))
import readback as rb


def squashed(text): return re.sub(r'[^a-z0-9]', '', text.lower())


def only_the_spoken_title_differs(status):
    """measure.py's `document title fleet '<first 40 characters, as spoken>' / emulator '<the document's>'` as the only difference, and the two the same once spaces and punctuation are taken out."""
    m = re.fullmatch(r"not comparable: document title fleet '(.*)' / emulator '(.*)'", status)
    if not m: return False
    a, b = squashed(m.group(1)), squashed(m.group(2))
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def reason_of(status, outcome, surface):
    """(reason, detail) for a page that measure.py did not find comparable."""
    detail = status
    if only_the_spoken_title_differs(status): return 'title spoken differently', detail + ('; a cookie or consent surface is also there: ' + '; '.join(surface['lines']) if surface['surface'] else '')
    if surface['surface']: return 'consent surface', f'{status}; begins in a surface: {"; ".join(surface["lines"])}'
    if outcome == 'not-matched': return 'consent not matched', f'{status}; the recording found a dialog and no control of the list'
    if status.startswith('unstable'): return 'two runs disagree', detail
    if status.startswith('not comparable'):
        return ('document differs' if re.search(r'document title|headings read', status) else 'census differs'), detail
    if status.startswith(('emulator fault', 'second run fault')): return ('timeout' if 'timeout' in status else 'emulator fault'), detail
    if status.startswith('no emulator run'): return 'emulator fault', detail
    if status.startswith('oracle lacks'): return 'fleet capture incomplete', detail
    return 'emulator fault', detail


def build(misses, consent):
    by_url = {p['url']: p for p in consent['pages']}; pages = []
    for p in misses['pages']:
        c = by_url.get(p['url'], {}); surface = {'surface': any((c.get(s) or {}).get('surface') for s in ('fleet', 'emulator')), 'lines': [l for s in ('fleet', 'emulator') for l in (c.get(s) or {}).get('lines', [])][:2]}
        entry = {'url': p['url'], 'status': p['status'], 'consent': c.get('outcome'), 'comparable': p['status'] == 'comparable'}
        if not entry['comparable']: entry['reason'], entry['detail'] = reason_of(p['status'], c.get('outcome'), surface)
        elif surface['surface']: entry['inASurface'] = surface['lines']; entry['asymmetric'] = bool(c.get('asymmetric'))
        pages.append(entry)
    reasons = {}
    for p in pages:
        if not p['comparable']: reasons[p['reason']] = reasons.get(p['reason'], 0) + 1
    return {'comparable': sum(p['comparable'] for p in pages), 'total': len(pages), 'comparableInASurface': sum(1 for p in pages if p.get('inASurface')), 'comparableInASurfaceForOneSideOnly': sum(1 for p in pages if p.get('asymmetric')), 'reasons': reasons, 'pages': pages}


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    rb.write_json(sys.argv[3], build(rb.read_json(sys.argv[1]), rb.read_json(sys.argv[2])))
