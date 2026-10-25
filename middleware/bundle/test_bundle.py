"""python3 -m unittest discover -s middleware/bundle -t middleware/bundle   (from the repository root)

The inputs of the runtime bundle: one file holds the pins, and the archive it is made into is the same bytes for the same files."""
import hashlib, json, os, pathlib, re, shutil, subprocess, sys, tarfile, tempfile, time, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import check_no_browser, compare_bundles, compare_live, keep as keep_lists, lean, mktar, sizes
sys.path.insert(0, str(ROOT / 'emu'))
import paths


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

    def test_the_python_is_the_stripped_install_only_build_and_the_pins_are_its_checksums(self):
        """The release's own SHA256SUMS: cpython-3.13.16+20261013-<triple>-install_only_stripped.tar.gz (the install_only ones were e588e50d… and ca0e6a70…)."""
        p = pins()
        self.assertEqual(p['PBS_SHA256_LINUX_X64'], 'd0080766b6b74aeb81e1949ef0d9a20e6c17f7b160fb295a69b936ccb17660be')
        self.assertEqual(p['PBS_SHA256_DARWIN_ARM64'], '16a5332fb0dcb77f163fc8f8cbccd95be1644cc53e68e5d2a79f50afd6680a0e')
        text = (ROOT / 'middleware/bundle/build.sh').read_text()
        self.assertIn('-install_only_stripped.tar.gz"', text)
        self.assertNotRegex(text, r'-install_only\.tar\.gz')

    def test_a_python_whose_checksum_is_not_the_pinned_one_is_refused_before_anything_is_unpacked(self):
        check = next(l for l in (ROOT / 'middleware/bundle/build.sh').read_text().splitlines() if 'is not the pinned build' in l)
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'python.tar.gz').write_bytes(b'not the build')
            script = f'sha256() {{ if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d" " -f1; else shasum -a 256 "$1" | cut -d" " -f1; fi; }}\nW={d}; PBS_SHA={"0" * 64}; PBS_RELEASE=r; TRIPLE=t\n{check}\necho unpacked'
            ran = subprocess.run(['sh', '-c', script], capture_output=True, text=True)
        self.assertEqual(ran.returncode, 1); self.assertIn('is not the pinned build', ran.stderr); self.assertNotIn('unpacked', ran.stdout)

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


