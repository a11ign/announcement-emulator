"""Attribute every miss of the Gate figure to a cause, with the evidence that shows it (A11-166).

    python attribute_gate.py <results dir> --oracle <dir> --emulator <dir> --probes <dir of the probes' outputs> --replay-run <dir> --downloads <dir>

Reads `misses-held-freeze.json` (the Gate figure's misses on the ten shapes, `check.py gate_misses`) and writes `misses-attributed.json` and one evidence file per cause under `evidence/`. A miss is attributed by the table `CAUSES`: the pages and entries
it covers, the class, the explanation, and where the cause was found. Every miss of the figure must be covered by exactly one cause, or this refuses. The causes were found by reading the fleet's record, the page's recorded bytes and the emulator against
NVDA's and Chromium's source, and each was tried on a copy of the frozen emulator (probes.py): nothing is fixed here.

Classes (the plan's): `emulator bug`, `Windows-only`, `method`, `unexplained`. The Gate's rule counts only the first two as passing."""
import sys, os, re, json, glob, argparse, difflib
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE); ROOT = os.path.dirname(Q3)
sys.path.insert(0, Q3); sys.path.insert(0, os.path.join(Q3, 'remeasure')); sys.path.insert(0, os.path.join(Q3, 'replay'))
import corpus_capture as cc, readback as rb, check


def lines_of(path, first, last):
    with open(path) as f: return [l.rstrip('\n') for l in f.read().splitlines()[first - 1:last]]


def find_line(path, needle):
    """(line number, the line) of the one line of a file that has `needle`."""
    with open(path) as f: hits = [(n, l.rstrip('\n')) for n, l in enumerate(f, 1) if needle in l]
    if len(hits) != 1: raise SystemExit(f'{path}: {len(hits)} lines have {needle!r}, the evidence quotes exactly one')
    return hits[0]


def disagreements(fleet, emulator):
    """The fleet's announcements the longest order-preserving exact matching leaves unmatched, as measure.py counts a miss."""
    ok = set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, fleet, emulator, autojunk=False).get_opcodes():
        if tag == 'equal': ok.update(range(i1, i2))
    return [fleet[i] for i in range(len(fleet)) if i not in ok]


def probe_result(oracle, emulator_dir, probe_dir, url, channels):
    """For one page and channel(s): the fleet's announcements the frozen emulator misses, and the ones a probe of it misses."""
    slug = cc.slug_of(url); fleet = rb.read_json(os.path.join(oracle, slug + '.json'))['capture']['structure']
    frozen = rb.read_json(os.path.join(emulator_dir, slug + '.run1.json'))['structure']; path = os.path.join(probe_dir, slug + '.run1.json')
    tried = rb.read_json(path)['structure'] if os.path.exists(path) else None
    return {'page': url, **{ch: {'frozen': disagreements(fleet[ch], frozen[ch]), 'probe': disagreements(fleet[ch], tried[ch]) if tried else None} for ch in channels}}


def fleet_lines(oracle, url, first, last):
    return rb.read_json(os.path.join(oracle, cc.slug_of(url) + '.json'))['capture']['transcript'][first:last]


class Sources:
    """Where the quoted lines and the probes' outputs are: read once, passed to the three causes."""
    def __init__(self, oracle, emulator_dir, probes, downloads, repo=ROOT):
        self.oracle, self.emulator_dir, self.probes = oracle, emulator_dir, probes
        self.chromium = os.path.join(downloads, 'chromium-src', 'ax_platform_node_win.cc'); self.storage = os.path.join(downloads, 'nvda-src', 'nvdaHelper', 'vbufBase', 'storage.cpp')
        self.standin, self.live = os.path.join(repo, 'emu', 'standin.py'), os.path.join(repo, 'emu', 'live.py')
        self.livepage, self.sweep = os.path.join(repo, 'q3', 'livepage.py'), os.path.join(repo, 'q3', 'sweep.py')

    def probe(self, name, pages, channels): return [probe_result(self.oracle, self.emulator_dir, os.path.join(self.probes, name), u, channels) for u in pages]


