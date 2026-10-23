"""What the live emulator does that a test asks about, run under the emulator's virtualenv (test_gatefixes.py starts it; `-I`, so every path is set here).

    <emulator python> -I probe_live.py facade
    <emulator python> -I probe_live.py scroll <address of pages/ico-back-to-top.html> <port>
    <emulator python> -I probe_live.py uids <address of any page> <port>

Prints one JSON object."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, 'emu'), os.path.join(ROOT, 'q3')]
os.environ.setdefault('EMU_NVDA_INI', os.path.join(ROOT, 'q3', 'nvda-fleet.ini')); os.environ.setdefault('EMU_FLEET_VOICES', '1')


def facade():
    """IAccessible::accKeyboardShortcut over a platform node with and without an access key."""
    import boot, standin, objlayer
    node = lambda **extra: standin.PN({'depth': 0, 'ix': 1, 'role': 'link', 'state': {}, **extra}, None)
    world = objlayer.World(node())
    return {'with': objlayer.Facade(node(accessKey='m'), world).accKeyboardShortcut(0), 'without': objlayer.Facade(node(), world).accKeyboardShortcut(0)}


def scroll(url, port):
    """Keys scroll nothing and the one pending request does; the request is the node's, so it outlives a read of the tree and is dropped only when the node is gone from it."""
    from livepage import LivePage
    import driver, sweep
    d = LivePage(url=url, port=port)
    try:
        w = sweep.Walker(d, driver); sweep.anchor_to_top(w); sweep.read_through(w)
        y = lambda: d.s.eval('window.scrollY')
        back_to_top = lambda: (d.s.eval('window.scrollTo(0, 0)'), w.perform('control+end'))      # the caret goes to the last line, which asks for a scroll again
        before = {'scrollY': y(), 'pending': d._pending_scroll is not None}
        delivered = d.deliver_pending_scroll(); after = {'scrollY': y(), 'pending': d._pending_scroll is not None}
        again = d.deliver_pending_scroll()
        back_to_top(); asked = d._pending_scroll is not None; d.refresh()
        survived = {'asked': asked, 'pending': d._pending_scroll is not None, 'delivered': d.deliver_pending_scroll(), 'scrollY': y()}
        back_to_top(); d.s.eval("document.querySelector('footer').remove()"); d.refresh()
        gone = {'delivered': d.deliver_pending_scroll(), 'scrollY': y()}
        return {'before': before, 'delivered': delivered, 'after': after, 'again': again, 'survived': survived, 'gone': gone}
    finally: d.close()


def uids(url, port):
    """The extension's dump of an unchanged page twice, then once more after a paragraph is added at the top of the page."""
    import session
    s = session.Session(url=url, port=port)
    try:
        s.navigate(url)
        take = lambda: [(n['ix'], n['uid'], n['role'], n.get('name')) for n in s.dump()[0]]
        first, second = take(), take()
        s.eval("document.body.insertBefore(document.createElement('p'), document.body.firstChild).textContent = 'Added'"); added = take()
        return {'first': first, 'second': second, 'added': added}
    finally: s.close()


if __name__ == '__main__':
    what = sys.argv[1]
    print(json.dumps(facade() if what == 'facade' else scroll(sys.argv[2], int(sys.argv[3])) if what == 'scroll' else uids(sys.argv[2], int(sys.argv[3]))))
