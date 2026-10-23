"""Where each side's capture begins, what consent was given in the recording, and whether a dialog is still there (A11-166): the committed account of the cookie rule, page by page.

    python consent_report.py <archive-manifest.json> <oracle dir> <emulator out dir> <out.json>

For every page of the manifest: the outcome of its consent sidecar (`given`, `no-dialog`, `not-matched`; the manifest carries it) and, for the fleet's capture and for the emulator's runs, two readings of a cookie or consent SURFACE (a dialog or a banner about
cookies, not a settings button the page keeps for good):
  contains   a swept announcement of any channel says one: the surface is in the page that side read (both sides are read the same way);
  begins     the first lines the fleet's NVDA read (`transcript`) say one: the fleet started reading in it (the emulator's read-through is not recorded, so the emulator has no `begins`).
A surface is a line with `cookie(s)` or `consent` and a word of a dialog or a banner (`accept`, `agree`, `allow`, `we use cookies`, `cookies on`, `your cookie`, `compliance`, `dialog`, a `Consent` tab). A side with either reading is `surface`, and named with
the lines that say so (at most two, 100 characters each: third-party text kept short). A page whose two sides differ in `contains` is `asymmetric`: one side was shown a dialog the other was not. `check.py consent` checks the report against the manifest."""
import sys, os, re, glob, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, Q3); sys.path.insert(0, os.path.join(Q3, 'remeasure'))
import corpus_capture as cc
import readback as rb

COOKIE_WORD = re.compile(r'\b(cookies?|consent)\b', re.I)
DIALOG_WORD = re.compile(r"\b(accept|agree|allow|dialog|alert|compliance|banner|we use cookies|uses cookies|cookies on|your cookie)\b|\btab\b.*\bconsent\b", re.I)
TRANSCRIPT_LINES = 6      # the fleet's NVDA starts reading where the page puts it: a dialog that took the focus is in the first lines
CHANNELS = ('headings', 'landmarks', 'formFields', 'graphics', 'links', 'lists', 'frames')


def is_surface(line): return bool(COOKIE_WORD.search(line) and DIALOG_WORD.search(line))


def shown(lines): return [str(l)[:100] for l in lines if is_surface(str(l))]


def reading(transcript, structure):
    """One capture: the surface lines the first lines of the transcript have (`begins`) and those any swept channel has (`contains`)."""
    begins = shown(list(transcript or [])[:TRANSCRIPT_LINES]); contains = shown([a for c in CHANNELS for a in (structure or {}).get(c) or []])
    return {'begins': begins[:2], 'contains': contains[:2], 'surface': bool(begins or contains), 'lines': (begins + contains)[:2]}


def side_of(records):
    """One side's reading from its records (the fleet's one, the emulator's runs): a surface in any of them."""
    readings = [reading(r.get('transcript'), r.get('structure')) for r in records if r]
    if not readings: return {'begins': [], 'contains': [], 'surface': False, 'lines': [], 'unread': 'no record of this side to read (the emulator timed out, or the fleet has none)'}
    return {'begins': [l for r in readings for l in r['begins']][:2], 'contains': [l for r in readings for l in r['contains']][:2], 'surface': any(r['surface'] for r in readings), 'lines': [l for r in readings for l in r['lines']][:2]}


def report(manifest, oracle_dir, emulator_dir):
    pages = []
    for p in manifest['pages']:
        slug = cc.slug_of(p['url']); path = os.path.join(oracle_dir, slug + '.json')
        fleet = side_of([(rb.read_json(path).get('capture') or {})] if os.path.exists(path) else [])
        runs = [rb.read_json(f) for f in sorted(glob.glob(os.path.join(emulator_dir, f'{slug}.run*.json')))]
        emulator = side_of([r for r in runs if 'structure' in r])
        pages.append({'url': p['url'], 'outcome': p['consent'], 'why': p.get('consentWhy'), 'cookies': p.get('consentCookies'), 'fleet': fleet, 'emulator': emulator,
                      'asymmetric': bool(fleet and emulator and bool(fleet['contains']) != bool(emulator['contains']))})
    return {'outcomes': dict(collections.Counter(p['consent'] for p in manifest['pages'])), 'pages': pages}


if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    rb.write_json(sys.argv[4], report(rb.read_json(sys.argv[1]), sys.argv[2], sys.argv[3]))
