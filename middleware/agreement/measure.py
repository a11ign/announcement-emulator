"""Question 5 of A11-208: how often the passive predictions are the words the fleet's NVDA said for the same actions, by announcement shape.

    python3 measure.py --fleet <dir> --passive <report.json> <report.json> --pages <pages.json> [--freeze <freeze.json>] [--out <dir>]

Inputs. `--fleet` holds the worker's records, two for each page: `<slug>.f1.json` and `<slug>.f2.json`, as q3/fleet_capture.mjs writes them. `--passive` is the Playwright JSON report of each of two
runs of the sample suite's corpus project; a test's `predicted-nvda-speech.json` attachment is its prediction. A page's slug is `slug()` of its address.

Definitions, fixed before the first fleet capture of this ticket (they are among the files `freeze.json` names):
  channel   what the same actions produced on both sides:
              stops     the phrase for each Tab stop. The fleet's focus probe presses Tab and then asks NVDA to repeat the focus (NVDA+Tab) and records that phrase (`interaction.focusOrder`);
                        the prediction is what NVDA says when asked to repeat the focus on the node the page's focusin names (`repeatFocus`), for each stop of the walk;
              typed     the echo of the six digits typed into the first text field (`interaction.typedFeedback.echoed`) against the characters predicted for the same keys;
              field     the phrase for that field when it has the focus (`typedFeedback.focusBefore`) against `repeatFocus` of the focus move the click made;
              title     the document's title as spoken at the load (`documentReady`) against the first utterance of the predicted load;
              headings, landmarks, formFields, graphics, links, lists, frames
                        the lists of the fleet's structure sweep (`structure`) against the lists of the first sweep the middleware ran, over the tree at the load.
  unit      one announcement of the fleet's record in a channel; the fleet is the oracle.
  exact     byte-equal strings. (`title` is compared after the normal form q3/measure.py uses: the fleet's title is what NVDA spoke, "GOV dot UK", and the page's is "GOV.UK".)
  agreed    an oracle unit is agreed when it is in the longest order-preserving matching of the two lists by exact equality (difflib, autojunk off), as q3/measure.py counts: one missing or extra
            element costs one miss and not every one after it.
  shape     q3/shapes.py's shape of the oracle's unit (ROLE, STATE, NAME, LEVEL, COUNT, POSITION); the shapes are ranked by the number of units over every channel.
  stable    both fleet captures of the page give the same list in the channel, and both passive runs do. A channel that is not stable on a page is counted and not compared.
  comparable the page's title and its heading and link counts are the same in the fleet's census and the tree. A page that is not is listed and not compared.
Beside the figure: the two fleet captures against each other and the two passive runs against each other, by the same rules, so that how far the page itself moves between two readings is on the page.
Nothing here writes an a11ign evidence field: the output is a measurement of a prediction (ADR 0047)."""
import argparse, base64, collections, difflib, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'q3'))
from shapes import shape_of      # noqa: E402  (q3/shapes.py reads NVDA's source from $EMU_DOWNLOADS)

LISTS = ('headings', 'landmarks', 'formFields', 'graphics', 'links', 'lists', 'frames')
CHANNELS = ('title', 'stops', 'field', 'typed') + LISTS


def slug(address): return re.sub(r'[^a-z0-9]+', '-', re.sub(r'^https?://', '', address.lower())).strip('-')[:80] + '-' + hashlib.sha256(address.encode()).hexdigest()[:8]


def norm(title):
    """q3/measure.py's normal form of a title."""
    return re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\bdot\b', ' ', (title or '').lower().replace('​', ''))).strip()


# ---- what each side said, as lists per channel

def fleet_channels(record):
    """The oracle's lists, or None if the capture did not succeed."""
    cap = (record or {}).get('capture') or {}
    if (record or {}).get('status') != 200 or cap.get('error') or 'structure' not in cap: return None
    interaction, typed = cap.get('interaction') or {}, (cap.get('interaction') or {}).get('typedFeedback') or {}
    title = next((e.get('title') for e in cap.get('diagnostics', []) if e.get('event') == 'documentReady'), None)
    out = {'title': [title] if title else [], 'stops': list(interaction.get('focusOrder') or []), 'field': [typed['focusBefore']] if typed.get('typed') and typed.get('focusBefore') else [],
           'typed': (typed.get('echoed') or '').split() if typed.get('typed') else []}
    out.update({ch: list(cap['structure'].get(ch, [])) for ch in LISTS})
    return out


def fleet_census(record):
    for e in ((record or {}).get('capture') or {}).get('diagnostics', []):
        if e.get('event') == 'structureCensus': return {k: e.get(k) for k in ('heading', 'link')}
    return None


