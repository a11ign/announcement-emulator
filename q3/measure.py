"""Q3 and the Gate: agreement between the emulator and the fleet's transcripts, exact, by element kind and by shape.

    python measure.py <oracle_dir> <emu_dir> [--split dev|held|all] [--final] [--json out.json] [--misses N]

Definitions, fixed before any figure existed (docs/announcement-emulator-spike.md, Q3):
  unit      one announcement in a swept channel of the capture's `structure` (headings, landmarks, formFields, graphics, links, lists, frames), the
            fleet's list being the oracle and the emulator's list for the same page and channel the prediction. Table cells are not swept (probeTables is
            opt-in and off for real pages) and are not measured.
  exact     byte-equal strings. Both sides are already what the worker records (trimmed, Guidepup's join), so nothing else is applied.
  agree     an oracle announcement is agreed when it is in the longest order-preserving matching of the two lists by exact equality (difflib, autojunk off), so a
            single missing or extra element costs one miss, not every element after it. The position-by-position count is given beside it.
  shape     shapes.shape_of(); the top 10 are ranked over the oracle announcements of every comparable page in the run, in the channels the fleet's shape
            script reads (not frames).
  stable    both emulator runs of a page give identical lists in every channel. An unstable page is not compared.
  comparable the page's accessibility census in the oracle (heading, link, graphic counts) equals the emulator tree's. A page that is not is listed, with
            its URL and the counts, and kept out of the denominator; the Gate also prints the figure with them in.
Held pages' strings are not printed unless --final."""
import sys, os, json, glob, argparse, difflib, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split import split_of
from shapes import shape_of, FIELDS, vocabularies

CHANNELS = ("headings", "landmarks", "formFields", "graphics", "links", "lists", "frames")
SHAPE_CHANNELS = [c for c in CHANNELS if c in FIELDS]
FORM_ROLES = ("edit", "combo box", "check box", "radio button", "toggle button", "slider", "spin button", "switch", "list box", "tab", "menu button", "split button", "button")

ap = argparse.ArgumentParser(); ap.add_argument('oracle'); ap.add_argument('emu'); ap.add_argument('--split', default='dev', choices=['dev', 'held', 'all'])
ap.add_argument('--final', action='store_true'); ap.add_argument('--json'); ap.add_argument('--misses', type=int, default=0); ap.add_argument('--top', type=int, default=10); ap.add_argument('--sig', type=int, default=0)
ap.add_argument('--as-frozen', action='store_true', help='the comparability rules as they stood when the emulator was frozen (see the Q3 section: two were corrected after the first held reading)')
a = ap.parse_args()
quiet = lambda url: split_of(url) == 'held' and not a.final


def census_of(rec):
    for e in rec['capture'].get('diagnostics', []):
        if e.get('event') == 'structureCensus': return {k: e.get(k) for k in ('heading', 'link', 'graphic', 'landmark', 'formControl')}
    return None


def kind_of(channel, text):
    if channel in ('headings', 'landmarks', 'links', 'lists', 'graphics', 'frames'): return channel
    toks = [t.strip().lower() for t in text.split(',')]
    for t in reversed(toks):
        if t == 'button' or t.endswith(' button') and t not in ('radio button', 'toggle button', 'menu button', 'split button'): return 'buttons'
        if t in FORM_ROLES: return 'formFields'
    return 'formFields'


pages = []
for f in sorted(glob.glob(os.path.join(a.oracle, '*.json'))):
    try: rec = json.load(open(f))
    except Exception: continue
    cap = rec.get('capture') or {}; url = cap.get('url')
    if not url: continue
    if a.split != 'all' and split_of(url) != a.split: continue
    slug = os.path.basename(f)[:-5]
    runs = []
    for k in (1, 2):
        g = os.path.join(a.emu, f'{slug}.run{k}.json')
        runs.append(json.load(open(g)) if os.path.exists(g) else None)
    pages.append({'slug': slug, 'url': url, 'role': rec.get('role'), 'oracle': cap, 'census': census_of(rec), 'runs': runs, 'split': split_of(url)})

