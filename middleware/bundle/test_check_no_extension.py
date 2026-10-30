"""python3 -m unittest discover -s middleware/bundle -t middleware/bundle   (from the repository root)

The lean bundle carries no browser extension and no extension-only code (A11-231, the chairman, 2026-10-25): check_no_browser.py, the one command the build and CI run on the bundle, fails on one."""
import pathlib, re, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import check_no_browser, check_no_extension, mktar

MANIFEST = b'{"manifest_version": 3, "name": "companion"}'


def offending(names, manifests=None):
    return check_no_extension.offending(names, (manifests or {}).get)


class Rules(unittest.TestCase):
    def test_the_extensions_files_are_found_wherever_the_bundle_is_rooted(self):
        for name in ('emu/ext2', 'emu/ext2/bg.js', 'emu/ext2/manifest.json', './emu/ext2/page.html', 'bundle/emu/ext2/tree.js', 'q1/ext-id.txt', 'middleware/runtime/fallback.py'):
            self.assertEqual([n for n, _ in offending([name])], [name], name)

    def test_a_packed_extension_is_found(self):
        for name in ('companion.crx', 'x/Companion.CRX'):
            self.assertEqual(len(offending([name])), 1, name)

    def test_a_manifest_that_declares_manifest_version_is_an_extensions(self):
        self.assertEqual(offending(['companion/manifest.json'], {'companion/manifest.json': MANIFEST}), [('companion/manifest.json', 'an extension manifest (declares manifest_version)')])
        self.assertEqual(len(offending(['manifest.json'], {'manifest.json': b'{ "manifest_version" : 2 }'})), 1)

    def test_a_manifest_without_manifest_version_is_not(self):
        held = {'nvda-src/source/manifest.json': b'{"name": "not an extension"}', 'web/manifest.json': b'{"short_name": "app"}'}
        self.assertEqual(offending(list(held), held), [])

    def test_python_is_not_read_for_manifests(self):
        name = 'python/lib/python3.13/site-packages/pkg/manifest.json'
        self.assertEqual(offending([name], {name: MANIFEST}), [])

    def test_site_packages_is_not_read_for_manifests_wherever_the_bundle_is_rooted(self):
        for name in ('bundle/python/lib/python3.13/site-packages/p/manifest.json', './x/site-packages/p/manifest.json'):
            self.assertEqual(offending([name], {name: MANIFEST}), [], name)

    def test_a_manifest_that_cannot_be_read_is_not_taken_for_an_extensions(self):
        self.assertEqual(offending(['x/manifest.json']), [])

    def test_what_the_bundle_does_hold_is_not_taken_for_an_extension(self):
        held = ['bundle.json', 'NOTICES', 'LICENSE', 'emu/live.py', 'emu/session.py', 'emu/capture.py', 'emu/tables.json', 'middleware/runtime/main.py', 'middleware/runtime/cdp.py',
                'middleware/runtime/incremental.py', 'q3/sweep.py', 'python/bin/python3', 'nvda-src/source/NVDAObjects/IAccessible/chromium.py']
        self.assertEqual(offending(held), [])

    def test_the_files_build_sh_copies_from_this_commit_hold_no_extension(self):
        """build.sh step 5 lists what is copied; that list, run over this commit, must offend nothing."""
        text = (HERE / 'build.sh').read_text()
        listed = re.search(r"git ls-files --cached --others --exclude-standard -- (.*?) \\\n\s*\| grep -Ev '([^']*)'", text, re.S)
        self.assertIsNotNone(listed, 'build.sh step 5 no longer reads as a git ls-files over patterns and a grep -Ev')
        patterns = [p.strip("'") for p in listed.group(1).split()]
        files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', *patterns], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        files = [f for f in files if not re.search(listed.group(2), f)]
        self.assertIn('middleware/runtime/main.py', files)
        self.assertEqual(offending(files), [])


