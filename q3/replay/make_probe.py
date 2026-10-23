"""The archive-only probe page of a run (A11-165): a page that exists nowhere but in the archive, so that a capture of it proves a box is behind the replay server.

    <replay venv python> make_probe.py marker                        prints a fresh marker: three plain words
    <replay venv python> make_probe.py <archives dir> <marker>      writes <archives dir>/probe.flows and prints the address

The address is on a reserved name (`replay-probe.test`, RFC 6761), which no resolver answers: a box that is not behind the server cannot read the page, and one that is reads `<marker>` as the page's heading. The
marker (words: NVDA says `6613d43c` as `6613d 43c`) is made fresh for each run, so a capture cannot have read it from an earlier one. Needs mitmproxy (the replay virtualenv)."""
import sys, os
from mitmproxy import http, io
from mitmproxy.test import tflow

ADDRESS = 'https://replay-probe.test/'
WORDS = ('plum heron quartz maple otter ember falcon willow copper ridge lantern harbor cedar tundra velvet orchid pebble summit thistle marble juniper meadow saffron beacon cobalt fennel glacier hazel indigo kestrel lagoon mosaic nectar opal prairie quill russet sparrow timber umber violet walnut yarrow zephyr amber birch clover dune elder fern garnet heath iris jasper kelp linden moss nettle olive pine reed sage teal').split()


def new_marker(rng=None):
    """Three plain words, drawn fresh for the run: a screen reader says words as they are written, and a capture cannot have read this run's marker from an earlier run."""
    import secrets
    pick = (rng or secrets).choice
    return 'replay probe ' + ' '.join(pick(WORDS) for _ in range(3))


def page(marker):
    return f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><title>Replay probe</title></head>\n<body><main><h1>{marker}</h1><p>This page is in the replay archive and nowhere else.</p><a href="{ADDRESS}">Replay probe, itself</a> <a href="{ADDRESS}other">Replay probe, other</a></main></body></html>\n'


def write(archives_dir, marker, name='probe.flows', status=200, html=None):
    """The probe archive; `html` (the unit tests of the consent cookies) replaces the page's body, at the same address."""
    os.makedirs(archives_dir, exist_ok=True)
    flow = tflow.tflow(req=http.Request.make('GET', ADDRESS), resp=http.Response.make(status, html or page(marker), {'content-type': 'text/html; charset=utf-8'}))
    with open(os.path.join(archives_dir, name), 'wb') as f: io.FlowWriter(f).add(flow)
    return ADDRESS


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'marker': print(new_marker())
    elif len(sys.argv) == 3: print(write(sys.argv[1], sys.argv[2]))
    else: sys.exit(__doc__)