def empty_anchor_is_a_link(src, pages):
    node = rb.read_json(os.path.join(src.probes, 'node-sheffield.json')); linked_at = find_line(src.standin, "if s.get('linked'): out |= CONST['STATE_SYSTEM_LINKED']")
    with open(src.chromium) as f: chromium = f.read().splitlines()
    linked_src = next(n for n, l in enumerate(chromium, 1) if l.strip() == '// Handle STATE_SYSTEM_LINKED')
    return {
        'class': 'emulator bug', 'miss': 'You are here, navigation landmark, list, with N items, Home, link (the fleet) / main landmark, You are here, ... (the emulator)', 'pages': pages,
        'what the fleet read': {'page': pages[0], 'read-through lines 17 to 21': fleet_lines(src.oracle, pages[0], 17, 21), 'note': 'line 19 is a link with no name, which the fleet speaks as "out of list, main landmark, link": the first thing in <main> is an <a id="main-content"></a> with no href; the next line is the breadcrumb'},
        'what the emulator has': {'node of <a id="main-content">': node, 'note': 'role link, no name, no `linked` state (Chromium sets the AX state kLinked only for an anchor with an href)'},
        'how NVDA then speaks the breadcrumb': 'NVDA announces a landmark only when it is new to the control-field stack of what it spoke last (speech/speech.py:1584-1620, controlFieldStackCache). On the fleet the empty link inside <main> has just been spoken, so "main landmark" is not said again at the breadcrumb; in the emulator the empty link is not in the buffer, the previous link is the header menu, and "main landmark" is said.',
        'why the emulator lacks the link': {'chromium': {'file': 'ax_platform_node_win.cc', 'lines': [linked_src, linked_src + 3], 'text': chromium[linked_src - 1:linked_src + 3]},
                                            'emulator': {'file': 'emu/standin.py', 'line': linked_at[0], 'text': linked_at[1].strip()},
                                            'cause': 'Chromium on Windows reports STATE_SYSTEM_LINKED for every node whose role is a link; the emulator reports it only when the AX state `linked` is set, so an anchor with no href is not "in a link" (gecko_ia2 fillVBuf: in_link, interactive), is not interactive, and an empty node of no text leaves no line in the buffer'},
        'probe': {'change': 'standin.py line: `or r == \'link\'`', 'variant': 'linked', 'results': src.probe('out-linked', pages, ['links']),
                  'note': 'with the one change the empty link and the breadcrumb agree on every page; what is left on each page is the `Alt plus, m` access key, outside the ten shapes'}}


def page_scroll_state(src, pages):
    scroll_at = find_line(src.livepage, 'scroll_browser = False'); lazy_at = find_line(src.sweep, 'd.s.eval("window.scrollTo(0, 0)"); time.sleep(0.5)')
    return {
        'class': 'emulator bug', 'miss': 'an element a page shows only once it has been scrolled: ICO "Back to top, same page, link"; National Archives heading level 2 "<title>" and "Skip to end, same page, link"', 'pages': pages,
        'the pages': {'ico.org.uk': 'index.js: `function l(){0===window.scrollY?a.classList.add("opacity-0"):a.classList.remove("hidden","opacity-0")}` on a scroll listener rate-limited to 500 ms: the #button-top link is `hidden` until the page has been scrolled',
                      'caselaw.nationalarchives.gov.uk': 'document_navigation.js: an IntersectionObserver on the start of the document shows #js-document-navigation (`.autohide` is display:none, `.show` display:block; position:fixed) once it has scrolled out of view; the bar holds the h2 with the title and the "Back to top" and "Skip to end" links'},
        'what the emulator does': {'livepage.py': {'line': scroll_at[0], 'text': scroll_at[1].strip()}, 'sweep.py load_lazy_content': {'line': lazy_at[0], 'text': lazy_at[1].strip(), 'note': 'scrolls the page to its end for lazily loaded content and then back to the top; nothing scrolls it again, so every sweep reads the page at scrollY 0'},
                                   'on the fleet': 'NVDA scrolls the browser as its caret moves (IA2 scrollTo), so the page is scrolled when the sweeps run'},
        'probe': {'change': 'load_lazy_content leaves the page scrolled to its end', 'variant': 'page-left-at-end', 'results': src.probe('out-page-left-at-end', pages, ['headings', 'links']),
                  'note': 'on each page the announcements the frozen emulator misses are all agreed once the page is left scrolled'}}


