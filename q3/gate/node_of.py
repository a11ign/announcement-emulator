"""The emulator's accessibility node for an element of a page (A11-166): what the tree the emulator builds from Chrome says of it, which is what its virtual buffer is made from.

    <emulator python> node_of.py <address> <out.json> --tag a --no-url [--html-id main-content] [--root <export dir>]      run under with_replay.py

Lists each node whose HTML tag, id and (with `--no-url`) lack of a URL match: its role, name, state and place."""
import sys, os, json, argparse
ap = argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('out'); ap.add_argument('--tag'); ap.add_argument('--html-id'); ap.add_argument('--no-url', action='store_true')
ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ap.add_argument('--port', type=int, default=9895); a = ap.parse_args()
Q3 = os.path.join(a.root, 'q3') if os.path.isdir(os.path.join(a.root, 'q3')) else a.root
os.environ.setdefault('EMU_NVDA_INI', Q3 + '/nvda-fleet.ini'); os.environ.setdefault('EMU_FLEET_VOICES', '1')
sys.path.insert(0, Q3)
from livepage import LivePage
d = LivePage(url=a.url, port=a.port)
found = [{'role': n.role, 'name': n.raw.get('name'), 'tag': n.raw.get('htmlTag'), 'htmlId': n.raw.get('htmlId'), 'state': n.raw.get('state'), 'nameFrom': n.raw.get('nameFrom'), 'location': n.raw.get('location')}
         for ix, n in sorted(d.world.by_ix.items())
         if (not a.tag or n.raw.get('htmlTag') == a.tag) and (not a.html_id or n.raw.get('htmlId') == a.html_id) and (not a.no_url or not n.raw.get('url'))]
with open(a.out, 'w') as f: json.dump(found, f, indent=1, default=str)
d.close()
