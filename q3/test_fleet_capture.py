"""python3 -m unittest discover -s q3 -t q3 -p test_fleet_capture.py   (from the repository root; needs node)

fleet_capture.mjs sends the worker's own /capture body. Without --typing-dialog it is the body A11-166's route has always sent; with it, two more opt-in probes are asked for."""
import http.server, json, os, subprocess, tempfile, threading, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
OLD_BODY = {'probeForms': False, 'probeFocus': True, 'probeNavigation': True, 'probeFocusContext': True, 'probeFocusReveal': True, 'steps': 600}


class Worker(http.server.BaseHTTPRequestHandler):
    bodies = []
    def do_POST(self):
        type(self).bodies.append(json.loads(self.rfile.read(int(self.headers['content-length']))))
        out = json.dumps({'transcript': ['a'], 'url': 'http://x/'}).encode()
        self.send_response(200); self.send_header('content-length', str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass


def ask(*extra):
    Worker.bodies = []
    server = http.server.HTTPServer(('127.0.0.1', 0), Worker); threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'out.json')
            subprocess.run(['node', os.path.join(HERE, 'fleet_capture.mjs'), f'a11y-worker-2=http://127.0.0.1:{server.server_port}', 'https://example.com/', out, *extra], check=True, capture_output=True, timeout=60)
            with open(out) as f: record = json.load(f)
    finally: server.shutdown(); server.server_close()
    return Worker.bodies[0], record


class FleetCapture(unittest.TestCase):
    def test_without_the_flag_the_body_is_the_one_a11_166_sent(self):
        body, record = ask()
        self.assertEqual(body, {'url': 'https://example.com/', **OLD_BODY})
        self.assertEqual(record['capture']['transcript'], ['a'])

    def test_the_steps_and_tables_arguments_still_mean_what_they_did(self):
        body, _ = ask('300', '--tables')
        self.assertEqual(body, {'url': 'https://example.com/', **{**OLD_BODY, 'steps': 300}, 'probeTables': True})

    def test_with_the_flag_the_typing_and_escape_probes_are_asked_for(self):
        body, _ = ask('--typing-dialog')
        self.assertEqual(body, {'url': 'https://example.com/', **OLD_BODY, 'probeTyping': True, 'probeDialog': True})

    def test_the_flag_may_follow_the_step_count(self):
        body, _ = ask('450', '--typing-dialog')
        self.assertEqual((body['steps'], body['probeTyping'], body['probeDialog']), (450, True, True))


if __name__ == '__main__': unittest.main()
