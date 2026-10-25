"""python3 -m unittest discover -s middleware/runtime -t middleware/runtime -p 'test_import_trace.py'   (from the repository root)

The trace that decides what the lean bundle keeps (A11-231). An audit hook cannot be taken off, so each case runs in a Python of its own."""
import os, pathlib, subprocess, sys, tempfile, textwrap, unittest

HERE = pathlib.Path(__file__).resolve().parent


def traced(code, root, out, **env):
    """Run `code` in a fresh interpreter with the trace on, rooted at `root`; returns (the lines of the trace file, the process)."""
    script = f'import sys; sys.path.insert(0, {str(HERE)!r}); import import_trace; import_trace.install()\n' + textwrap.dedent(code)
    ran = subprocess.run([sys.executable, '-I', '-c', script], capture_output=True, text=True, env={**os.environ, 'EMU_DOWNLOADS': str(root), 'ANNOUNCEMENT_EMULATOR_IMPORT_TRACE': str(out), **env}, cwd=str(root))
    lines = pathlib.Path(out).read_text().splitlines() if pathlib.Path(out).exists() else []
    return lines, ran


class ImportTrace(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.dir.name).resolve() / 'bundle'; self.root.mkdir()
        self.out = pathlib.Path(self.dir.name) / 'trace.txt'

    def tearDown(self): self.dir.cleanup()

    def write(self, rel, text='x = 1\n'):
        path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text); return path

    def test_it_does_nothing_unless_the_variable_is_set(self):
        script = f'import sys; sys.path.insert(0, {str(HERE)!r}); import import_trace; print(import_trace.install())'
        ran = subprocess.run([sys.executable, '-I', '-c', script], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != 'ANNOUNCEMENT_EMULATOR_IMPORT_TRACE'})
        self.assertEqual(ran.stdout.strip(), 'None')

    def test_a_module_imported_from_under_the_root_is_in_the_trace_by_its_bundle_relative_path(self):
        self.write('nvda-src/source/mymod.py')
        lines, ran = traced("sys.path.insert(0, 'nvda-src/source'); import mymod", self.root, self.out)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn('file nvda-src/source/mymod.py', lines)

    def test_a_file_opened_under_the_root_is_in_the_trace_even_when_it_is_not_there(self):
        self.write('nvda-src/source/locale/en/symbols.dic', 'a\n')
        lines, ran = traced("open('nvda-src/source/locale/en/symbols.dic').close()\ntry: open('nvda-src/source/locale/en/gone.dic')\nexcept OSError: pass", self.root, self.out)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn('file nvda-src/source/locale/en/symbols.dic', lines); self.assertIn('file nvda-src/source/locale/en/gone.dic', lines)

    def test_a_file_outside_the_root_is_not_in_the_trace(self):
        elsewhere = pathlib.Path(self.dir.name) / 'elsewhere.txt'; elsewhere.write_text('x')
        lines, _ = traced(f'open({str(elsewhere)!r}).close()', self.root, self.out)
        self.assertFalse(any('elsewhere' in l for l in lines))

    def test_the_overlay_is_written_as_the_source_tree_it_copies(self):
        self.write('nvda-appdir/locale/en/cldr.dic', 'names\n')
        lines, _ = traced("open('nvda-appdir/locale/en/cldr.dic').close()", self.root, self.out)
        self.assertIn('file nvda-src/source/locale/en/cldr.dic', lines); self.assertFalse(any(l.startswith('file nvda-appdir') for l in lines))

    def test_an_import_no_finder_could_satisfy_is_in_the_trace_though_the_code_swallowed_it(self):
        lines, ran = traced("try:\n    import a_module_nobody_ships\nexcept ImportError:\n    pass\ntry:\n    import winreg\nexcept ImportError:\n    pass", self.root, self.out)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn('missing a_module_nobody_ships', lines); self.assertIn('missing winreg', lines)

    def test_an_import_that_is_found_is_not_a_missing_one(self):
        lines, _ = traced('import json', self.root, self.out)
        self.assertNotIn('missing json', lines)

    def test_the_trace_is_written_when_the_process_dies_of_a_missing_import(self):
        lines, ran = traced('import a_module_nobody_ships', self.root, self.out)
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn('missing a_module_nobody_ships', lines)

    def test_the_modules_the_interpreter_imported_before_the_hook_are_in_it(self):
        (self.root / 'python').mkdir()
        lines, _ = traced('pass', pathlib.Path(sys.base_prefix).resolve(), self.out)      # the root is the interpreter's own prefix here: its site and os are under it
        self.assertTrue(any(l.endswith('os.py') for l in lines), lines[:5])

    def test_several_processes_append_to_the_same_file(self):
        self.write('a.py'); self.write('b.py')
        traced("sys.path.insert(0, '.'); import a", self.root, self.out)
        traced("sys.path.insert(0, '.'); import b", self.root, self.out)
        lines = self.out.read_text().splitlines()
        self.assertIn('file a.py', lines); self.assertIn('file b.py', lines)

    def test_the_hooks_own_reading_is_not_the_runs_and_a_name_is_not_a_file(self):
        lines, _ = traced("compile('x = 1', '<unknown>', 'exec')", self.root, self.out)
        self.assertFalse(any('<' in l for l in lines))
        self.assertFalse(any(l.startswith('file ') and 'trace.txt' in l for l in lines))

    def test_main_and_replay_start_the_trace_before_they_import_anything_else(self):
        for name in ('main.py', 'replay.py'):
            text = (HERE / name).read_text()
            self.assertLess(text.index('import_trace.install()'), text.index('import argparse, http.server' if name == 'main.py' else 'import gzip'), name)


if __name__ == '__main__': unittest.main()
