"""Start and steer a replay or recording proxy (A11-165): mitmproxy, from the replay virtualenv `setup.sh` builds under $EMU_DOWNLOADS/replay/venv.

    start_replay(confdir, root, archive=None, port=0, host='127.0.0.1') -> Proxy      answers from archives under `root`
    start_record(confdir, flows, port=0, host='127.0.0.1') -> Proxy                   writes every exchange to `flows`

Both pick a free port when `port` is 0. `Proxy.control(path)` asks a replay proxy (the reserved host `replay.control`); `Proxy.stop()` ends it, which for a recorder is what flushes the file."""
import os, sys, time, socket, signal, subprocess, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from control import control
sys.path.insert(0, str(HERE.parent.parent / 'emu'))
from paths import DOWNLOADS
VENV = DOWNLOADS / 'replay' / 'venv' / 'bin'


def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


class Proxy:
    def __init__(self, process, port, host):
        self.process, self.port, self.host = process, port, host

    def control(self, path, timeout=60): return control(self.port, path, timeout)

    def wait_ready(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.process.poll() is not None: raise RuntimeError(f'the proxy exited with {self.process.returncode} before it was ready')
            try: self.control('/ping', timeout=3); return self
            except Exception: time.sleep(0.25)
        raise RuntimeError('the proxy was not ready in %d s' % timeout)

    def wait_listening(self, timeout=60):
        """For a recorder, which has no control address: ready when its port accepts a connection."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.process.poll() is not None: raise RuntimeError(f'the proxy exited with {self.process.returncode} before it was ready')
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=2): return self
            except OSError: time.sleep(0.25)
        raise RuntimeError('the proxy was not listening in %d s' % timeout)

    def stop(self, wait=20):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try: self.process.wait(wait)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()


def _spawn(args, env, port, host, log):
    port = port or free_port()
    cmd = [str(VENV / 'mitmdump'), '--listen-host', host, '--listen-port', str(port), '--set', 'termlog_verbosity=warn', '--set', 'flow_detail=0', *args]
    return Proxy(subprocess.Popen(cmd, env={**os.environ, **env}, stdout=log or subprocess.DEVNULL, stderr=subprocess.STDOUT), port, host)


def start_replay(confdir, root, archive=None, port=0, host='127.0.0.1', log=None):
    env = {'REPLAY_ROOT': str(root)} | ({'REPLAY_ARCHIVE': archive} if archive else {})
    return _spawn(['-s', str(HERE / 'addon.py'), '--set', f'confdir={confdir}', '--set', 'connection_strategy=lazy'], env, port, host, log)


def start_record(confdir, flows, port=0, host='127.0.0.1', log=None):
    return _spawn(['-w', str(flows), '--set', f'confdir={confdir}'], {}, port, host, log)
