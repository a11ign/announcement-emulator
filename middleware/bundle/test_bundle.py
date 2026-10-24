"""python3 -m unittest discover -s middleware/bundle -t middleware/bundle   (from the repository root)

The inputs of the runtime bundle: one file holds the pins, and the archive it is made into is the same bytes for the same files."""
import hashlib, json, os, pathlib, subprocess, sys, tarfile, tempfile, time, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import mktar


def pins():
    out = subprocess.run(['sh', '-c', f'set -a; . "{ROOT}/pins.env"; set +a; env'], capture_output=True, text=True, check=True).stdout
    return dict(line.split('=', 1) for line in out.splitlines() if '=' in line)


class Pins(unittest.TestCase):
    def test_the_revisions_are_the_ones_the_spike_was_measured_with(self):
        p = pins()
        self.assertEqual(p['NVDA_REV'], '5d92106f17e461dac62aa48257bbbf4183e033d0')
        self.assertEqual(p['CLDR_REV'], '6d3ba86c3963f023550a4b1aa8160945e77ca423')
        self.assertEqual(p['CHROME'], '155.0.8059.84')
        self.assertEqual(p['PYTHON'], '3.13.16')
        write_up = (ROOT / 'docs' / 'announcement-emulator-spike.md').read_text()
        for pin in (p['NVDA_REV'][:8], p['CLDR_REV'][:8], p['CHROME']): self.assertIn(pin, write_up)

    def test_the_two_scripts_read_the_pins_and_hold_none_of_their_own(self):
        names = ('NVDA_REV', 'CLDR_REV', 'ARIA_REV', 'CHROME', 'PYTHON')
        for script in ('setup.sh', 'middleware/bundle/build.sh'):
            text = (ROOT / script).read_text()
            self.assertIn('pins.env', text, script)
            for name in names: self.assertNotRegex(text, rf'^{name}=', script)

    def test_every_python_build_the_bundle_downloads_has_a_checksum_pinned(self):
        p = pins()
        for key in ('PBS_SHA256_LINUX_X64', 'PBS_SHA256_DARWIN_ARM64'): self.assertRegex(p[key], r'^[0-9a-f]{64}$')

    def test_the_chromium_files_are_the_seven_the_tables_are_made_from(self):
        files = subprocess.run(['sh', '-c', f'. "{ROOT}/pins.env"; echo $CHROMIUM_FILES'], capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(len(files), 7)
        self.assertTrue(all(f.startswith(('ui/accessibility/', 'third_party/')) for f in files))


class Archive(unittest.TestCase):
    def tree(self, root):
        (root / 'a').mkdir(); (root / 'a' / 'x.txt').write_text('x'); (root / 'b.sh').write_text('#!/bin/sh\n'); os.chmod(root / 'b.sh', 0o755); (root / 'a' / 'y.txt').write_text('y')
        os.symlink('a/x.txt', root / 'link')

    def test_two_archives_of_the_same_files_are_the_same_bytes_whenever_and_wherever_they_are_made(self):
        digests = []
        for pause in (0, 1.1):
            with tempfile.TemporaryDirectory() as d:
                root = pathlib.Path(d) / 'bundle'; root.mkdir(); self.tree(root)
                time.sleep(pause)
                os.utime(root / 'a' / 'x.txt', (time.time() + 500, time.time() + 500))      # a different mtime
                out = pathlib.Path(d) / 'out.tar.gz'; mktar.make(str(root), str(out))
                digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1])

    def test_the_archive_has_the_files_with_the_executable_bit_and_no_owner(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / 'bundle'; root.mkdir(); self.tree(root)
            out = pathlib.Path(d) / 'out.tar.gz'; mktar.make(str(root), str(out))
            with tarfile.open(out) as t:
                members = {m.name: m for m in t.getmembers()}
        self.assertEqual(sorted(members), ['a', 'a/x.txt', 'a/y.txt', 'b.sh', 'link'])
        self.assertEqual(members['b.sh'].mode, 0o755); self.assertEqual(members['a/x.txt'].mode, 0o644)
        self.assertEqual((members['b.sh'].uid, members['b.sh'].gid, members['b.sh'].uname), (0, 0, ''))
        self.assertTrue(members['link'].issym())


class WritePins(unittest.TestCase):
    def test_the_pins_of_the_package_are_the_platforms_that_were_built(self):
        with tempfile.TemporaryDirectory() as d:
            files = []
            for platform in ('linux-x64', 'darwin-arm64'):
                f = pathlib.Path(d) / f'pin-{platform}.json'; f.write_text(json.dumps({'platform': platform, 'file': f'b-{platform}.tar.gz', 'sha256': 'ab' * 32, 'bytes': 5})); files.append(str(f))
            out = subprocess.run(['node', str(HERE / 'write-pins.mjs'), '1.2.3', *files], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), {'version': '1.2.3', 'bundles': {p: {'file': f'b-{p}.tar.gz', 'sha256': 'ab' * 32, 'bytes': 5} for p in ('linux-x64', 'darwin-arm64')}})


if __name__ == '__main__': unittest.main()
