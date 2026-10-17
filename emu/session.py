"""Layer 0: a live Chrome 155 session driven over CDP (keys) and read through chrome.automation (tree + focus)."""
import json, subprocess, pathlib, atexit
R = pathlib.Path.home() / 'spikes/announcement-emulator-5661'
class Session:
    def __init__(self, page_file):
        self.p = subprocess.Popen(['node', str(R / 'emu/session.mjs'), str(page_file), str(R / 'emu/ext2'), str(R / 'chrome155/chrome-linux64/chrome')],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=R / 'emu')
        atexit.register(self.close)
        r = json.loads(self.p.stdout.readline()); assert r.get('ready'), r
    def _cmd(self, **c):
        self.p.stdin.write(json.dumps(c) + '\n'); self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline())
        if not r.get('ok'): raise RuntimeError(r.get('error'))
        return r
    def dump(self, tries=12):
        import time
        for _ in range(tries):
            d = self._cmd(cmd='dump')['dump']
            if 'error' not in d: self.sel = d.get('sel'); return d['nodes'], d['focusIx']
            time.sleep(1)       # the platform tree is built lazily after the first getDesktop() call
        raise RuntimeError(d['error'])
    def key(self, name, mods=0, wait=400): self._cmd(cmd='key', key=name, mods=mods, wait=wait)
    def focus(self, ix, wait=700): self._cmd(cmd='focus', ix=ix, wait=wait)
    def action(self, ix, wait=700): self._cmd(cmd='action', ix=ix, wait=wait)
    def scroll(self, ix, wait=500): self._cmd(cmd='scroll', ix=ix, wait=wait)
    def click(self, x, y, wait=700): self._cmd(cmd='click', x=x, y=y, wait=wait)
    def eval(self, expr): return self._cmd(cmd='eval', expr=expr).get('value')
    def close(self):
        try: self._cmd(cmd='quit')
        except Exception: pass
        self.p.kill()
