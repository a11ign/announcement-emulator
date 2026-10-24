"""The runtime process (A11-208): started by the middleware, one for each Playwright worker, it reads what the test's browser reports and writes predicted speech as JSON lines.

    python -I main.py --port <collector port> [--cdp <the browser's DevTools port>] [--no-sweeps]

stdout carries the protocol and nothing else (NVDA's own prints go to stderr):
    {"type": "ready", "bootMs": n}                              once NVDA is up and the collector is listening
    {"type": "record", "rec": {...}}                            each prediction, as it is made: kind is speech, observe, sweep or flag
    {"type": "drained", "id": n, "stats": {...}}                the answer to a drain
stdin: {"cmd": "drain", "id": n} (finish what is queued, run the sweeps, derive the flags), {"cmd": "quit"}.

This is GPL code, as the emulator is. The middleware that starts it is a separate program and never imports it (ADR 0047, Decision 3).
"""
import argparse, http.server, json, os, queue, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
QUIET = 0.25      # seconds without anything new before a drain takes the queue as complete
REORDER_WAIT = 0.4      # how long a snapshot is held for the one before it, which was posted first and may arrive second


class Collector(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(inbox):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('content-length') or 0))
            self.send_response(200); self.send_header('content-length', '2'); self.end_headers(); self.wfile.write(b'ok')
            kind = self.path.strip('/')
            if kind in ('alive',): return
            try: inbox.put((kind, json.loads(body), time.time()))
            except ValueError: pass
        def do_GET(self):
            self.send_response(200); self.send_header('content-length', '2'); self.end_headers(); self.wfile.write(b'ok')
        def log_message(self, *a): pass
    return Handler