def passive_channels(prediction):
    """The predicted lists from a test's `predicted-nvda-speech.json`, and the census of the tree it swept."""
    speech = prediction['predictedSpeech']
    loads = [s for s in speech if s['cause'] == 'load']
    first_typed = next((i for i, s in enumerate(speech) if s['cause'] == 'typed'), None)
    focus = [s for i, s in enumerate(speech) if s['cause'] == 'focus' and (first_typed is None or i < first_typed)]
    field = focus.pop() if first_typed is not None and focus else None      # the click that put the focus in the text field is the last move before the typing, and is not a stop of the walk
    sweep = next((s for s in prediction['sweeps'] if s['trigger'] == 'load'), None)
    out = {'title': [re.sub(r',? document$', '', loads[0]['utterances'][0])] if loads else [], 'stops': [s.get('repeatFocus', s['text']) for s in focus],
           'field': [field.get('repeatFocus', field['text'])] if field else [], 'typed': [s['text'] for s in speech if s['cause'] == 'typed']}
    out.update({ch: list(((sweep or {}).get('lists') or {}).get(ch, [])) for ch in LISTS})
    return out, ((sweep or {}).get('census') or None)


def passive_predictions(report):
    """{address: prediction} for the corpus tests of a Playwright JSON report."""
    found = {}
    def walk(suite):
        for s in suite.get('suites', []): walk(s)
        for spec in suite.get('specs', []):
            m = re.match(r'keyboard walk of (\S+)$', spec['title'])
            if not m: continue
            for t in spec['tests']:
                att = {a['name']: a for a in t['results'][-1]['attachments']}
                if 'predicted-nvda-speech.json' in att: found[m.group(1)] = json.loads(base64.b64decode(att['predicted-nvda-speech.json']['body']))
    walk({'suites': report['suites']})
    return found


# ---- comparing two lists

def matching(oracle, predicted):
    """(indexes of oracle units in the longest order-preserving matching, {index: the predicted unit that stands in its place})."""
    matched, stands = set(), {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, oracle, predicted, autojunk=False).get_opcodes():
        if tag == 'equal': matched.update(range(i1, i2))
        elif tag == 'replace':
            for n in range(i2 - i1): stands[i1 + n] = predicted[j1 + n] if j1 + n < j2 else None
    return matched, stands


def compare(channel, oracle, predicted):
    if channel == 'title': oracle, predicted = [norm(x) for x in oracle], [norm(x) for x in predicted]
    matched, stands = matching(oracle, predicted)
    return [{'channel': channel, 'i': i, 'expected': text, 'predicted': text if i in matched else stands.get(i), 'ok': i in matched, 'shape': list(shape_of(text))} for i, text in enumerate(oracle)]


def classify(row):
    """The cause of a miss where a rule with evidence names one (q3/measure.py's `classify`, which is this ticket's too); anything else is `unexplained`."""
    e, q = row['expected'], row['predicted']
    if 'Unlabelled graphic' in e or 'To get missing image descriptions' in e: return 'prompt'
    if q is None: return 'no counterpart'
    te, tq = [t.strip() for t in e.split(',')], [t.strip() for t in q.split(',')]
    if te != tq and [t for t in te if t != 'visited'] == [t for t in tq if t != 'visited']: return 'history'
    ce, cq = collections.Counter(te), collections.Counter(tq)
    oe, oq = list((ce - cq).elements()), list((cq - ce).elements())
    if any('(not supported)' in t for t in oe + oq) or ('English' in oe and not oq): return 'language'
    return 'unexplained'


def comparable(fleet_rec, fleet_c, passive_c, passive_census):
    """Whether the page was the same page on both sides: its title, and its heading and link counts."""
    problems = {}
    ft, pt = norm((fleet_c['title'] or [''])[0]), norm((passive_c['title'] or [''])[0])
    if ft and pt and ft[:25] not in pt and pt[:25] not in ft: problems['title'] = (ft[:40], pt[:40])
    fc = fleet_census(fleet_rec)
    if fc and passive_census:
        for k in ('heading', 'link'):
            if fc.get(k) is not None and fc[k] != passive_census.get(k): problems[k] = (fc[k], passive_census.get(k))
    return problems


