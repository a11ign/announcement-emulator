"""When the extension is the tree source and does not give a tree, the DevTools port is (A11-230, A11-229). The middleware picks the extension where it can be expected to load, and cannot know that it did, or that
it can see the test's pages: a team's own channel or executablePath may run a browser that ignores it, and a browser may load it and give it no desktop tree. So the runtime waits a while after the first page of the
browser and, if the extension has not posted a tree (a `ready` alone is not one: it comes up before it has read anything), reads the trees through the port instead. The two rules are here so that they can be
tested without a browser."""


def due(wait, first_page_at, tree_seen, switched, now):
    """Whether the runtime should take over the trees now: it was asked to wait (`wait` seconds, 0 for never), a page has been seen, the extension has posted no tree since, and it has not switched already."""
    return bool(wait) and not switched and not tree_seen and first_page_at is not None and now - first_page_at >= wait


def tree_seen(seen, kind, body):
    """Whether the extension has posted a tree, once `kind`/`body` has arrived: its `snap`, and not the port's own (`devtools`). Its `ready` says it started and nothing more, and a browser that gives it no desktop tree posts that and no tree."""
    return seen or (kind == 'snap' and not body.get('devtools'))


def from_extension_after_switch(kind, body):
    """Whether something in the inbox is the extension's, and is to be dropped once the trees come from the port: its trees and its restarts. The port's own carry `devtools` (a tree) or `source` (a start)."""
    if kind == 'snap': return not body.get('devtools')
    if kind == 'ready': return body.get('source') != 'devtools'
    return False


def reason(wait):
    return f'the extension posted no tree within {wait:g} s of the first page, so the trees are read through the DevTools port'
