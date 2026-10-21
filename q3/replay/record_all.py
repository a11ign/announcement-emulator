"""Record every address of the corpus once, with its scripts and every resource it loads, into one archive each (A11-165).

    python record_all.py <corpus.json> <run dir> [--jobs 6] [--only substring] [--manifest manifest.json]

`<run dir>/archives/<slug>.flows` for each address (the slug is corpus_capture.slug_of), written by a recording proxy that the emulator's own Chrome 155 loads the page through (record.mjs: Edge's user agent, the 1008x872
window, scrolled to the end and back). The run's CA is made on first use in `<run dir>/ca` and stays there. An address already recorded is kept, so an interrupted batch resumes; an address whose page did not load
(its own address got no response) is not kept and is named. `--manifest` writes what is committed of the archives: the run's id and, for each address, its archive file, its sha256, the number of exchanges, the hosts, the status the address ended on and when it was
recorded. A page recorded with an error status is served with status 200 (`write_served_status`). The archives hold third-party pages and are not committed."""
import sys, os, json, argparse, hashlib, subprocess, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import corpus_capture as cc
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'remeasure'))
import readback as rb
import proxy as px
import ca as cert_names

VENV_PY = str(px.VENV / 'python')


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def ensure_ca(run_dir):
    ca_dir = os.path.join(run_dir, 'ca')
    if not os.path.exists(os.path.join(ca_dir, 'mitmproxy-ca-cert.pem')):
        subprocess.run([VENV_PY, os.path.join(HERE, 'ca.py'), 'init', ca_dir], check=True, capture_output=True)
    return cert_names.identify(os.path.join(ca_dir, 'mitmproxy-ca-cert.pem'))


def write_served_status(run_dir, record):
    """A page recorded with an error status (a site down for maintenance) is served with status 200, its body as recorded: the fleet's worker refuses to capture a page the server answered with anything but 2xx, so a page
    recorded so could not be read at all. The sidecar `<archive>.served.json` says so, and the manifest carries `servedStatus`. Pages recorded with a 2xx status have neither."""
    status = record['mainStatus']
    if 200 <= status < 300: return record
    sidecar = os.path.join(run_dir, record['archive'] + '.served.json')
    rb.write_json(sidecar, {'address': record['endedAt'], 'recordedStatus': status, 'servedStatus': 200, 'why': 'the worker refuses a page the server answered with other than 2xx; the body is the recording\'s'})
    return {**record, 'servedStatus': 200}


def record_one(url, run_dir, spki, timeout=240):
    """('ok', info) or ('failed: why', None). The archive is moved into place only when the page's own address got a response."""
    slug = cc.slug_of(url); archives = os.path.join(run_dir, 'archives'); dest = os.path.join(archives, slug + '.flows'); part = dest + '.part'; meta = dest + '.meta.json'
    if os.path.exists(dest) and os.path.exists(meta): return 'kept', rb.read_json(meta)
    p = px.start_record(os.path.join(run_dir, 'ca'), part)
    try:
        p.wait_listening()
        done = subprocess.run(['node', os.path.join(HERE, 'record.mjs'), url, f'127.0.0.1:{p.port}', spki, meta + '.page'], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f'failed: no recording in {timeout} s', None
    finally: p.stop()
    if not os.path.exists(part): return 'failed: no archive written', None
    info = json.loads(subprocess.run([VENV_PY, os.path.join(HERE, 'flows.py'), 'info', part, url], capture_output=True, text=True, check=True).stdout)
    page = rb.read_json(meta + '.page') if os.path.exists(meta + '.page') else {}
    if info['mainStatus'] is None: os.remove(part); return f'failed: the page\'s own address got no response ({done.stderr.strip()[-100:] or page.get("navigateError")})', None
    os.replace(part, dest)
    record = {'url': url, 'slug': slug, 'archive': f'archives/{slug}.flows', 'sha256': sha256_of(dest), 'bytes': os.path.getsize(dest), **{k: info[k] for k in ('requests', 'hosts', 'mainStatus', 'endedAt')},
              'finalAddress': page.get('finalAddress'), 'title': page.get('title'), 'recordedAt': page.get('recordedAt')}
    rb.write_json(meta, record)
    if os.path.exists(meta + '.page'): os.remove(meta + '.page')
    return 'ok', record


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('corpus'); ap.add_argument('run'); ap.add_argument('--jobs', type=int, default=6); ap.add_argument('--only', default=''); ap.add_argument('--manifest')
    a = ap.parse_args(argv)
    urls = [e if isinstance(e, str) else e['url'] for e in rb.read_json(a.corpus)]
    os.makedirs(os.path.join(a.run, 'archives'), exist_ok=True)
    spki = ensure_ca(a.run)['spki']; failed = []; records = {}
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for url, (state, rec) in zip([u for u in urls if a.only in u], ex.map(lambda u: record_one(u, a.run, spki), [u for u in urls if a.only in u])):
            print(cc.slug_of(url), state, (f'{rec["requests"]} exchanges, {rec["hosts"]} hosts, status {rec["mainStatus"]}' if rec else ''), flush=True)
            if rec: records[url] = write_served_status(a.run, rec)
            else: failed.append(url)
    if a.manifest:
        rb.write_json(a.manifest, {'runId': os.path.basename(os.path.normpath(a.run)), 'pages': [records[u] for u in urls if u in records]})
    print(f'{len(records)} of {len([u for u in urls if a.only in u])} addresses recorded; failed: {failed}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__': main(sys.argv[1:])
