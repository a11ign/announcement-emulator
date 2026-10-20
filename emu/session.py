"""Layer 0: a live Chrome 155 session driven over CDP (keys) and read through chrome.automation (tree + focus)."""
import json, os, subprocess, pathlib, atexit
from paths import CODE, DOWNLOADS as R
class Session:
    def __init__(self, page_file=None, url=None, port=8765):
        """A served file (the system tests' pages), or a live address (`url`). `port` is the session's collector port, `port + 1` its DevTools port: sessions with different ports run side by side."""
        self.p = subprocess.Popen(['node', str(CODE / 'emu/session.mjs'), 'url:' + url if url else str(page_file), str(CODE / 'emu/ext2'), str(R / 'chrome155/chrome-linux64/chrome')],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=CODE / 'emu',
                                  env={**os.environ, 'EMU_DOWNLOADS': str(R), 'EMU_PORT': str(port), 'EMU_CDP': str(port + 1)})
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
    def navigate(self, url, settle=2500, timeout=40000): return self._cmd(cmd='navigate', url=url, settle=settle, timeout=timeout)
    def add_history(self, urls): return self._cmd(cmd='history', urls=list(urls))
    def reload(self, settle=2500): return self._cmd(cmd='reload', settle=settle)
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
