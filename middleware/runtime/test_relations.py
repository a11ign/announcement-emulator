"""The reverse relations of the emulator's tree (emu/standin.py `Builder._relation_ids`, emu/objlayer.py `World.relations`, A11-229).

A node that names no `details` or `errormessage` of its own is looked for in the lists of the nodes that do (`detailsForIx`, `errorMessageForIx`). Looking in every node for every node was quadratic in the tree: 95% of the
650 s a recorded walk of a page of 3,700 nodes took to be predicted. It is made once for a tree now; the answers are the ones the search gave, in the same order.
"""
import json, os, pathlib, subprocess, sys, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'emu'))
import standin
from paths import DOWNLOADS

PYTHON = next((p for p in (DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python', DOWNLOADS / 'python' / 'bin' / 'python3') if p.exists()), None)
HAVE = PYTHON is not None and (DOWNLOADS / 'nvda-src' / 'source').is_dir()


def tree(size=60):
    """A flat depth-first list of nodes as the extractor makes it: a root and `size` children, some naming others in `detailsIx` / `errorMessageIx` and some named in `detailsForIx` / `errorMessageForIx`, and one with a list
    that names the same node twice."""
    nodes = [{'ix': 0, 'depth': 0, 'role': 'rootWebArea'}]
    for i in range(1, size + 1):
        n = {'ix': i, 'depth': 1, 'role': 'genericContainer'}
        if i % 7 == 0: n['detailsIx'] = [i - 3, -1]
        if i % 11 == 0: n['errorMessageIx'] = [i - 5]
        if i % 5 == 0: n['detailsForIx'] = [i + 1, i + 2]
        if i % 9 == 0: n['errorMessageForIx'] = [i - 1, i - 1, i + 3]
        if i == 13: n['detailsForIx'] = [4, 4]
        nodes.append(n)
    return nodes


def scanned(by_ix, pn, key):
    """What the search over every node answered."""
    return [n.ix for n in by_ix.values() if pn.ix in (n.raw.get(key) or [])]


class Builder(unittest.TestCase):
    def setUp(self):
        self.root = standin.build_platform_tree(tree()); self.builder = standin.Builder(self.root)

    def test_a_node_that_names_nothing_is_found_in_the_lists_of_the_nodes_that_name_it_as_the_search_found_it(self):
        for pn in self.builder.by_ix.values():
            for rtype, key in (('details', 'detailsForIx'), ('error', 'errorMessageForIx')):
                if pn.raw.get(self.builder.FORWARD[rtype]): continue
                self.assertEqual(self.builder._relation_ids(pn, rtype), scanned(self.builder.by_ix, pn, key), (pn.ix, rtype))
            for rtype, key in (('detailsFor', 'detailsIx'), ('errorFor', 'errorMessageIx')):
                self.assertEqual(self.builder._relation_ids(pn, rtype), scanned(self.builder.by_ix, pn, key), (pn.ix, rtype))

    def test_a_node_that_names_others_gives_them_without_the_ones_that_are_none(self):
        pn = self.builder.by_ix[7]
        self.assertEqual(self.builder._relation_ids(pn, 'details'), [4])

    def test_a_node_listed_twice_by_another_is_found_once(self):
        self.assertEqual(self.builder._relation_ids(self.builder.by_ix[4], 'detailsFor'), scanned(self.builder.by_ix, self.builder.by_ix[4], 'detailsIx'))
        self.assertEqual(self.builder._relation_ids(self.builder.by_ix[8], 'error'), [9])
        self.assertEqual(self.builder._relation_ids(self.builder.by_ix[4], 'details'), [13] + scanned(self.builder.by_ix, self.builder.by_ix[4], 'detailsForIx')[1:])

    def test_the_nodes_are_looked_through_once_for_each_list_and_not_once_for_each_node(self):
        looked = []
        class Counting(dict):
            def values(self): looked.append(1); return super().values()
        builder = standin.Builder(standin.build_platform_tree(tree(300))); nodes = list(dict.values(builder.by_ix)); builder.by_ix = Counting(builder.by_ix)
        for pn in nodes:
            for rtype in ('details', 'error', 'detailsFor', 'errorFor'): builder._relation_ids(pn, rtype)
        self.assertLessEqual(len(looked), 4)      # the four lists the relations are in: `detailsForIx`, `errorMessageForIx`, `detailsIx`, `errorMessageIx`


@unittest.skipUnless(HAVE, "needs the emulator's virtualenv and NVDA's source (setup.sh)")
class World(unittest.TestCase):
    def test_the_worlds_relations_are_the_ones_the_search_found(self):
        script = """
import sys, json
sys.path.insert(0, %r)
import standin, objlayer
flat = json.loads(sys.stdin.read())
world = objlayer.World(standin.build_platform_tree(flat))
bad = []
for pn in world.by_ix.values():
    for rtype, key in (('details', 'detailsForIx'), ('error', 'errorMessageForIx'), ('labelledBy', 'labelForIx'), ('describedBy', 'descriptionForIx')):
        if pn.raw.get(world.FORWARD[rtype]): continue
        want = [n.ix for n in world.by_ix.values() if pn.ix in (n.raw.get(key) or [])]
        if world.relations(pn, rtype) != want: bad.append((pn.ix, rtype))
print(json.dumps(bad))
""" % str(ROOT / 'emu')
        out = subprocess.run([str(PYTHON), '-I', '-c', script], input=json.dumps(tree()), capture_output=True, text=True, env={**os.environ, 'EMU_DOWNLOADS': str(DOWNLOADS), 'EMU_NVDA_INI': str(ROOT / 'q3' / 'nvda-fleet.ini')}, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1]), [])


if __name__ == '__main__': unittest.main()