class NoBrowser(unittest.TestCase):
    """The runtime holds no browser and no browser library: the middleware runs in the Chromium the team's Playwright installed (A11-230)."""
    LINUX_CHROME = ['chrome/chrome-linux64/chrome', 'chrome/chrome-linux64/chrome_sandbox', 'chrome/chrome-linux64/libEGL.so', 'chrome/chrome-linux64/locales/en-US.pak']
    MAC_CHROME = ['chrome/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing']
    LIBRARIES = ['libs/root/usr/lib/x86_64-linux-gnu/libasound.so.2', 'libs/root/usr/lib/x86_64-linux-gnu/libcups.so.2', 'libs/root/usr/bin/Xvfb']

    def test_a_chrome_for_testing_archive_is_found_for_each_platform(self):
        for names in (self.LINUX_CHROME, self.MAC_CHROME):
            self.assertEqual([n for n, _ in check_no_browser.offending(names)], names)

    def test_the_libraries_a_browser_needs_are_found(self):
        self.assertEqual([n for n, _ in check_no_browser.offending(self.LIBRARIES)], self.LIBRARIES)
        for name in ('python/lib/libnss3.so', 'usr/lib/libgbm.so.1', 'usr/lib/libatk-1.0.so.0', 'usr/lib/libatk-bridge-2.0.so.0'):
            self.assertEqual(len(check_no_browser.offending([name])), 1, name)

    def test_a_headless_shell_or_chromium_is_found_wherever_it_is_put(self):
        for name in ('x/headless_shell', 'x/chrome-headless-shell', 'x/chromium', 'x/Chromium.app/Contents/MacOS/Chromium', 'chrome-linux64/anything'):
            self.assertEqual(len(check_no_browser.offending([name])), 1, name)

    def test_what_the_bundle_does_hold_is_not_taken_for_a_browser(self):
        held = ['bundle.json', 'chromium-src/ax_platform_node_win.cc', 'chromium-src/ax_object.cc', 'python/bin/python3', 'python/lib/python3.13/webbrowser.py',
                'python/share/terminfo/i/iTerm.app', 'python/lib/python3.13/site-packages/nh3/nh3.abi3.so', 'emu/ext2/manifest.json', 'emu/ext2/passive.js', 'middleware/runtime/cdp.py',
                'nvda-src/source/NVDAObjects/IAccessible/chromium.py', 'q1/ext-id.txt']
        self.assertEqual(check_no_browser.offending(held), [])

    def test_an_archive_and_a_directory_are_read_the_same_way(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / 'bundle'
            for name in ('bundle.json', 'chrome/chrome-linux64/chrome', 'python/bin/python3'):
                (root / name).parent.mkdir(parents=True, exist_ok=True); (root / name).write_text('x')
            archive = pathlib.Path(d) / 'b.tar.gz'; mktar.make(str(root), str(archive))
            self.assertEqual(sorted(n for n, _ in check_no_browser.offending(check_no_browser.names_in(str(root)))),
                             sorted(n for n, _ in check_no_browser.offending(check_no_browser.names_in(str(archive)))))
            ran = subprocess.run([sys.executable, str(HERE / 'check_no_browser.py'), str(archive)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 1); self.assertIn('chrome/chrome-linux64/chrome', ran.stderr)
            (root / 'chrome' / 'chrome-linux64' / 'chrome').unlink()
            self.assertEqual(subprocess.run([sys.executable, str(HERE / 'check_no_browser.py'), str(root)], capture_output=True, text=True).returncode, 1)      # its directory is still there
            shutil.rmtree(root / 'chrome')
            self.assertEqual(subprocess.run([sys.executable, str(HERE / 'check_no_browser.py'), str(root)], capture_output=True, text=True).returncode, 0)

    def test_the_build_downloads_no_browser_and_checks_the_archive_it_makes(self):
        text = (ROOT / 'middleware/bundle/build.sh').read_text()
        for gone in ('chrome-for-testing', 'CFT_DIR', 'apt-get download', 'dpkg-deb'): self.assertNotIn(gone, text)
        self.assertLess(text.index('check_no_browser.py'), text.index('mktar.py'))
        self.assertIn('"chromiumTables": "$CHROME"', text)


class WritePins(unittest.TestCase):
    def test_the_pins_of_the_package_are_the_platforms_that_were_built(self):
        with tempfile.TemporaryDirectory() as d:
            files = []
            for platform in ('linux-x64', 'darwin-arm64'):
                f = pathlib.Path(d) / f'pin-{platform}.json'; f.write_text(json.dumps({'platform': platform, 'file': f'b-{platform}.tar.gz', 'sha256': 'ab' * 32, 'bytes': 5})); files.append(str(f))
            out = subprocess.run(['node', str(HERE / 'write-pins.mjs'), '1.2.3', *files], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), {'version': '1.2.3', 'bundles': {p: {'file': f'b-{p}.tar.gz', 'sha256': 'ab' * 32, 'bytes': 5} for p in ('linux-x64', 'darwin-arm64')}})


class WritePinsAgainstTheSums(unittest.TestCase):
    PINS = {'linux-x64': 'ab' * 32, 'darwin-arm64': 'cd' * 32}

    def run_pins(self, sums_lines, pins=None):
        pins = pins or self.PINS
        with tempfile.TemporaryDirectory() as d:
            files = []
            for platform, sha in pins.items():
                f = pathlib.Path(d) / f'pin-{platform}.json'; f.write_text(json.dumps({'platform': platform, 'file': f'b-{platform}.tar.xz', 'sha256': sha, 'bytes': 5})); files.append(str(f))
            sums = pathlib.Path(d) / 'SHA256SUMS'; sums.write_text(''.join(sums_lines))
            return subprocess.run(['node', str(HERE / 'write-pins.mjs'), '1.2.3', '--sums', str(sums), *files], capture_output=True, text=True)

    def lines(self, **replace):
        return [f'{replace.get(p, sha)}  b-{p}.tar.xz\n' for p, sha in self.PINS.items()]

    def test_pins_that_are_in_the_sums_are_written(self):
        done = self.run_pins(self.lines())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual({p: b['sha256'] for p, b in json.loads(done.stdout)['bundles'].items()}, self.PINS)

    def test_a_pin_with_another_sum_than_the_listing_is_refused_and_nothing_is_written(self):
        done = self.run_pins(self.lines(**{'darwin-arm64': 'ee' * 32}))
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(done.stdout, '')
        self.assertIn('darwin-arm64 pins b-darwin-arm64.tar.xz', done.stderr)
        self.assertIn('ee' * 32, done.stderr)

    def test_a_pin_the_listing_has_no_line_for_is_refused(self):
        done = self.run_pins(self.lines()[:1])
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('no line for it', done.stderr)

    def test_a_binary_mode_listing_is_read(self):
        done = self.run_pins([line.replace('  ', ' *') for line in self.lines()])
        self.assertEqual(done.returncode, 0, done.stderr)


def write_tree(root, files, links=()):
    for rel, text in files.items():
        path = pathlib.Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    for rel, target in links: os.symlink(target, pathlib.Path(root) / rel)


LIB = 'python/lib/python3.13'
SITE = f'{LIB}/site-packages'


def module(name, directory=LIB):
    """A standard-library module as build.sh leaves it: its source, and its bytecode beside it."""
    return {f'{directory}/{name}.py': f'# {name}', f'{directory}/{name}.pyc': f'bytecode of {name}'}


def full_layout():
    files = {'bundle.json': '{}', 'LICENSE': 'GPL', f'{LIB}/LICENSE.txt': 'PSF', 'python/bin/python3.13': 'elf', 'python/bin/idle3.13': 'script', 'python/bin/pip3': 'script',
             'python/lib/libpython3.13.so.1.0': 'so', 'python/include/Python.h': 'h', 'python/share/man/python.1': 'man',
             f'{LIB}/__pycache__/os.cpython-313.pyc': 'cache', f'{LIB}/lib-dynload/_tkinter.so': 'so',
             f'{LIB}/test/test_x.py': '# test', f'{LIB}/idlelib/x.py': '# idle', f'{LIB}/tkinter/__init__.py': '# tk', f'{LIB}/ensurepip/__init__.py': '# ensurepip', f'{LIB}/turtledemo/x.py': '# turtle',
             f'{LIB}/pydoc_data/topics.py': '# topics', f'{LIB}/config-3.13-x86_64-linux-gnu/libpython3.13.a': 'a',
             f'{SITE}/requests/api.py': '# api', f'{SITE}/requests/__init__.py': '# init', f'{SITE}/requests/data.pem': 'pem', f'{SITE}/requests-2.32.5.dist-info/licenses/LICENSE': 'Apache',
             f'{SITE}/requests-2.32.5.dist-info/top_level.txt': 'requests\n', f'{SITE}/serial/__init__.py': '# serial', f'{SITE}/pyserial-3.5.dist-info/top_level.txt': 'serial\n',
             f'{SITE}/nh3/__init__.py': '# nh3', f'{SITE}/nh3-0.3.2.dist-info/top_level.txt': 'nh3\n', f'{SITE}/pip/__init__.py': '# pip',
             f'{SITE}/fast_diff_match_patch.cpython-313-x86_64-linux-gnu.so': 'so', f'{SITE}/fast_diff_match_patch-2.1.0.dist-info/top_level.txt': 'fast_diff_match_patch\n',
             'nvda-src/copying.txt': 'GPL', 'nvda-src/source/speech/__init__.py': '# speech', 'nvda-src/source/speech/speech.py': '# speech', 'nvda-src/source/speech/unused.py': '# unused', 'nvda-src/source/unused.py': '# unused',
             'nvda-src/source/oleacc.py': '# read as text', 'nvda-src/source/locale/en/cldr.dic': 'nvda own', 'nvda-src/source/locale/en/symbols.dic': 'symbols', 'nvda-src/source/locale/de/symbols.dic': 'symbole',
             'nvda-src/source/images/icon.png': 'png', 'nvda-src/source/documentation/en/userGuide.md': 'doc', 'nvda-src/source/appModules/chrome.py': '# chrome',
             'nvda-src/tests/system/libraries/SystemTestSpy/speechSpyGlobalPlugin.py': '# spy', 'nvda-src/tests/system/libraries/SystemTestSpy/blocking.py': '# blocking',
             'nvda-src/tests/system/nvdaSettingsFiles/standard-dontShowWelcomeDialog.ini': '[x]', 'nvda-src/tests/unit/test_y.py': '# unit',
             'nvda-appdir/locale/en/cldr.dic': 'the pinned names', 'nvda-appdir/speech/speech.py': '# a second copy', 'cldr-src/locale/en/cldr.dic': 'the pinned names', 'chromium-src/ax_node.cc': '// c',
             'emu/boot.py': '# boot', 'emu/ext2/manifest.json': '{}', 'emu/tables.json': '{}', 'q1/ext-id.txt': 'id', 'q3/shapes.py': '# shapes', 'middleware/runtime/main.py': '# main', 'middleware/runtime/import_trace.py': '# trace'}
    for name in ('os', 'json/__init__', 'json/decoder', 'json/tool', 'encodings/__init__', 'encodings/cp1252', 'encodings/utf_8', 'argparse', 'colorsys', 'tkinter/dialog'): files.update(module(name))
    files[f'{LIB}/notcompiled.py'] = '# a module the compile left alone'
    return files


KEEP = ['python/bin/python3.13', f'{LIB}/os.py', f'{LIB}/json/__init__.py', f'{LIB}/json/decoder.py', f'{LIB}/argparse.py', f'{LIB}/notcompiled.py', f'{SITE}/requests/api.py',
        f'{SITE}/fast_diff_match_patch.cpython-313-x86_64-linux-gnu.so', f'{SITE}/serial/__init__.py', 'nvda-src/source/speech/__init__.py', 'nvda-src/source/speech/speech.py', 'nvda-src/source/oleacc.py',
        'nvda-src/tests/system/libraries/SystemTestSpy/speechSpyGlobalPlugin.py', 'nvda-src/tests/system/nvdaSettingsFiles/standard-dontShowWelcomeDialog.ini']


class Lean(unittest.TestCase):
    """lean.py on a tree that looks like the full layout: what stays, what goes, and in what form (A11-231)."""
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(); cls.root = pathlib.Path(cls.dir.name)
        write_tree(cls.root, full_layout(), links=[('python/bin/python3', 'python3.13'), ('python/bin/idle3', 'idle3.13'), ('python/bin/python', 'python3.13')])
        os.unlink(cls.root / 'python/bin/idle3.13')      # its link is left pointing at nothing
        cls.removed = lean.make_lean(cls.root, set(KEEP))
        cls.left = {p for p in lean.files_of(cls.root)}

    @classmethod
    def tearDownClass(cls): cls.dir.cleanup()

    def test_nothing_is_left_of_the_python_that_the_runtime_never_imports(self):
        for gone in ('test', 'idlelib', 'tkinter', 'ensurepip', 'turtledemo', 'pydoc_data', 'config-3.13-x86_64-linux-gnu'):
            self.assertFalse(any(p.startswith(f'{LIB}/{gone}/') for p in self.left), gone)
        for gone in ('python/include/Python.h', 'python/share/man/python.1', 'python/lib/libpython3.13.so.1.0', f'{LIB}/lib-dynload/_tkinter.so', 'python/bin/idle3.13', 'python/bin/pip3'):
            self.assertNotIn(gone, self.left)
        self.assertFalse(any('__pycache__' in p for p in self.left))

    def test_the_standard_library_is_what_the_list_names_and_all_of_encodings_and_the_licence(self):
        kept = {p for p in self.left if p.startswith(LIB + '/') and 'site-packages' not in p}
        self.assertEqual(kept, {f'{LIB}/{n}' for n in ('LICENSE.txt', 'os.pyc', 'json/__init__.pyc', 'json/decoder.pyc', 'argparse.pyc', 'notcompiled.py',
                                                         'encodings/__init__.pyc', 'encodings/cp1252.pyc', 'encodings/utf_8.pyc')})      # json/tool, colorsys and tkinter/dialog were not read
        self.assertTrue((self.root / LIB / 'lib-dynload').is_dir())      # the interpreter warns at every start without it

    def test_a_standard_library_module_that_is_kept_is_bytecode_alone_and_the_rest_is_source(self):
        self.assertIn(f'{LIB}/json/decoder.pyc', self.left); self.assertNotIn(f'{LIB}/json/decoder.py', self.left)
        self.assertIn(f'{LIB}/notcompiled.py', self.left)      # no bytecode beside it: it stays as it is
        for source in ('nvda-src/source/speech/speech.py', 'nvda-src/source/oleacc.py', f'{SITE}/requests/api.py', f'{SITE}/serial/__init__.py'): self.assertIn(source, self.left)      # read as text, and GPL: source

    def test_site_packages_keeps_each_distribution_that_has_a_file_the_list_names_whole_with_its_licence(self):
        self.assertTrue({f'{SITE}/requests/__init__.py', f'{SITE}/requests/api.py', f'{SITE}/requests/data.pem', f'{SITE}/requests-2.32.5.dist-info/licenses/LICENSE', f'{SITE}/requests-2.32.5.dist-info/top_level.txt',
                         f'{SITE}/fast_diff_match_patch.cpython-313-x86_64-linux-gnu.so', f'{SITE}/fast_diff_match_patch-2.1.0.dist-info/top_level.txt', f'{SITE}/serial/__init__.py'} <= self.left)
        self.assertFalse(any(p.startswith((f'{SITE}/nh3', f'{SITE}/pip')) for p in self.left))

    def test_nvda_is_one_tree_of_the_files_the_list_names_and_english(self):
        nvda = {p for p in self.left if p.startswith('nvda-')}
        self.assertEqual(nvda, {'nvda-src/copying.txt', 'nvda-src/source/speech/__init__.py', 'nvda-src/source/speech/speech.py', 'nvda-src/source/oleacc.py', 'nvda-src/source/locale/en/cldr.dic', 'nvda-src/source/locale/en/symbols.dic',
                                'nvda-src/tests/system/libraries/SystemTestSpy/speechSpyGlobalPlugin.py', 'nvda-src/tests/system/nvdaSettingsFiles/standard-dontShowWelcomeDialog.ini'})
        for gone in ('nvda-appdir', 'cldr-src', 'chromium-src'): self.assertFalse((self.root / gone).exists(), gone)

    def test_the_pinned_names_are_put_over_nvdas_file_in_place(self):
        self.assertEqual((self.root / 'nvda-src/source/locale/en/cldr.dic').read_text(), 'the pinned names')

    def test_this_repositorys_runtime_and_the_interpreter_stay(self):
        for kept in ('bundle.json', 'LICENSE', 'emu/boot.py', 'emu/tables.json', 'q3/shapes.py', 'middleware/runtime/main.py', 'middleware/runtime/import_trace.py', 'python/bin/python3.13', 'python/bin/python3', f'{LIB}/LICENSE.txt'):
            self.assertIn(kept, self.left)
        self.assertTrue((self.root / 'python/bin/python3').is_symlink())
        self.assertNotIn('python/bin/idle3', self.left); self.assertNotIn('python/bin/python', self.left)      # a link to what is gone, and one nothing uses

    def test_a_file_the_list_names_that_the_full_layout_lacks_fails_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            write_tree(d, {'bundle.json': '{}', 'nvda-src/source/a.py': '# a'})
            with self.assertRaises(SystemExit) as raised: lean.prune(pathlib.Path(d), {'nvda-src/source/a.py', 'nvda-src/source/moved.py'})
            self.assertIn('moved.py', str(raised.exception)); self.assertIn('trace.sh', str(raised.exception))

    def test_the_command_line_makes_a_tree_lean_in_place(self):
        with tempfile.TemporaryDirectory() as d:
            write_tree(d, full_layout()); keep = pathlib.Path(d) / 'keep.txt'; keep.write_text('\n'.join(KEEP) + '\n')
            ran = subprocess.run([sys.executable, str(HERE / 'lean.py'), d, str(keep)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertFalse((pathlib.Path(d) / 'nvda-appdir').exists()); self.assertFalse((pathlib.Path(d) / LIB / 'test').exists())


class KeepList(unittest.TestCase):
    def trace(self, d, name, lines):
        path = pathlib.Path(d) / name; path.write_text('\n'.join(lines) + '\n'); return str(path)

    def test_the_list_is_the_files_of_the_two_pruned_parts_that_the_runs_read_and_the_full_layout_has(self):
        with tempfile.TemporaryDirectory() as d:
            write_tree(d, {'python/lib/python3.13/json/__init__.py': '', 'nvda-src/source/speech/speech.py': ''})
            t = self.trace(d, 'a.txt', ['file python/lib/python3.13/json/__init__.py', 'file python/lib/python3.13/__pycache__/json.cpython-313.pyc', 'file python/lib/python3.13/json/__init__.pyc', 'file emu/boot.py',
                                        'file nvda-src/source/speech/speech.py', 'file nvda-src/.git/HEAD', 'missing winreg'])
            self.assertEqual(keep_lists.collect([t], layout=d), (['nvda-src/source/speech/speech.py', 'python/lib/python3.13/json/__init__.py'], []))
            self.assertEqual(keep_lists.collect([t], only='nvda-src/')[0], ['nvda-src/.git/HEAD', 'nvda-src/source/speech/speech.py'])

    def test_a_run_that_read_what_the_lean_bundle_does_not_ship_fails_the_list(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.trace(d, 'a.txt', ['file chromium-src/ax_node.cc', 'file cldr-src/locale/en/cldr.dic', 'file nvda-src/source/a.py'])
            self.assertEqual(keep_lists.collect([t])[1], ['chromium-src/ax_node.cc', 'cldr-src/locale/en/cldr.dic'])
            ran = subprocess.run([sys.executable, str(HERE / 'keep.py'), str(pathlib.Path(d) / 'out.txt'), t], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 1); self.assertIn('chromium-src/ax_node.cc', ran.stderr); self.assertFalse((pathlib.Path(d) / 'out.txt').exists())

    def test_the_list_is_sorted_one_path_to_a_line_and_takes_another_list_in(self):
        with tempfile.TemporaryDirectory() as d:
            write_tree(d, {'layout/nvda-src/source/b.py': '', 'layout/nvda-src/source/a.py': '', 'layout/python/lib/python3.13/os.py': ''})
            t = self.trace(d, 'a.txt', ['file python/lib/python3.13/os.py', 'file nvda-src/source/b.py'])
            also = self.trace(d, 'also.txt', ['nvda-src/source/a.py', 'nvda-src/tests/system/robot/chromeTests.py'])      # the second is the test harness: not in the layout
            out = pathlib.Path(d) / 'out.txt'
            self.assertEqual(subprocess.run([sys.executable, str(HERE / 'keep.py'), str(out), '--layout', str(pathlib.Path(d) / 'layout'), '--also', also, t], capture_output=True, text=True).returncode, 0)
            self.assertEqual(out.read_text(), 'nvda-src/source/a.py\nnvda-src/source/b.py\npython/lib/python3.13/os.py\n')

    def test_the_committed_lists_are_sorted_and_name_only_the_two_pruned_parts(self):
        for path in sorted((HERE / 'keep').glob('*.txt')):
            lines = path.read_text().splitlines()
            self.assertEqual(lines, sorted(set(lines)), path.name)
            self.assertTrue(all(l.startswith(('python/', 'nvda-src/')) and '__pycache__' not in l and not l.endswith('.pyc') for l in lines), path.name)


class FakeLayouts:
    """Two bundles that are only a Python and a replay.py, to test the comparison and not NVDA."""
    def __init__(self, root, variant):
        self.path = pathlib.Path(root) / variant
        (self.path / 'python/bin').mkdir(parents=True); os.symlink(sys.executable, self.path / 'python/bin/python3')
        (self.path / 'middleware/runtime').mkdir(parents=True)
        (self.path / 'middleware/runtime/replay.py').write_text(
            'import json, sys, time\nprint(json.dumps({"records": [{"kind": "speech", "text": "same", "ms": time.time()}, {"kind": "speech", "text": %r, "ms": time.time()}], "stats": {"speechMs": time.time(), "sweepMs": [time.time()], "keys": 0}}))\n' % variant)


class Compare(unittest.TestCase):
    def test_every_recording_under_the_fixtures_is_replayed_with_and_without_sweeps_and_with_focus(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures = pathlib.Path(d) / 'fixtures'
            for name in ('a.jsonl.gz', 'sub/b.jsonl.gz', 'sub/deeper/c.jsonl.gz'): (fixtures / name).parent.mkdir(parents=True, exist_ok=True); (fixtures / name).write_bytes(b'')
            (fixtures / 'devtools').mkdir(); (fixtures / 'devtools/not-a-session.json.gz').write_bytes(b'')
            self.assertEqual([r.relative_to(fixtures).as_posix() for r in compare_bundles.recordings(fixtures)], ['a.jsonl.gz', 'sub/b.jsonl.gz', 'sub/deeper/c.jsonl.gz'])
            same = FakeLayouts(d, 'same').path
            failures, runs = compare_bundles.compare_replays(same, same, fixtures)
            self.assertEqual((failures, runs), ([], 9))      # three recordings, three modes

    def test_two_layouts_that_speak_differently_fail_naming_the_recording_the_flags_and_the_record(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures = pathlib.Path(d) / 'fixtures'; (fixtures / 'sub').mkdir(parents=True); (fixtures / 'sub/b.jsonl.gz').write_bytes(b'')
            failures, runs = compare_bundles.compare_replays(FakeLayouts(d, 'full').path, FakeLayouts(d, 'lean').path, fixtures)
        self.assertEqual(len(failures), 3)
        self.assertTrue(all(f.startswith('sub/b.jsonl.gz') and 'record 1 differs in [\'text\']' in f and '"full"' in f and '"lean"' in f for f in failures), failures)
        self.assertEqual(sorted(f.split(': ')[0].split(' ', 1)[1] for f in failures), ['(with sweeps)', '--no-sweeps', '--report-focus'])

    def test_only_the_clock_is_left_out_of_the_comparison(self):
        a = json.dumps({'records': [{'kind': 'speech', 'text': 'x', 'ms': 1.5, 't': 7}], 'stats': {'speechMs': 70, 'sweepMs': [22], 'keys': 2}})
        b = json.dumps({'records': [{'kind': 'speech', 'text': 'x', 'ms': 9.1, 't': 7}], 'stats': {'speechMs': 71, 'sweepMs': [25], 'keys': 2}})
        c = json.dumps({'records': [{'kind': 'speech', 'text': 'x', 'ms': 1.5, 't': 8}], 'stats': {'speechMs': 70, 'sweepMs': [22], 'keys': 2}})
        self.assertEqual(compare_bundles.transcript(a), compare_bundles.transcript(b))
        self.assertNotEqual(compare_bundles.transcript(a), compare_bundles.transcript(c))      # the page's clock (t) is part of the transcript

    def test_a_replay_that_fails_in_a_layout_is_a_failure_and_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures = pathlib.Path(d) / 'fixtures'; fixtures.mkdir(); (fixtures / 'a.jsonl.gz').write_bytes(b'')
            broken = FakeLayouts(d, 'broken').path; (broken / 'middleware/runtime/replay.py').write_text('raise SystemExit("ModuleNotFoundError: gettext")')
            failures, _ = compare_bundles.compare_replays(FakeLayouts(d, 'full').path, broken, fixtures)
        self.assertEqual(len(failures), 3); self.assertIn('gettext', failures[0])

    def test_a_module_the_trace_missed_fails_the_check_and_one_the_full_layout_lacks_too_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            write_tree(root / 'full', {f'{LIB}/gettext.py': '', f'{LIB}/json/tool.py': '', 'nvda-src/source/speech/speech.py': '', 'nvda-src/source/locale/en/cldr.dic': ''})
            write_tree(root / 'lean', {f'{LIB}/json/tool.pyc': '', 'nvda-src/source/speech/speech.py': '', 'nvda-src/source/locale/en/cldr.dic': ''})
            (root / 'full.txt').write_text('missing winreg\nmissing _winapi\nfile nvda-src/source/speech/speech.py\n')
            (root / 'lean.txt').write_text('missing winreg\nmissing _winapi\nmissing gettext\nfile nvda-src/source/speech/speech.py\nfile python/lib/python3.13/gettext.py\nfile python/lib/python3.13/json/tool.py\n'
                                           'file nvda-src/source/NVDAObjects/UIA/__init__.py\nfile python/lib/python3.13/__pycache__/gettext.cpython-313.pyc\n')
            imports, files = compare_bundles.misses(root / 'full', root / 'lean', root / 'full.txt', root / 'lean.txt')
            self.assertEqual(imports, ['gettext'])      # winreg and _winapi are not on Linux, in either
            self.assertEqual(files, ['python/lib/python3.13/gettext.py'])      # json/tool.py is there as bytecode; NVDAObjects/UIA is in neither
            ran = subprocess.run([sys.executable, str(HERE / 'compare_bundles.py'), 'misses', '--full', str(root / 'full'), '--lean', str(root / 'lean'), '--full-trace', str(root / 'full.txt'), '--lean-trace', str(root / 'lean.txt')], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 1); self.assertIn('import the lean bundle lacks: gettext', ran.stderr); self.assertIn('python/lib/python3.13/gettext.py', ran.stderr)
            (root / 'lean.txt').write_text('missing winreg\nmissing _winapi\nfile nvda-src/source/speech/speech.py\n')
            self.assertEqual(subprocess.run([sys.executable, str(HERE / 'compare_bundles.py'), 'misses', '--full', str(root / 'full'), '--lean', str(root / 'lean'), '--full-trace', str(root / 'full.txt'), '--lean-trace', str(root / 'lean.txt')], capture_output=True, text=True).returncode, 0)

    def test_a_run_that_wrote_no_trace_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / 'full.txt').write_text('')
            with self.assertRaises(SystemExit) as raised: compare_bundles.misses(d, d, pathlib.Path(d) / 'full.txt', pathlib.Path(d) / 'nothing.txt')
            self.assertIn('no trace was written', str(raised.exception))


def report(tests):
    """A Playwright JSON report whose tests carry the middleware's predicted-nvda-speech.json: {title: (speech [(cause, text)], flags [name])}."""
    import base64
    specs = [{'title': title, 'tests': [{'results': [{'attachments': [
        {'name': 'predicted NVDA speech', 'contentType': 'text/plain', 'body': base64.b64encode(b'text').decode()},
        {'name': 'predicted-nvda-speech.json', 'contentType': 'application/json', 'body': base64.b64encode(json.dumps({'predictedSpeech': [{'cause': c, 'text': t, 'atMs': 5, 'runtimeMs': 1.5} for c, t in speech], 'flags': [{'flag': f, 'atMs': 9} for f in flags]}).encode()).decode()}]}]}]}
             for title, (speech, flags) in tests.items()]
    return {'suites': [{'suites': [{'specs': specs}]}]}


class Live(unittest.TestCase):
    """compare_live.py: the live suite's predictions, lean against full, where two runs of the full layout agree."""
    def write(self, d, name, tests):
        path = pathlib.Path(d) / name; path.write_text(json.dumps(report(tests))); return str(path)

    def test_a_test_whose_speech_differs_in_the_lean_run_where_the_full_runs_agree_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            full = {'a': ([('load', 'Page, document')], []), 'b': ([('focus', 'Name, edit')], ['unheard-error'])}
            lean_same = dict(full); lean_other = {**full, 'a': ([('load', 'Page')], [])}
            a, b = self.write(d, 'a.json', full), self.write(d, 'b.json', full)
            self.assertEqual(compare_live.compare(compare_live.predictions(a), compare_live.predictions(b), compare_live.predictions(self.write(d, 'l.json', lean_same))), ([], [], 2))
            self.assertEqual(compare_live.compare(compare_live.predictions(a), compare_live.predictions(b), compare_live.predictions(self.write(d, 'l2.json', lean_other))), (['a'], [], 2))
            different = self.write(d, 'l3.json', {**full, 'b': ([('focus', 'Name, edit')], [])})
            reported = subprocess.run([sys.executable, str(HERE / 'compare_live.py'), a, b, different], capture_output=True, text=True)
            self.assertEqual(reported.returncode, 0); self.assertIn('differs in the lean bundle: b', reported.stdout)      # reported, and not a failure: a live run's timing moves a quick test's last event
            strict = subprocess.run([sys.executable, str(HERE / 'compare_live.py'), '--strict', a, b, different], capture_output=True, text=True)
            self.assertEqual(strict.returncode, 1)

    def test_a_test_the_full_layout_does_not_agree_with_itself_on_is_named_and_not_compared(self):
        with tempfile.TemporaryDirectory() as d:
            a = {'quick': ([('load', 'x')], ['unheard-error'])}; b = {'quick': ([('load', 'x')], [])}
            differ, unstable, compared = compare_live.compare(compare_live.predictions(self.write(d, 'a.json', a)), compare_live.predictions(self.write(d, 'b.json', b)), compare_live.predictions(self.write(d, 'c.json', {'quick': ([], [])})))
            self.assertEqual((differ, unstable, compared), ([], ['quick'], 0))

    def test_the_clock_is_not_part_of_the_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            one = report({'a': ([('load', 'x')], [])}); two = report({'a': ([('load', 'x')], [])})
            import base64
            body = json.loads(base64.b64decode(two['suites'][0]['suites'][0]['specs'][0]['tests'][0]['results'][0]['attachments'][1]['body']))
            body['predictedSpeech'][0].update(atMs=999, runtimeMs=77.7)
            two['suites'][0]['suites'][0]['specs'][0]['tests'][0]['results'][0]['attachments'][1]['body'] = base64.b64encode(json.dumps(body).encode()).decode()
            (pathlib.Path(d) / 'one.json').write_text(json.dumps(one)); (pathlib.Path(d) / 'two.json').write_text(json.dumps(two))
            self.assertEqual(compare_live.predictions(str(pathlib.Path(d) / 'one.json')), compare_live.predictions(str(pathlib.Path(d) / 'two.json')))


class Formats(unittest.TestCase):
    NAMES = ('gz', 'xz', 'zst')

    def available(self, ext): return ext != 'zst' or shutil.which('zstd') is not None

    def test_each_format_is_the_same_bytes_whenever_and_wherever_it_is_made_and_unpacks_with_tar(self):
        for ext in self.NAMES:
            if not self.available(ext): continue
            digests = []
            for pause in (0, 1.1):
                with tempfile.TemporaryDirectory() as d:
                    root = pathlib.Path(d) / 'bundle'; root.mkdir(); write_tree(root, {'a/x.txt': 'x' * 5000, 'a/y.txt': 'y', 'b.sh': '#!/bin/sh\n'}); os.chmod(root / 'b.sh', 0o755)
                    time.sleep(pause); os.utime(root / 'a' / 'x.txt', (time.time() + 500, time.time() + 500))
                    out = pathlib.Path(d) / f'out.tar.{ext}'; mktar.make(str(root), str(out))
                    digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
                    unpacked = pathlib.Path(d) / 'unpacked'; unpacked.mkdir()
                    ran = subprocess.run(['tar', '-xf', str(out), '-C', str(unpacked)], capture_output=True, text=True)
                    if ran.returncode == 0: self.assertEqual((unpacked / 'a' / 'x.txt').read_text(), 'x' * 5000); self.assertTrue(os.access(unpacked / 'b.sh', os.X_OK))
                    else: self.skipTest(f"this host's tar cannot unpack .{ext}: {ran.stderr.strip()}")
            self.assertEqual(digests[0], digests[1], ext)

    def test_the_format_is_the_files_extension_and_nothing_else_is_made(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / 'b').mkdir()
            with self.assertRaises(ValueError): mktar.make(str(pathlib.Path(d) / 'b'), str(pathlib.Path(d) / 'out.zip'))


class Choice(unittest.TestCase):
    """sizes.py's rule: the smaller of xz and zst among those that unpack in 5 s or less on every runner with the host's tar."""
    def m(self, fmt, size, seconds, ok=True): return {'format': fmt, 'bytes': size * 1_000_000, 'unpackSeconds': seconds, 'tarUnpacksIt': ok}

    def platforms(self, xz=(10, 1.0), zst=(9, 0.7), zst_mac=None):
        gz = lambda: self.m('gz', 16, 0.5)
        linux = [gz(), self.m('xz', xz[0], xz[1]), self.m('zst', zst[0], zst[1])]
        mac = [gz(), self.m('xz', xz[0], xz[1]), self.m('zst', *(zst_mac or zst))]
        return {'linux-x64': linux, 'darwin-arm64': mac}

    def test_the_smaller_acceptable_format_ships(self):
        self.assertEqual(sizes.choose(self.platforms())[0], 'zst')
        self.assertEqual(sizes.choose(self.platforms(xz=(8, 1.0)))[0], 'xz')

    def test_a_format_that_is_slow_to_unpack_on_either_runner_does_not(self):
        self.assertEqual(sizes.choose(self.platforms(zst_mac=(9, 5.5)))[0], 'xz')
        self.assertEqual(sizes.choose(self.platforms(xz=(8, 1.0), zst_mac=(6, 4.9)))[0], 'zst')      # 4.9 s is inside the limit

    def test_a_format_the_hosts_tar_cannot_unpack_does_not(self):
        broken = self.platforms(); broken['darwin-arm64'][2]['tarUnpacksIt'] = False
        self.assertEqual(sizes.choose(broken)[0], 'xz')

    def test_what_a_plain_ubuntu_container_does_with_a_format_is_reported_and_does_not_decide(self):
        """That image has no xz and no zstd program, so both fail there (measured in CI): a rule that needed it would ship neither."""
        winner, table = sizes.choose(self.platforms(), {'zst': 'failed', 'xz': 'failed'})
        self.assertEqual(winner, 'zst')
        self.assertIn('| failed |', table); self.assertIn('plain ubuntu:24.04 tar', table)

    def test_nothing_ships_when_neither_is_acceptable_and_the_table_shows_all_three_formats(self):
        none, table = sizes.choose(self.platforms(xz=(10, 6.0), zst_mac=(9, 7.0)))
        self.assertIsNone(none)
        for fmt in ('gz', 'xz', 'zst'): self.assertIn(f'| {fmt} |', table)
        self.assertIn('no: 7.0 s to unpack on darwin-arm64, over 5.0 s', table)

    def test_the_size_by_part_adds_up_to_the_total(self):
        with tempfile.TemporaryDirectory() as d:
            write_tree(d, {'python/bin/python3.13': 'a' * 1000, f'{LIB}/os.pyc': 'b' * 200, f'{SITE}/x/__init__.py': 'c' * 30, 'nvda-src/source/a.py': 'd' * 4, 'emu/boot.py': 'e' * 5, 'emu/ext2/manifest.json': 'f' * 6, 'q1/ext-id.txt': 'g', 'bundle.json': 'h' * 7})
            p = sizes.parts(d)
        self.assertEqual((p['Python: interpreter and its libraries'], p['Python: standard library'], p['Python: packages'], p['NVDA']), (1000, 200, 30, 4))
        self.assertEqual((p['Runtime (this repository)'], p['Companion extension'], p['The rest'], p['Total']), (5, 7, 7, 1000 + 200 + 30 + 4 + 5 + 7 + 7))


class AppDir(unittest.TestCase):
    """boot.py gives NVDA the overlay as its appDir when there is one (setup.sh's layout), and nvda-src/source when there is none (the bundle's)."""
    def test_the_development_layout_keeps_its_overlay_and_the_bundle_uses_nvdas_source_in_place(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            write_tree(root, {'nvda-src/source/locale/en/cldr.dic': 'pinned names'})      # the bundle: the pinned names are in NVDA's file, and there is no overlay
            self.assertEqual(paths.app_dir(root), root / 'nvda-src' / 'source')
            (root / 'nvda-appdir').mkdir()      # setup.sh's layout
            self.assertEqual(paths.app_dir(root), root / 'nvda-appdir')

    def test_a_layout_with_neither_an_overlay_nor_the_pinned_names_is_not_taken_for_the_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d); write_tree(root, {'nvda-src/source/speech/speech.py': ''})      # NVDA's checkout, set up without its overlay
            self.assertEqual(paths.app_dir(root), root / 'nvda-appdir')

    def test_the_pinned_names_must_be_somewhere_for_a_lean_tree_to_be_made(self):
        with tempfile.TemporaryDirectory() as d:
            write_tree(d, {'nvda-src/source/speech/speech.py': ''})
            with self.assertRaises(SystemExit): lean.overlay_in_place(d)

    def test_boot_asks_paths_for_the_app_dir(self):
        self.assertIn('globalVars.appDir = str(app_dir(R))', (ROOT / 'emu' / 'boot.py').read_text())


class Build(unittest.TestCase):
    TEXT = (HERE / 'build.sh').read_text()

    def test_the_lean_bundle_is_made_from_the_full_layout_after_it_is_copied_out_and_before_it_is_archived(self):
        order = [self.TEXT.index(x) for x in ('-I -m compileall', 'cp -R "$B/." "$FULL_DIR"', 'python3 "$HERE/lean.py"', 'python3 "$HERE/check_no_browser.py"', 'python3 "$HERE/mktar.py"')]
        self.assertEqual(order, sorted(order))

    def test_the_cpp_the_live_region_rules_were_ported_from_is_cited_and_not_shipped(self):
        for gone in ('nvdaHelper', 'ia2LiveRegions', 'textFromIAccessible'): self.assertNotIn(gone, self.TEXT)

    def test_the_full_layout_is_what_a11_230_shipped_and_is_made_before_it_is_pruned(self):
        for made in ('mkdir -p "$B/chromium-src"', 'cp -R "$B/nvda-src/source" "$B/nvda-appdir"', 'mkdir -p "$B/cldr-src/locale/en"'): self.assertLess(self.TEXT.index(made), self.TEXT.index('cp -R "$B/." "$FULL_DIR"'), made)

    def test_the_tools_that_built_the_packages_do_not_ship(self):
        self.assertIn('pip uninstall --quiet --yes setuptools wheel', self.TEXT); self.assertIn('rm -rf "${B:?}/$LIB/site-packages/pip"', self.TEXT)

    def test_the_standard_library_is_compiled_with_paths_that_do_not_depend_on_where_it_was_built(self):
        self.assertRegex(self.TEXT, r'compileall -q -b -j 1 -s "\$B" --invalidation-mode unchecked-hash')

    def test_a_build_with_no_trace_to_prune_by_is_refused(self):
        self.assertRegex(self.TEXT, r'\[ -f "\$KEEP" \] \|\| \{[^}]*trace\.sh')

    def test_the_default_format_is_one_of_the_two_compressions_the_ticket_names(self):
        self.assertRegex(self.TEXT, r'(^|\n)FORMAT=(xz|zst);')


if __name__ == '__main__': unittest.main()