def caret_after_a_menu_closes(src, pages):
    live_at = find_line(src.live, 'sel = (0, 0) if first else L.buffers[self.b._h].sel')
    trace = rb.read_json(glob.glob(os.path.join(src.probes, 'trace-' + cc.slug_of(pages[0]) + '.json'))[0])
    n0 = next(i for i, r in enumerate(trace) if r['key'] == 'enter' and 'Open menu' in trace[i - 1]['said'])
    fleet_record = rb.read_json(os.path.join(src.oracle, cc.slug_of(pages[0]) + '.json'))['capture']
    return {
        'class': 'emulator bug', 'miss': 'Close search, button, expanded (the fleet lists it between Open search and Close notification; the emulator does not reach it)', 'pages': pages,
        'what the fleet did': {'focus events of the probes (page order)': fleet_record['interaction']['focusEvents']['log'][:6], 'form fields it listed': fleet_record['structure']['formFields'][3:7],
                               'note': 'after the probe on "Open menu" (Enter opens the menu and focus goes into it; Escape closes it) the next backward step stops on "Open search"'},
        'what the emulator did': {'page': pages[0], 'keys from the probe on Open menu (key, announced, caret, line of the buffer the caret is on, focus)': [{k: r[k] for k in ('key', 'said', 'caret', 'lineText', 'focus')} for r in trace[n0 - 1:n0 + 4]],
                                  'note': 'Enter moves the caret into the opened menu (offset 206); Escape closes it and the menu\'s text leaves the buffer; the caret is still at offset 206, which is now the line of "Open search"; the next backward step starts before that line and passes "Open search"'},
        'why': {'nvda': {'file': 'nvdaHelper/vbufBase/storage.cpp', 'lines': [742, 760], 'text': lines_of(src.storage, 742, 744) + ['...'] + lines_of(src.storage, 760, 760), 'note': 'replaceSubtree corrects the selection to "the deepest field the selection started in that still exists", relative to that field'},
                'emulator': {'file': 'emu/live.py', 'line': live_at[0], 'text': live_at[1].strip(), 'note': 'refresh builds a new buffer and keeps the old selection as a number; node identifiers are renumbered at every read, so no field can be found again'}},
        'probe': {'change': 'the caret put back on the line of the control that was probed once the probe is over (probe_caret_back.py: a probe of the cause, not an implementation of storage.cpp)', 'variant': 'caret-back', 'results': src.probe('out-caret-back', pages, ['formFields']),
                  'note': '"Close search, button, expanded" agrees on both pages; what is left is the emulator\'s "banner landmark" prefix on "Open search", which is not a Gate miss (a shape outside the ten)'}}


def build(results, oracle, emulator_dir, probes, downloads, repo=ROOT):
    """(the Gate's misses, the evidence of each cause by file name, the pages each cause covers)."""
    gate = check.gate_misses(rb.read_json(os.path.join(results, 'misses-held-freeze.json'))); src = Sources(oracle, emulator_dir, probes, downloads, repo)
    by = lambda text: sorted({m['url'] for m in gate if text in m['url']})
    pages = {'sheffield': by('sheffield.ac.uk'), 'scroll': by('ico.org.uk') + by('caselaw.nationalarchives.gov.uk'), 'hes': by('historicenvironment.scot')}
    evidence = {'evidence/empty-anchor-is-a-link.json': empty_anchor_is_a_link(src, pages['sheffield']), 'evidence/page-scroll-state.json': page_scroll_state(src, pages['scroll']),
                'evidence/caret-after-a-menu-closes.json': caret_after_a_menu_closes(src, pages['hes'])}
    return gate, evidence, pages


def attribute(gate, pages, evidence_files):
    """One entry per miss, with the class and evidence of the cause that covers it; refuses a miss no cause covers."""
    cause_of = lambda m: ('evidence/empty-anchor-is-a-link.json' if m['url'] in pages['sheffield'] else 'evidence/page-scroll-state.json' if m['url'] in pages['scroll'] else 'evidence/caret-after-a-menu-closes.json' if m['url'] in pages['hes'] else None)
    out = []
    for m in gate:
        file = cause_of(m)
        if file is None: raise SystemExit(f'no cause covers {m["url"]} {m["channel"]}[{m["i"]}] {m["expected"][:50]!r}')
        e = evidence_files[file]
        out.append({'page': m['url'], 'channel': m['channel'], 'i': m['i'], 'expected': m['expected'], 'predicted': m['predicted'], 'class': e['class'], 'evidence': [file], 'why': e['miss']})
    return out


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('results'); ap.add_argument('--oracle', required=True); ap.add_argument('--emulator', required=True); ap.add_argument('--probes', required=True); ap.add_argument('--downloads', required=True); a = ap.parse_args(argv)
    gate, evidence, pages = build(a.results, a.oracle, a.emulator, a.probes, a.downloads)
    os.makedirs(os.path.join(a.results, 'evidence'), exist_ok=True)
    for name, data in evidence.items(): rb.write_json(os.path.join(a.results, name), data)
    entries = attribute(gate, pages, evidence)
    rb.write_json(os.path.join(a.results, 'misses-attributed.json'), {'misses': entries})
    print(f'{len(entries)} misses attributed:', {c: sum(1 for e in entries if e['class'] == c) for c in sorted({e['class'] for e in entries})})


if __name__ == '__main__': main(sys.argv[1:])
