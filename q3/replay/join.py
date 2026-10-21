"""Prove that the fleet and the emulator were served the same bytes (A11-165): the replay servers' logs of each page, joined into one committed summary.

    python join.py <manifest.json> <fleet logs dir> <summary.json> --emulator label=<logs dir> [--emulator label=<logs dir> ...] [--explained explained.json]

For every page of the manifest it reads the fleet's log (`<slug>.<worker>.json`, one) and each emulator run's log (`<slug>.run<k>.json` under each `--emulator` directory), checks that every one was served from the archive the
manifest names (its sha256), and joins the fleet's log with each emulator run's (archive.page_join): what each side asked for, and the requests the archive did not answer on one side that it answered on the other.
Requests to a browser's own services (`BROWSER_OWN`) are counted in each side's totals but are not compared: they are the browsers' background traffic, which differs by browser, and are not the page's. `--explained` is a
JSON object of `<slug>: <reason>` for the pages whose difference the write-up explains; the check (check.py `served`) accepts a difference only for a page named there."""
import sys, os, glob, argparse
from urllib.parse import urlsplit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import page_join, summarise
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'remeasure'))
import readback as rb

BROWSER_OWN = ('clients2.google.com', 'update.googleapis.com', 'mtalk.google.com', 'android.clients.google.com', 'optimizationguide-pa.googleapis.com', 'content-autofill.googleapis.com', 'safebrowsing.googleapis.com',
               'edge.microsoft.com', 'config.edge.microsoft.com', 'msedge.api.cdp.microsoft.com', 'edgedl.me.gvt1.com', 'redirector.gvt1.com',
               'nav-edge.smartscreen.microsoft.com', 'xpaywalletcdn-prod.azureedge.net')


def is_browser_own(request): return (urlsplit(request['url']).hostname or request['url'].split(':')[0]) in BROWSER_OWN


def split_own(log):
    """(the page's requests, the browser's own): a log's requests told apart by host."""
    return [r for r in log if not is_browser_own(r)], [r for r in log if is_browser_own(r)]


def read_log(path): return rb.read_json(path)


def join_page(page, fleet_log, emulator_logs):
    """One page's entry: the archive it was served from on each side, each side's totals, and the differences."""
    f_page, f_own = split_own(fleet_log['requests'])
    entry = {'url': page['url'], 'slug': page['slug'], 'archiveSha256': page['sha256'], 'fleet': {'worker': fleet_log.get('worker'), 'archiveSha256': fleet_log['sha256'], **summarise(f_page), 'browserOwn': len(f_own)}, 'emulator': {}, 'differences': []}
    for label, log in sorted(emulator_logs.items()):
        e_page, e_own = split_own(log['requests'])
        j = page_join(f_page, e_page)
        entry['emulator'][label] = {'archiveSha256': log['sha256'], **j['emulator'], 'browserOwn': len(e_own)}
        for key in ('missedOnFleetAnsweredOnEmulator', 'missedOnEmulatorAnsweredOnFleet'):
            entry['differences'] += [{'run': label, 'kind': key, 'request': r} for r in j[key]]
    return entry


def build(manifest, fleet_dir, emulator_dirs, explained=None):
    pages = []; explained = explained or {}
    for page in manifest['pages']:
        slug = page['slug']; fleet = glob.glob(os.path.join(fleet_dir, f'{slug}.*.json'))
        emulator = {f'{label}.{os.path.basename(f)[len(slug) + 1:-5]}': read_log(f) for label, d in emulator_dirs.items() for f in sorted(glob.glob(os.path.join(d, f'{slug}.run*.json')))}
        if len(fleet) != 1 or not emulator: pages.append({'url': page['url'], 'slug': slug, 'missing': f'{len(fleet)} fleet logs, {len(emulator)} emulator logs'}); continue
        entry = join_page(page, read_log(fleet[0]), emulator)
        if slug in explained: entry['explained'] = explained[slug]
        pages.append(entry)
    return {'browserOwn': list(BROWSER_OWN), 'pages': pages}


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('manifest'); ap.add_argument('fleet'); ap.add_argument('summary'); ap.add_argument('--emulator', action='append', default=[]); ap.add_argument('--explained')
    a = ap.parse_args(argv)
    emulators = dict(x.split('=', 1) for x in a.emulator)
    summary = build(rb.read_json(a.manifest), a.fleet, emulators, rb.read_json(a.explained) if a.explained else None)
    rb.write_json(a.summary, summary)
    bad = [p for p in summary['pages'] if p.get('differences') or p.get('missing')]
    print(f'{len(summary["pages"])} pages joined; {len(bad)} with a difference or a missing log')


if __name__ == '__main__': main(sys.argv[1:])
