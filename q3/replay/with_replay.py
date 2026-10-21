"""Run one command with a replay proxy in front of the emulator's Chrome (A11-165).

    python with_replay.py --run <run dir> --archive <slug>.flows --log <log.json> [--timeout <seconds>] -- <command ...>

Starts a replay proxy on a free loopback port, loaded with `<run dir>/archives/<archive>` and the run's CA (`<run dir>/ca`), and gives the command the two variables `emu/session.mjs` reads (`EMU_PROXY`, `EMU_PROXY_SPKI`);
when the command ends it writes what the proxy served to `--log` (the archive's sha256 and every request with how it was answered) and stops the proxy. Exits with the command's own status (124 when it ran past `--timeout` and was ended with everything it started); 70 when the proxy could not be started."""
import sys, os, json, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proxy as px
import ca as cert_names
from process import run_in_group, TIMED_OUT


def run_under_replay(run_dir, archive, command, log_path, timeout=None, extra_env=None):
    ca_dir = os.path.join(run_dir, 'ca'); spki = cert_names.identify(os.path.join(ca_dir, 'mitmproxy-ca-cert.pem'))['spki']
    p = px.start_replay(ca_dir, os.path.join(run_dir, 'archives'), archive=archive)
    try:
        p.wait_ready()
        env = {**os.environ, 'EMU_PROXY': f'127.0.0.1:{p.port}', 'EMU_PROXY_SPKI': spki, **(extra_env or {})}
        try: status = run_in_group(command, timeout, env)
        except subprocess.TimeoutExpired: status = TIMED_OUT      # the command and what it started are ended; what the proxy served up to then is still kept
        served = p.control('/log')
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        with open(log_path + '.part', 'w') as f: json.dump({**served, 'status': status}, f, indent=1)
        os.replace(log_path + '.part', log_path)
        return status
    finally: p.stop()


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--' not in argv: sys.exit(__doc__)
    cut = argv.index('--'); ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); ap.add_argument('--archive', required=True); ap.add_argument('--log', required=True); ap.add_argument('--timeout', type=int)
    a = ap.parse_args(argv[:cut])
    try: sys.exit(run_under_replay(a.run, a.archive, argv[cut + 1:], a.log, a.timeout))
    except RuntimeError as e: print(e, file=sys.stderr); sys.exit(70)