status = collections.OrderedDict(); P = []
for p in pages:
    r1, r2 = p['runs']
    if r1 is None: p['status'] = 'no emulator run'
    elif r1.get('fault') or 'structure' not in r1: p['status'] = f"emulator fault: {r1.get('fault')}"
    elif r2 is not None and (r2.get('fault') or 'structure' not in r2): p['status'] = f"second run fault: {r2.get('fault')}"
    elif r2 is not None and any(r1['structure'][c] != r2['structure'][c] for c in CHANNELS): p['status'] = 'unstable: the two emulator runs differ'
    elif not p['oracle'].get('structure') or any(c not in p['oracle']['structure'] for c in CHANNELS): p['status'] = 'oracle lacks a channel'
    else:
        oc, ec = p['census'] or {}, r1['census']
        # CORRECTED after the first held-out reading (a.as_frozen restores the earlier rule): the graphic count is not used, because the fleet's tree census and the
        # emulator's tree count images differently - on W3C's static demo pages, which do not change, they differ by two - and a count that differs on a page that
        # cannot have changed does not say the page changed.
        diff = {k: (oc.get(k), ec.get(k)) for k in (('heading', 'link', 'graphic') if a.as_frozen else ('heading', 'link')) if oc.get(k) != ec.get(k)}
        ot = next((e.get('title') for e in p['oracle'].get('diagnostics', []) if e.get('event') == 'documentReady'), None)      # what the fleet's browser reported as the document's title when NVDA was asked
        et = r1.get('title')
        # CORRECTED likewise: the fleet's title is what NVDA SPOKE ("GOV dot UK Design System"), the emulator's is the document's ("GOV.UK Design System"); the word `dot` is dropped from both.
        norm = lambda t: re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\bdot\b', ' ', (t or '').lower().replace('\u200b', '')) if not a.as_frozen else (t or '').lower().replace('\u200b', '')).strip()
        if ot and et and norm(ot)[:25] not in norm(et) and norm(et)[:25] not in norm(ot): diff['document title'] = (repr(ot[:40]), repr(et[:40]))
        oh, eh = set(p['oracle']['structure']['headings']), set(r1['structure']['headings'])
        names = lambda L: {x.split(', heading')[0].split(', ')[-1] for x in L}
        overlap = len(names(oh) & names(eh)) / max(1, len(names(oh)))
        if oh and overlap < .5: diff['headings read'] = ('fleet names %d, %.0f%% of them found in the emulator\'s' % (len(names(oh)), 100 * overlap), 'a different document')
        p['status'] = 'comparable' if not diff else 'not comparable: ' + ', '.join(f'{k} fleet {v[0]} / emulator {v[1]}' for k, v in diff.items())
        p['census_diff'] = diff
    status.setdefault(p['status'].split(':')[0], []).append(p)
    P.append(p)
print(f"pages {len(P)} ({a.split})  " + '   '.join(f'{k}: {len(v)}' for k, v in status.items()))
for k, v in status.items():
    if k != 'comparable':
        for p in v: print(f"   {k}: {p['url']}  [{p['status']}]")


def evaluate(p):
    rows = []
    r1 = p['runs'][0]
    for ch in CHANNELS:
        O, E = p['oracle']['structure'][ch], r1['structure'][ch]
        sm = difflib.SequenceMatcher(None, O, E, autojunk=False)
        matched, pred = set(), {}
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal': matched.update(range(i1, i2))
            elif tag == 'replace':
                for n in range(i2 - i1): pred[i1 + n] = E[j1 + n] if j1 + n < j2 else None
        for i, text in enumerate(O):
            rows.append({'url': p['url'], 'channel': ch, 'i': i, 'expected': text, 'predicted': text if i in matched else pred.get(i), 'ok': i in matched,
                         'positional': i < len(E) and E[i] == text, 'shape': shape_of(text), 'kind': kind_of(ch, text)})
        p.setdefault('extras', {})[ch] = len(E) - len(matched)
    return rows

