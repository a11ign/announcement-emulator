"""When the extension is the tree source and does not come up, the DevTools port is (A11-230). The middleware picks the extension where it can be expected to load, and cannot know that it did: a
team's own channel or executablePath may run a browser that ignores it. So the runtime waits a while after the first page of the browser and, if the extension has said nothing, reads the trees
through the port instead. The two rules are here so that they can be tested without a browser."""


def due(wait, first_page_at, extension_up, switched, now):
    """Whether the runtime should take over the trees now: it was asked to wait (`wait` seconds, 0 for never), a page has been seen, the extension has not spoken, and it has not switched already."""
    return bool(wait) and not switched and not extension_up and first_page_at is not None and now - first_page_at >= wait


def from_extension_after_switch(kind, body):
    """Whether something in the inbox is the extension's, and is to be dropped once the trees come from the port: its trees and its restarts. The port's own carry `devtools` (a tree) or `source` (a start)."""
    if kind == 'snap': return not body.get('devtools')
    if kind == 'ready': return body.get('source') != 'devtools'
    return False


def reason(wait):
    return f'the extension did not come up within {wait:g} s of the first page, so the trees are read through the DevTools port'