def measure(pages, fleet, passive_runs):
    """rows, per-page status. `fleet[slug] = [f1, f2]` records; `passive_runs = [{address: prediction}, {address: prediction}]`."""
    rows, status = [], {}
    for address in pages:
        key = slug(address)
        f1, f2 = (fleet.get(key) or [None, None])[:2]
        c1, c2 = fleet_channels(f1), fleet_channels(f2)
        preds = [run.get(address) for run in passive_runs]
        if c1 is None: status[address] = {'status': 'no fleet reading'}; continue
        if preds[0] is None: status[address] = {'status': 'no passive reading'}; continue
        p1, census1 = passive_channels(preds[0])
        p2 = passive_channels(preds[1])[0] if len(preds) > 1 and preds[1] else None
        problems = comparable(f1, c1, p1, census1)
        if problems: status[address] = {'status': 'not comparable', 'problems': {k: list(v) for k, v in problems.items()}}; continue
        status[address] = {'status': 'comparable', 'unstable': []}
        for ch in CHANNELS:
            stable_fleet = c2 is None or c1[ch] == c2[ch]
            stable_passive = p2 is None or p1[ch] == p2[ch]
            if not (stable_fleet and stable_passive):
                status[address]['unstable'].append({'channel': ch, 'fleet': stable_fleet, 'passive': stable_passive}); continue
            for r in compare(ch, c1[ch], p1[ch]): rows.append({'address': address, 'kind': 'fleet-vs-passive', **r})
            if c2 is not None:
                for r in compare(ch, c1[ch], c2[ch]): rows.append({'address': address, 'kind': 'fleet-vs-fleet', **r})
            if p2 is not None:
                for r in compare(ch, p1[ch], p2[ch]): rows.append({'address': address, 'kind': 'passive-vs-passive', **r})
    for r in rows: r['class'] = 'agree' if r['ok'] else classify(r)
    return rows, status


# ---- the tables

def tally(rows, key):
    t = collections.OrderedDict()
    for r in rows:
        c = t.setdefault(key(r), [0, 0]); c[0] += r['ok']; c[1] += 1
    return t


def rate(ok, n): return f'{100 * ok / n:.1f}%' if n else 'n/a'


def report(rows, status, top=10):
    lines = []
    out = lines.append
    kinds = ('fleet-vs-passive', 'fleet-vs-fleet', 'passive-vs-passive')
    out(f"pages {len(status)}: " + ', '.join(f'{k} {v}' for k, v in collections.Counter(s['status'] for s in status.values()).items()))
    for a, s in status.items():
        if s['status'] != 'comparable': out(f"  {s['status']}: {a} {s.get('problems', '')}")
        elif s['unstable']: out(f"  unstable channels on {a}: {', '.join(u['channel'] for u in s['unstable'])}")
    main = [r for r in rows if r['kind'] == 'fleet-vs-passive']
    ranked = collections.Counter(' + '.join(r['shape']) for r in main).most_common()
    shapes = [s for s, _ in ranked[:top]]
    for title, key, order in (('by channel', lambda r: r['channel'], list(CHANNELS)), (f'by shape (the {top} commonest of the fleet\'s units)', lambda r: ' + '.join(r['shape']) if ' + '.join(r['shape']) in shapes else None, shapes)):
        out(f'\nagreement {title}: the passive predictions against the fleet / the fleet against itself / the passive runs against each other')
        tallies = {k: tally([r for r in rows if r['kind'] == k], key) for k in kinds}
        for label in order:
            cells = []
            for k in kinds:
                ok, n = tallies[k].get(label, [0, 0]); cells.append(f'{ok:>5} / {n:<5} {rate(ok, n):>6}')
            if tallies['fleet-vs-passive'].get(label, [0, 0])[1]: out(f'  {" | ".join(cells)}  {label or "(other shapes)"}')
    ok, n = sum(r['ok'] for r in main), len(main)
    out(f'\nall channels: {ok} of {n} units agreed = {rate(ok, n)}')
    top_rows = [r for r in main if ' + '.join(r['shape']) in shapes]
    out(f'the {top} commonest shapes: {sum(r["ok"] for r in top_rows)} of {len(top_rows)} = {rate(sum(r["ok"] for r in top_rows), len(top_rows))}')
    out('\nmisses by cause (all channels): ' + ', '.join(f'{c} {v}' for c, v in collections.Counter(r['class'] for r in main if not r['ok']).most_common()))
    return '\n'.join(lines)


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('--fleet', required=True); ap.add_argument('--passive', nargs='+', required=True); ap.add_argument('--pages', required=True)
    ap.add_argument('--freeze'); ap.add_argument('--out'); ap.add_argument('--top', type=int, default=10)
    a = ap.parse_args(argv)
    with open(a.pages) as f: pages = [p['url'] for p in json.load(f)['sample']]
    fleet = {}
    def load(path):
        if not os.path.exists(path): return None
        with open(path) as f: return json.load(f)
    for address in pages: fleet[slug(address)] = [load(os.path.join(a.fleet, f'{slug(address)}.f{k}.json')) for k in (1, 2)]
    runs = [passive_predictions(load(p)) for p in a.passive]
    rows, status = measure(pages, fleet, runs)
    text = report(rows, status, a.top)
    print(text)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, 'agreement.txt'), 'w') as f: f.write(text + '\n')
        with open(os.path.join(a.out, 'agreement.json'), 'w') as f: json.dump({'status': status, 'rows': rows}, f, indent=1, ensure_ascii=False)


if __name__ == '__main__': main(sys.argv[1:])