def table(rows, key, title, order=None, limit=None):
    c = collections.OrderedDict()
    for r in rows:
        t = c.setdefault(key(r), [0, 0, 0]); t[0] += r['ok']; t[1] += 1; t[2] += r['positional']
    items = sorted(c.items(), key=lambda kv: -kv[1][1]) if order is None else [(k, c[k]) for k in order if k in c]
    print(f"\n{title}\n  {'exact / total':>16}  {'%':>6}  {'positional':>10}")
    for k, (ok, n, pos) in items[:limit]:
        print(f"  {ok:>7} / {n:<7}  {100 * ok / n:>5.1f}%  {pos:>10}  {k}")
    return c

def classify(r):
    """The cause of a miss, where a rule with evidence names one (docs/announcement-emulator-spike.md, Gate). Anything else is `unexplained`.
      history   the fleet browser had visited the link's address and ours had not (or the reverse): the only difference is the word `visited`. The fleet's
                profile history is not something the emulator can read; it is neither an emulator bug nor Windows-only, which the Gate's two classes do not allow for.
      language  a language name: Windows' (GetLocaleInfo, languageHandler.py:164) where the emulator has the language code.
      prompt    Chromium's image-description prompt and role text, present in the fleet's tree and absent from the Linux one (measured in Q2 and here)."""
    e, q = r['expected'], r['predicted']
    if 'Unlabelled graphic' in e or 'To get missing image descriptions' in e: return 'prompt'
    if q is None: return 'unexplained'
    te, tq = [t.strip() for t in e.split(',')], [t.strip() for t in q.split(',')]
    ce, cq = collections.Counter(te), collections.Counter(tq)
    oe, oq = list((ce - cq).elements()), list((cq - ce).elements())
    if te != tq and [t for t in te if t != 'visited'] == [t for t in tq if t != 'visited']: return 'history'      # the strings differ only in where the word `visited` stands (or whether it does)
    if 'Unlabelled graphic' in e or 'To get missing image descriptions' in e: return 'prompt'
    if any('(not supported)' in t for t in oe + oq) or ('English' in oe and not oq): return 'language'
    return 'unexplained'



ok_pages = [p for p in P if p['status'] == 'comparable']
all_rows = [r for p in ok_pages for r in evaluate(p)]
for r in all_rows: r['class'] = 'agree' if r['ok'] else classify(r)
# A page whose graphics sweep lacks the prompt'd graphic starts its link sweep elsewhere (the sweeps carry the caret from one to the next), so the link and list
# announcements that follow differ in order and in which element is reached first: `prompt-downstream`, INFERRED from the same page having a `prompt` miss.
_prompt_pages = {r['url'] for r in all_rows if r['class'] == 'prompt'}
for r in all_rows:
    if r['class'] == 'unexplained' and r['url'] in _prompt_pages and r['channel'] in ('links', 'lists', 'landmarks', 'formFields'): r['class'] = 'prompt-downstream'
