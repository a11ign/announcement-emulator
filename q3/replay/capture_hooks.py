"""What the fleet capture does around each page when the fleet reads a replay (A11-165): load the page's archive into the box's replay server before the capture, and keep what the server answered after it.

`corpus_capture.py --replay-run <run dir> --replay-ports name=port,... --replay-readback <file>` builds one `FleetReplay` and calls `before` and `after` for each page on each box. Each box has its own replay server
on this machine (its own port), because several boxes capture at once, each a different page. A page's log is `<logs dir>/<slug>.<worker>.json`; the record is stamped with a `replay` block (the archive's id,
the box's read-back, what the server answered). Standard library only."""
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from control import control
from archive import summarise
import replay_readback as rrb


class FleetReplay:
    def __init__(self, run_dir, ports, readback, logs_dir=None, control_fn=control):
        self.run_dir, self.ports, self.readback = run_dir, ports, readback
        self.logs_dir = logs_dir or os.path.join(run_dir, 'fleet-logs'); self.control = control_fn
        os.makedirs(self.logs_dir, exist_ok=True)

    def archive_of(self, slug): return f'{slug}.flows'

    def archive_sha256(self, slug):
        with open(os.path.join(self.run_dir, 'archives', self.archive_of(slug)), 'rb') as f: return hashlib.sha256(f.read()).hexdigest()

    def drop_log(self, worker, slug):
        """Remove the log of a capture that failed, so that a page has the log of the capture that was kept and no other."""
        path = os.path.join(self.logs_dir, f'{slug}.{worker}.json')
        if os.path.exists(path): os.remove(path)

    def is_current(self, record, slug):
        """Is a record already on disk this run's: stamped with this run's id and the sha256 of the archive now on disk, by a box that still passes the replay read-back. A record of another run or another archive is captured again."""
        block = record.get('replay') or {}
        return (block.get('runId') == self.readback.get('runId') and block.get('archiveSha256') == self.archive_sha256(slug) and record.get('worker') in rrb.passed_workers(self.readback))

    def before(self, worker, slug):
        """Load the page's archive into the box's server; the answer carries the archive's sha256, which is the archive's id."""
        archive = self.archive_of(slug)
        if not os.path.exists(os.path.join(self.run_dir, 'archives', archive)): raise RuntimeError(f'no archive for {slug}')
        return self.control(self.ports[worker], '/use?archive=' + archive)

    def after(self, worker, slug, used):
        """Write what the box's server answered to the page's log; the `replay` block for the record. `used` is what `before` returned."""
        served = self.control(self.ports[worker], '/log')
        if served['sha256'] != used['sha256']: raise RuntimeError('the server changed archive during the capture')
        path = os.path.join(self.logs_dir, f'{slug}.{worker}.json')
        with open(path + '.part', 'w') as f: json.dump({'worker': worker, **served}, f, indent=1)
        os.replace(path + '.part', path)
        counts = summarise(served['requests']); box = self.readback['workers'][worker]
        return {'runId': self.readback.get('runId'), 'archive': self.archive_of(slug), 'archiveSha256': used['sha256'], 'requests': counts['requests'], 'unmatched': counts['miss'],
                'blocked': counts.get('blocked', 0), 'log': os.path.basename(path),
                'readback': {'proxyReadAt': box['proxy']['readAt'], 'certificateReadAt': box['certificate']['readAt'], 'probeReadAt': box['on']['capturedAt']}}
