"""A static copy of every address of the corpus, several at a time (A11-155).

    python snapshot_all.py <corpus.json> <out_root> [--jobs 6] [--only substring] [--frames srcdoc|files] [--lazy keep|eager] [--index static-pages.json]

`<out_root>/<slug>/index.html` and `meta.json` for each address (snapshot.mjs; the slug is corpus_capture.slug_of). A page already done is kept, so an interrupted batch resumes. Prints one line a page and a summary;
exit 1 if any page has no copy. The copies are third-party's pages and are served, not committed: what is committed is `static-pages.json` (address, slug, title, size) from `--index`."""
import sys, os, json, subprocess, argparse, concurrent.futures as cf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import corpus_capture as cc

HERE = os.path.dirname(os.path.abspath(__file__))


def snapshot(url, out_root, options=(), timeout=240):
    dest = os.path.join(out_root, cc.slug_of(url))
    if os.path.exists(os.path.join(dest, 'meta.json')): return url, 'kept'
    try:
        done = subprocess.run(['node', os.path.join(HERE, 'snapshot.mjs'), url, dest, *options], capture_output=True, text=True, timeout=timeout)
        return url, 'ok' if done.returncode == 0 and os.path.exists(os.path.join(dest, 'meta.json')) else 'failed: ' + (done.stderr.strip() or done.stdout.strip())[-160:]
    except subprocess.TimeoutExpired:
        return url, f'failed: no copy in {timeout} s'


def served_bytes(directory): return sum(os.path.getsize(os.path.join(directory, f)) for f in os.listdir(directory) if f != 'meta.json')


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('corpus'); ap.add_argument('out'); ap.add_argument('--jobs', type=int, default=6); ap.add_argument('--only', default=''); ap.add_argument('--index'); ap.add_argument('--frames', default='srcdoc'); ap.add_argument('--lazy', default='keep')
    a = ap.parse_args(argv)
    urls = [e['url'] for e in json.load(open(a.corpus)) if a.only in e['url']]
    os.makedirs(a.out, exist_ok=True); failed = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for url, state in ex.map(lambda u: snapshot(u, a.out, ('--frames', a.frames, '--lazy', a.lazy)), urls):
            print(cc.slug_of(url), state, flush=True)
            if state.startswith('failed'): failed.append(url)
    index = []
    for url in urls:
        meta = os.path.join(a.out, cc.slug_of(url), 'meta.json')
        if os.path.exists(meta):
            m = json.load(open(meta)); index.append({'url': url, 'slug': cc.slug_of(url), 'finalAddress': m['finalAddress'], 'title': m['title'], 'elements': m['elements'], 'bytes': served_bytes(os.path.join(a.out, cc.slug_of(url))), 'iframes': m['iframes'], 'frames': m.get('frames', 'srcdoc'), 'lazy': m.get('lazy', 'keep'),
                                                     'stylesheetsInlined': m['stylesheetsInlined'], 'snapshotAt': m['snapshotAt']})
    if a.index: json.dump(index, open(a.index, 'w'), indent=1)
    print(f'{len(index)} of {len(urls)} pages have a copy; failed: {failed}')
    sys.exit(1 if failed or len(index) != len(urls) else 0)


if __name__ == '__main__': main(sys.argv[1:])
