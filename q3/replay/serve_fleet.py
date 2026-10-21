"""One replay server for each fleet box, on this machine (A11-165).

    python serve_fleet.py <run dir> <worker=port> [<worker=port> ...] [--listen 0.0.0.0]

Each box is behind its own server, on its own port, because several boxes capture at once and each reads a different page (`capture_hooks.FleetReplay` loads each page's archive into the box's server before the capture).
Every server starts with the archive-only probe page (`probe.flows`) loaded. Runs until it is stopped (SIGINT or SIGTERM), then stops every server. Prints `ready` once all answer."""
import sys, os, signal, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proxy as px


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('workers', nargs='+'); ap.add_argument('--listen', default='0.0.0.0'); a = ap.parse_args(argv)
    ports = dict(w.split('=') for w in a.workers); servers = {}
    stop = []; signal.signal(signal.SIGTERM, lambda *_: stop.append(1)); signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    try:
        for name, port in ports.items(): servers[name] = px.start_replay(os.path.join(a.run, 'ca'), os.path.join(a.run, 'archives'), archive='probe.flows', port=int(port), host=a.listen)
        for s in servers.values(): s.wait_ready()
        print('ready', ' '.join(f'{n}={p}' for n, p in ports.items()), flush=True)
        while not stop and all(s.process.poll() is None for s in servers.values()): time.sleep(1)
        dead = [n for n, s in servers.items() if s.process.poll() is not None]
        if dead: print('a server exited:', ', '.join(dead), file=sys.stderr)
    finally:
        for s in servers.values(): s.stop()


if __name__ == '__main__': main(sys.argv[1:])