class Ordered:
    """Snapshots in the order the extension made them: they are posted without waiting for one another, and `seq` says which came first."""
    def __init__(self): self.expected = None; self.held = {}; self.lost = 0

    def add(self, snap, now):
        if self.expected is None: self.expected = snap['seq']
        if snap['seq'] >= self.expected: self.held[snap['seq']] = (snap, now)

    def reset(self): self.expected = None; self.held = {}

    def ready(self, now, final=False):
        out = []
        while self.held:
            if self.expected in self.held: out.append(self.held.pop(self.expected)[0]); self.expected += 1; continue
            first = min(self.held)
            if final or now - self.held[first][1] > REORDER_WAIT: self.lost += first - self.expected; self.expected = first; continue      # the missing one is not coming
            break
        return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--port', type=int, required=True); ap.add_argument('--cdp', type=int, default=0); ap.add_argument('--tree', choices=['extension', 'devtools'], default='extension'); ap.add_argument('--no-sweeps', action='store_true'); ap.add_argument('--report-focus', action='store_true', help='also record what NVDA+Tab says for each focus move (the fleet probe\'s phrase), for the agreement measure')
    args = ap.parse_args()
    protocol = os.fdopen(os.dup(1), 'w', buffering=1); sys.stdout = sys.stderr      # nothing NVDA prints may be taken for a record
    def send(message): protocol.write(json.dumps(message, separators=(',', ':')) + '\n'); protocol.flush()
    inbox = queue.Queue()
    server = Collector(('127.0.0.1', args.port), make_handler(inbox)); threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=lambda: [inbox.put(('cmd', json.loads(line), time.time())) for line in sys.stdin if line.strip()] or inbox.put(('cmd', {'cmd': 'quit'}, time.time())), daemon=True).start()
    t0 = time.time()
    import predict      # NVDA's boot: seconds
    predictor = predict.Predictor(lambda rec: send({'type': 'record', 'rec': rec}), sweeps=not args.no_sweeps, report_focus=args.report_focus)
    cdp = None
    if args.cdp:
        import cdp as cdp_module
        devtools = args.tree == 'devtools'      # the trees come through this port as well (axtree.py), where the extension is given none
        cdp = cdp_module.Cdp(args.cdp, lambda ev: inbox.put(('page', ev, time.time())), lambda target: inbox.put(('attached', {'target': target}, time.time())),
                             on_tree=(lambda snap: inbox.put(('snap', snap, time.time()))) if devtools else None,
                             on_connect=(lambda: inbox.put(('ready', {'t': round(time.time() * 1000), 'source': 'devtools'}, time.time()))) if devtools else lambda: None)
    send({'type': 'ready', 'bootMs': round((time.time() - t0) * 1000)})
    ordered = Ordered()
    dump = open(os.environ['AE_DUMP'], 'a', buffering=1) if os.environ.get('AE_DUMP') else None      # a log of what arrived and when, for finding what a run lost
    record = open(os.environ['AE_RECORD'], 'a', buffering=1) if os.environ.get('AE_RECORD') else None      # everything the runtime was told, whole, for replay.py
    def note(kind, body, arrived):
        if record and kind in ('snap', 'page', 'ready'): record.write(json.dumps({'k': kind, 'arrived': arrived, 'body': body}, separators=(',', ':')) + '\n')
        if not dump: return
        row = {'kind': kind, 'arrived': round(arrived * 1000), **{k: body[k] for k in ('seq', 't', 'page', 'why', 'url', 'ms', 'key', 'cmd') if k in body}}
        if kind == 'snap': f = next((n for n in body['nodes'] if n['ix'] == body['focusIx']), None); row.update(nodes=len(body['nodes']), focus=f and f'{f["role"]} {f.get("name")}')
        dump.write(json.dumps(row) + '\n')

    def handle(kind, body, arrived_at=0):
        try:
            if kind == 'snap': pass
            elif kind == 'page': predictor.on_page_event(body)
            elif kind in ('error', 'verify'): send({'type': 'record', 'rec': {'kind': kind, **body}})
            elif kind == 'ready': send({'type': 'record', 'rec': {'kind': 'start', 'what': 'tree-source' if body.get('source') == 'devtools' else 'extension', 't': body['t'], 'desktopChildren': body.get('desktopChildren'), 'documents': body.get('documents')}})      # when the extension's service worker was up: a test that ran before it was up lost what it did
            elif kind == 'hello': send({'type': 'record', 'rec': {'kind': 'start', 'what': 'worker', 't': body['t'], 'automation': body.get('automation'), 'getDesktop': body.get('getDesktop')}})
            elif kind == 'attached': send({'type': 'record', 'rec': {'kind': 'start', 'what': 'devtools', 't': round(arrived_at * 1000)}})
        except BaseException as e:
            import traceback; traceback.print_exc()
            send({'type': 'record', 'rec': {'kind': 'error', 'where': kind, 'message': f'{type(e).__name__}: {e}'}})

    def snapshots(final=False):
        for snap in ordered.ready(time.time(), final):
            try: predictor.on_snapshot(snap)
            except BaseException as e:
                import traceback; traceback.print_exc()
                send({'type': 'record', 'rec': {'kind': 'error', 'where': 'snapshot', 'message': f'{type(e).__name__}: {e}'}})

    while True:
        try: kind, body, arrived = inbox.get(timeout=0.05)
        except queue.Empty:
            snapshots()
            if not ordered.held: predictor.settle_events(time.time()); predictor.settle_states(time.time()); predictor.run_sweep()      # idle: one sweep, between two events
            continue
        note(kind, body, arrived)
        if kind == 'snap': ordered.add(body, arrived); snapshots()
        elif kind == 'page': handle('page', body)
        elif kind == 'ready':      # the extension started again: what it told before is done with, and its numbers begin again
            snapshots(final=True); ordered.reset(); predictor.restart(); handle(kind, body, arrived)
        elif kind == 'cmd':
            if body['cmd'] == 'quit': break
            if body['cmd'] == 'drain':
                last = time.time()
                while time.time() - last < QUIET:      # whatever the browser is still posting
                    try:
                        k, b, a = inbox.get(timeout=0.05)
                        note(k, b, a)
                        if k == 'snap': ordered.add(b, a)
                        elif k == 'page': handle('page', b)
                        elif k == 'cmd' and b['cmd'] == 'quit': break
                        else: handle(k, b, a)
                        last = time.time()
                    except queue.Empty: pass
                snapshots(final=True)
                stats = predictor.finish(); stats['lostSnapshots'] = ordered.lost
                send({'type': 'drained', 'id': body.get('id'), 'stats': stats})
        else: handle(kind, body, arrived)
    if cdp: cdp.stop()
    server.shutdown()


if __name__ == '__main__': main()
