"""python3 -m unittest discover -s q3/gate -t q3/gate   (from the repository root)

The batch-2 snapshot and the run list need nothing but the committed files."""
import sys, os, json, hashlib, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); Q3 = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, Q3)
import snapshot_batch2 as sb
from split import split_of

RESULTS = os.path.join(Q3, 'results'); GATE = os.path.join(RESULTS, 'gate')


def load(path):
    with open(path) as f: return json.load(f)


LAB_TEXT = '''export const REAL_PAGES = [
  { url: "https://a.example/old", batch: 2, publishedClaim: "conformant" },
];
export const BATCH_2_PAGES = /** @type {BatchTwoPage[]} */ ([
  { url: "https://one.example/a", batch: 2, publishedClaim: "conformant", source: "x", claimExcludes: ["1.1.1"], drawnFrom: "https://one.example/sitemap.xml" },
  { url: "https://two.example/b", batch: 2, publishedClaim: "conformant", source: "y", claimExcludes: [], drawnFrom: "https://two.example/sitemap.xml" },
  { url: "https://three.example/c", publishedClaim: "conformant", source: "z" },
]);
export const OTHER = [
  { url: "https://four.example/d", batch: 2 },
];
'''


class Snapshot(unittest.TestCase):
    def test_only_the_entries_of_the_batch_2_array_that_are_marked_batch_2_are_read(self):
        self.assertEqual(sb.batch_two_entries(LAB_TEXT), [('https://one.example/a', 'https://one.example/sitemap.xml'), ('https://two.example/b', 'https://two.example/sitemap.xml')])

    def test_a_lab_file_without_the_array_is_refused(self):
        with self.assertRaises(SystemExit): sb.batch_two_entries('export const REAL_PAGES = [];\n')

    def test_an_address_in_batch_2_twice_is_refused(self):
        with self.assertRaises(SystemExit): sb.snapshot('c' * 40, LAB_TEXT.replace('https://two.example/b', 'https://one.example/a'))

    def test_the_snapshot_names_the_lab_commit_the_files_sha256_and_each_addresss_split(self):
        s = sb.snapshot('c' * 40, LAB_TEXT)
        self.assertEqual((s['source']['commit'], s['source']['sha256']), ('c' * 40, hashlib.sha256(LAB_TEXT.encode()).hexdigest()))
        self.assertEqual([(p['url'], p['split']) for p in s['pages']], [(u, split_of(u)) for u in ('https://one.example/a', 'https://two.example/b')])


class CommittedBatch2(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.batch2 = load(os.path.join(GATE, 'corpus-batch2.json')); cls.corpus = load(os.path.join(RESULTS, 'corpus.json'))

    def test_there_are_at_least_120_addresses_once_each(self):
        urls = [p['url'] for p in self.batch2['pages']]
        self.assertGreaterEqual(len(urls), 120); self.assertEqual(len(urls), len(set(urls)))

    def test_no_batch_2_address_is_in_the_earlier_corpus(self):
        self.assertEqual({p['url'] for p in self.batch2['pages']} & {e['url'] for e in self.corpus}, set())

    def test_each_addresss_split_is_the_one_the_split_rule_gives(self):
        for p in self.batch2['pages']: self.assertEqual(p['split'], split_of(p['url']), p['url'])
        self.assertEqual({p['split'] for p in self.batch2['pages']}, {'dev', 'held'})      # both halves exist: the Gate uses the held one

    def test_the_snapshot_names_the_lab_commit_and_the_files_sha256(self):
        s = self.batch2['source']
        self.assertRegex(s['commit'], r'^[0-9a-f]{40}$'); self.assertRegex(s['sha256'], r'^[0-9a-f]{64}$'); self.assertEqual(s['repo'], 'a11ign/lab')


class RunList(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.batch2 = load(os.path.join(GATE, 'corpus-batch2.json')); cls.corpus = load(os.path.join(RESULTS, 'corpus.json')); cls.listed = load(os.path.join(GATE, 'corpus-run.json'))

    def test_the_committed_list_is_what_the_two_snapshots_make(self): self.assertEqual(self.listed, sb.run_list(self.batch2, self.corpus))

    def test_it_holds_every_batch_2_address_and_the_60_held_addresses_of_the_earlier_corpus_once_each(self):
        self.assertEqual(len([r for r in self.listed if r['set'] == 'batch2']), len(self.batch2['pages']))
        old = [r for r in self.listed if r['set'] == 'old60']
        self.assertEqual(len(old), 60); self.assertEqual({r['url'] for r in old}, {e['url'] for e in self.corpus if e['split'] == 'held'})
        self.assertEqual(len({r['url'] for r in self.listed}), len(self.listed))

    def test_the_earlier_corpus_files_split_is_the_rules(self):
        for e in self.corpus: self.assertEqual(e['split'], split_of(e['url']), e['url'])


if __name__ == '__main__': unittest.main()
