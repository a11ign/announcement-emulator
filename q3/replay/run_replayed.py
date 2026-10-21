"""Run the emulator over every page of an oracle directory, each page read through a replay server loaded with that page's archive (A11-165).

    python run_replayed.py <oracle_dir> <out_dir> --run <run dir> [--root <emulator checkout>] [--split dev|held|all] [--jobs 6] [--runs 2] [--port-base 9100] [--only substring] [--logs <dir>]

The same two runs a page as q3/run_all.py (`<out_dir>/<slug>.run<k>.json`, emulate.py's output, a page already done is skipped), at the page's ORIGINAL address, which is what the oracle record names: the proxy answers it from
`<run dir>/archives/<slug>.flows`, as it answers the fleet's Edge. `--root` is the checkout whose emulate.py is run: the frozen worktree for the Gate figure, this one for head. What the proxy served each run is
`<logs>/<slug>.run<k>.json` (default `<out_dir>/served`). Needs the replay virtualenv for the proxy and the emulator's own for the emulator."""
import sys, os, glob, subprocess, argparse, time, queue, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, Q3); sys.path.insert(0, HERE)
from split import split_of
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'remeasure'))
import readback as rb
import proxy as px
from process import run_in_group, TIMED_OUT
from paths import DOWNLOADS

EMU_PYTHON = str(DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python')


def command_for(run_dir, slug, root, url, out, port, log, timeout, python=EMU_PYTHON):
    """The command that reads one page once: the proxy wrapper around the emulator."""
    return [str(px.VENV / 'python'), os.path.join(HERE, 'with_replay.py'), '--run', run_dir, '--archive', slug + '.flows', '--log', log, '--timeout', str(timeout), '--',
            python, os.path.join(root, 'q3', 'emulate.py'), url, out, '--port', str(port)]


def pages_of(oracle, split, only):
    pages = []
    for f in sorted(glob.glob(os.path.join(oracle, '*.json'))):
        try: rec = rb.read_json(f)
        except Exception: continue
        url = (rec.get('capture') or {}).get('url')
        if not url or only not in url: continue
        if split != 'all' and split_of(url) != split: continue
        pages.append((os.path.basename(f)[:-5], url))
    return pages


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('oracle'); ap.add_argument('out'); ap.add_argument('--run', required=True); ap.add_argument('--root', default=os.path.dirname(Q3))
    ap.add_argument('--split', default='dev', choices=['dev', 'held', 'all']); ap.add_argument('--jobs', type=int, default=6); ap.add_argument('--runs', type=int, default=2); ap.add_argument('--only', default='')
    ap.add_argument('--port-base', type=int, default=9100); ap.add_argument('--timeout', type=int, default=900); ap.add_argument('--logs')
    a = ap.parse_args(argv)
    logs = a.logs or os.path.join(a.out, 'served'); os.makedirs(a.out, exist_ok=True); os.makedirs(logs, exist_ok=True)
    pages = pages_of(a.oracle, a.split, a.only)
    print(f'{len(pages)} pages, split={a.split}, {a.runs} runs each, {a.jobs} at a time, emulator at {os.path.basename(os.path.abspath(a.root))}', flush=True)

    def one(slot, slug, url):
        for k in range(1, a.runs + 1):
            out = os.path.join(a.out, f'{slug}.run{k}.json')
            if os.path.exists(out): continue
            t = time.time()
            try:
                code = run_in_group(command_for(a.run, slug, a.root, url, out + '.part', a.port_base + 2 * slot, os.path.join(logs, f'{slug}.run{k}.json'), a.timeout), a.timeout + 120)      # the wrapper ends the command at the timeout and keeps the proxy's log; this is for a wrapper that hangs
                if os.path.exists(out + '.part'): os.replace(out + '.part', out)
                elif code == TIMED_OUT: rb.write_json(out, {'url': url, 'fault': f'timeout {a.timeout}s'})
                fault = rb.read_json(out).get('fault') if os.path.exists(out) else 'no output'
            except subprocess.TimeoutExpired:
                fault = f'timeout {a.timeout}s'; rb.write_json(out, {'url': url, 'fault': fault})
            print(f'  slot {slot} {slug} run{k} {round(time.time() - t)}s {fault or "ok"}', flush=True)

    free = queue.Queue()
    for s in range(a.jobs): free.put(s)

    def job(p):
        s = free.get()
        try: one(s, *p)
        finally: free.put(s)
    with cf.ThreadPoolExecutor(a.jobs) as ex: list(ex.map(job, pages))
    print('done', flush=True)


if __name__ == '__main__': main(sys.argv[1:])