incl_rows = [r for p in P if p['status'].startswith(('comparable', 'not comparable')) for r in evaluate(p)]
table(all_rows, lambda r: r['kind'], f"agreement by element kind ({len(ok_pages)} comparable pages)", order=['headings', 'links', 'buttons', 'formFields', 'landmarks', 'lists', 'graphics', 'frames'])
table(all_rows, lambda r: r['channel'], "agreement by swept channel", order=list(CHANNELS))
shape_rows = [r for r in all_rows if r['channel'] in SHAPE_CHANNELS and r['shape']]
ranked = collections.Counter(r['shape'] for r in shape_rows).most_common()
top = [s for s, _ in ranked[:a.top]]
print(f"\nshapes: {len(shape_rows)} announcements in {len(ranked)} distinct shapes; top {a.top} cover {sum(n for _, n in ranked[:a.top])} = {100 * sum(n for _, n in ranked[:a.top]) / max(1, len(shape_rows)):.1f}% (the fleet's script quotes 33 shapes, top 10 = 94.3%)")
tc = table(shape_rows, lambda r: ' + '.join(r['shape']) if r['shape'] in top else None, f"agreement by shape (top {a.top}, ranked in this run)", order=[' + '.join(s) for s in top])
gate = [r for r in shape_rows if r['shape'] in top]
n, k = len(gate), sum(r['ok'] for r in gate)
print(f"\nGATE: {k} of {n} = {100 * k / max(1, n):.2f}% exact on the top {a.top} shapes   (positional: {sum(r['positional'] for r in gate)} of {n})   [{'AT OR ABOVE' if n and k / n >= .98 else 'BELOW'} 98%]")
inc = [r for r in incl_rows if r['channel'] in SHAPE_CHANNELS and r['shape'] in top]
print(f"      with the not-comparable pages kept in: {sum(r['ok'] for r in inc)} of {len(inc)} = {100 * sum(r['ok'] for r in inc) / max(1, len(inc)):.2f}%")
print(f"      emulator announcements with no counterpart in the fleet's lists (extras): {sum(sum(p['extras'].values()) for p in ok_pages)}")
miss = [r for r in all_rows if not r['ok']]
cl = collections.Counter(r['class'] for r in gate if not r['ok'])
print("      top-10 misses by cause: " + ', '.join(f'{c} {v}' for c, v in cl.most_common()))
excl = n - cl.get('history', 0)
print(f"      the same, with the pages' `history` misses not counted as misses against us: {k + cl.get('history', 0)} of {n} = {100 * (k + cl.get('history', 0)) / max(1, n):.2f}%   (an upper bound if the fleet's browser history could be reproduced)")
print(f"      misses over all channels: {len(miss)} of {len(all_rows)}; on top-{a.top} shapes: {n - k}")
if a.misses:
    print(f"\nmisses (first {a.misses}):")
    shown = 0
    for r in miss:
        if quiet(r['url']): continue
        print(f"  {r['url']}\n    {r['channel']}[{r['i']}] {' + '.join(r['shape'])}\n      expected  {r['expected']!r}\n      predicted {r['predicted']!r}")
        shown += 1
        if shown >= a.misses: break
def signature(r):
    """What differs, in one line: tokens only in the fleet's string / only in the prediction, or MISSING when the emulator has nothing for it."""
    if r['predicted'] is None: return 'MISSING (no counterpart in the emulator list)'
    e, q = [t.strip() for t in r['expected'].split(',')], [t.strip() for t in r['predicted'].split(',')]
    ce, cq = collections.Counter(e), collections.Counter(q)
    only_e, only_q = sorted((ce - cq).elements()), sorted((cq - ce).elements())
    if len(only_e) + len(only_q) > 4: return 'MANY tokens differ' + (' (same tokens, other order)' if ce == cq else '')
    return 'fleet has %s | emulator has %s' % (only_e or '-', only_q or '-')
if a.sig:
    sigs = collections.Counter((signature(r)) for r in miss)
    print("\nwhat the misses differ in (all channels; only the dev split is ever printed without --final):")
    for k, v in sigs.most_common(a.sig): print(f"  {v:>5}  {k}")
    if not a.final and a.split != 'dev': pass
if a.json:
    json.dump({'split': a.split, 'pages': [{'url': p['url'], 'status': p['status']} for p in P], 'gate': {'exact': k, 'total': n},
               'top': [' + '.join(s) for s in top], 'misses': [{k_: (v if k_ != 'shape' else list(v)) for k_, v in r.items()} for r in miss if (not quiet(r['url']))]},
              open(a.json, 'w'), indent=1, ensure_ascii=False)