class Command(unittest.TestCase):
    """check_no_browser.py is the command the build, the bundle job and release-bundles.yml run (ci-shape.test.ts asserts that)."""
    def run_on(self, path):
        return subprocess.run([sys.executable, str(HERE / 'check_no_browser.py'), str(path)], capture_output=True, text=True)

    def test_an_extension_in_a_directory_or_an_archive_fails_it_and_removing_it_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / 'bundle'
            for name, body in (('bundle.json', b'{}'), ('emu/ext2/manifest.json', MANIFEST), ('python/bin/python3', b'x')):
                (root / name).parent.mkdir(parents=True, exist_ok=True); (root / name).write_bytes(body)
            archive = pathlib.Path(d) / 'b.tar.xz'; mktar.make(str(root), str(archive))
            for target in (root, archive):
                ran = self.run_on(target)
                self.assertEqual(ran.returncode, 1, ran.stderr)
                self.assertIn('emu/ext2/manifest.json: an extension or its switch (emu/ext2)', ran.stderr)
            shutil.rmtree(root / 'emu')
            archive.unlink(); mktar.make(str(root), str(archive))
            for target in (root, archive):
                ran = self.run_on(target)
                self.assertEqual((ran.returncode, ran.stdout.strip()), (0, f'{target}: no browser, no browser library and no extension'))

    def test_an_extension_manifest_is_found_in_an_archive_by_what_it_declares(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / 'bundle'
            for name, body in (('python/lib/site-packages/x/manifest.json', MANIFEST), ('nvda-src/manifest.json', b'{"name": "x"}'), ('companion/manifest.json', MANIFEST)):
                (root / name).parent.mkdir(parents=True, exist_ok=True); (root / name).write_bytes(body)
            for target in (root, self.archive_of(root, pathlib.Path(d) / 'b.tar.gz')):
                ran = self.run_on(target)
                self.assertEqual(ran.returncode, 1)
                self.assertEqual(ran.stderr.strip().splitlines(), ['companion/manifest.json: an extension manifest (declares manifest_version)'])

    def test_a_hard_linked_manifest_is_read_in_an_archive_as_it_is_in_a_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / 'bundle'; (root / 'a').mkdir(parents=True); (root / 'b').mkdir()
            (root / 'a' / 'manifest.json').write_bytes(MANIFEST); (root / 'b' / 'manifest.json').hardlink_to(root / 'a' / 'manifest.json')
            archive = self.archive_of(root, pathlib.Path(d) / 'b.tar.gz')
            self.assertEqual(sorted(check_no_extension.manifests_in(str(archive))), sorted(check_no_extension.manifests_in(str(root))))
            self.assertEqual(sorted(check_no_extension.manifests_in(str(archive))), ['a/manifest.json', 'b/manifest.json'])

    def archive_of(self, root, archive):
        mktar.make(str(root), str(archive)); return archive

    def test_a_browser_is_still_found(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / 'bundle'; (root / 'chrome').mkdir(parents=True); (root / 'chrome' / 'chrome').write_text('x')
            ran = self.run_on(root)
            self.assertEqual(ran.returncode, 1); self.assertIn('chrome/chrome: a browser or library directory (chrome/)', ran.stderr)


class Stated(unittest.TestCase):
    def test_the_readme_says_what_the_guard_keeps_out_and_names_it(self):
        text = (ROOT / 'middleware/README.md').read_text()
        self.assertIn('No browser, no browser library and no extension (`bundle/check_no_browser.py`, with `bundle/check_no_extension.py`)', text)

    def test_the_build_and_both_workflows_run_the_command_that_holds_the_rules(self):
        self.assertIn('check_no_extension', (HERE / 'check_no_browser.py').read_text())
        for path in ('middleware/bundle/build.sh', '.github/workflows/middleware-spike.yml', '.github/workflows/release-bundles.yml'):
            self.assertIn('check_no_browser.py', (ROOT / path).read_text(), path)


if __name__ == '__main__': unittest.main()
