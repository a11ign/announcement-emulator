"""python3 -m unittest discover -s emu/langnames -t emu/langnames   (from the repository root)

The table's generation, the kernel32 stand-in and the check need nothing built. What runs NVDA's own Python (getLanguageDescription, the speech filter) runs it in a subprocess under the
emulator's virtualenv (`probe_nvda.py`) and is skipped without it (`setup.sh` builds it into $EMU_DOWNLOADS)."""
import contextlib, copy, ctypes, io, json, os, pathlib, re, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE), str(ROOT / 'emu'), str(ROOT / 'q2')]
import check, collect_codes, gen_language_names as gen, kernel32_standin as k32
from paths import DOWNLOADS

VENV_PYTHON = DOWNLOADS / 'q2' / 'venv' / 'bin' / 'python'
HAVE_NVDA = VENV_PYTHON.exists() and (DOWNLOADS / 'nvda-src' / 'source').is_dir()
TABLE = json.loads((HERE / gen.TABLE).read_text(encoding='utf-8'))
STATIC = ROOT / 'q3' / 'results' / 'remeasure' / 'static'


def answer(lcid, display=None, language=None, **extra):
    """What query-windows-locales.ps1 prints for one name."""
    reading = lambda value: {'result': len(value) + 1 if value else 0, 'value': value or ''}
    if lcid in (0, gen.LOCALE_CUSTOM_UNSPECIFIED): return {'lcid': lcid}
    return {'lcid': lcid, 'displayName': reading(display), 'language': reading(language)} | extra


def raw_of(names, voices=({'language': 'en-GB'},), voice_error=None):
    return {'worker': 'a11y-worker-2', 'windows': {'build': '1.2', 'uiCulture': 'en-GB'}, 'names': names,
            'voices': {'winrt': list(voices), 'winrtDefault': None, 'winrtError': voice_error, 'registryTokens': []}}


def write_source(directory, raw, codes=None):
    directory = pathlib.Path(directory)
    (directory / gen.RAW).write_text(json.dumps(raw), encoding='utf-8')
    (directory / gen.SCRIPT).write_text('script', encoding='utf-8')
    (directory / gen.CODES).write_text(''.join(c + '\n' for c in (sorted(raw['names']) if codes is None else codes)), encoding='utf-8')
    return directory


def probe(request):
    """NVDA's own Python's answers to `request` (probe_nvda.py), from a fresh process."""
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f: json.dump(request, f)
    try:
        done = subprocess.run([str(VENV_PYTHON), '-I', str(HERE / 'probe_nvda.py'), f.name], capture_output=True, text=True, timeout=300)
    finally: os.unlink(f.name)
    if done.returncode: raise RuntimeError(done.stderr[-2000:])
    return json.loads(done.stdout.strip().splitlines()[-1])


def gate_language_rows():
    """The 138 language misses among the ten commonest shapes at the freeze of the drift-free re-score (A11-155), from its committed misses; the 158 of every channel are `all`."""
    misses = json.loads((STATIC / 'misses-held-freeze.json').read_text(encoding='utf-8'))
    top = set(misses['top'])
    return [m for m in misses['misses'] if m['class'] == 'language' and ' + '.join(m['shape']) in top and m['channel'] != 'frames'], [m for m in misses['misses'] if m['class'] == 'language']


class Generation(unittest.TestCase):
    def test_the_committed_table_is_what_the_committed_source_generates_byte_for_byte(self):
        self.assertEqual((HERE / gen.TABLE).read_bytes(), gen.generate().encode('utf-8'))
        self.assertEqual(gen.main(['--check']), 0)

    def test_generation_is_deterministic(self):
        self.assertEqual(gen.generate(), gen.generate())

    def test_the_table_says_where_it_came_from(self):
        source = TABLE['source']
        for key, name in (('rawSha256', gen.RAW), ('scriptSha256', gen.SCRIPT), ('codesSha256', gen.CODES)):
            self.assertEqual(source[key], gen.sha256(HERE / name), name)
        self.assertEqual(TABLE['windows']['worker'], 'a11y-worker-2')

    def test_known_region_and_unknown_names_become_entries(self):
        with tempfile.TemporaryDirectory() as d:
            raw = raw_of({'cy': answer(1106, 'Welsh', 'Welsh (United Kingdom)'), 'en-GB': answer(2057, 'English', 'English (United Kingdom)'), 'ak': answer(4096), 'xx': answer(0),
                          'ts': answer(1073, None, 'Xitsonga (South Africa)')})
            table = json.loads(gen.generate(write_source(d, raw)))
        self.assertEqual(table['names']['cy'], {'known': True, 'lcid': 1106, 'displayName': 'Welsh', 'language': 'Welsh (United Kingdom)'})
        self.assertEqual(table['names']['ak'], {'known': False, 'lcid': 4096})      # Windows has no name: an entry, with no strings
        self.assertEqual(table['names']['xx'], {'known': False, 'lcid': 0})
        self.assertNotIn('displayName', table['names']['ts'])      # a call that returned 0 gave NVDA no string
        self.assertEqual(table['synthesizerLanguages'], ['en-GB'])

    def test_a_source_that_answers_another_list_than_the_codes_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            write_source(d, raw_of({'cy': answer(1106, 'Welsh', 'Welsh')}), codes=['cy', 'az'])
            with self.assertRaisesRegex(ValueError, "not asked \\['az'\\]"): gen.generate(pathlib.Path(d))

    def test_two_names_with_one_lcid_must_have_one_answer(self):
        with tempfile.TemporaryDirectory() as d:
            write_source(d, raw_of({'a': answer(1, 'A', 'A'), 'b': answer(1, 'B', 'B')}))
            with self.assertRaisesRegex(ValueError, 'shares its LCID'): gen.generate(pathlib.Path(d))

    def test_a_source_without_voices_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            write_source(d, raw_of({'cy': answer(1106, 'Welsh', 'Welsh')}, voices=(), voice_error='no WinRT'))
            with self.assertRaisesRegex(ValueError, 'no voices'): gen.generate(pathlib.Path(d))

    def test_windows_has_no_name_for_codes_the_fleet_itself_speaks_as_codes(self):
        for code in ('ak', 'ceb', 'yue'):      # the fleet says `ak (not supported)`, `ceb (not supported)`, `yue (not supported)` (q3/results/remeasure/static)
            self.assertFalse(TABLE['names'][code]['known'], code)

    def test_every_code_of_the_list_has_an_entry(self):
        self.assertEqual(check.check_table()[0], check.OK)
        self.assertEqual([c for c in gen.read_codes(HERE / gen.CODES) if c not in TABLE['names']], [])

    def test_a_table_that_is_not_what_the_source_generates_fails_the_check(self):
        with tempfile.TemporaryDirectory() as d:
            write_source(d, raw_of({'cy': answer(1106, 'Welsh', 'Welsh')}))
            (pathlib.Path(d) / gen.TABLE).write_text(gen.generate(pathlib.Path(d)).replace('Welsh', 'Cymraeg'), encoding='utf-8')
            status, why = check.check_table(d)
        self.assertEqual(status, check.FAIL); self.assertIn('is not what', why)


class StandIn(unittest.TestCase):
    def setUp(self): self.k = k32.Kernel32(k32.TABLE)

    def ask(self, name, lctype, size=1024):
        buf = ctypes.create_unicode_buffer(size); lcid = self.k.LocaleNameToLCID(name, 0)
        return self.k.GetLocaleInfo(lcid, lctype, buf, size), buf.value

    def test_a_known_code_is_answered_with_its_display_name(self):
        self.assertEqual(self.k.LocaleNameToLCID('cy', 0), 1106)
        self.assertEqual(self.ask('cy', k32.LOCALE_SLANGDISPLAYNAME), (len('Welsh') + 1, 'Welsh'))

    def test_the_language_string_is_the_one_for_slanguage(self):
        self.assertEqual(self.ask('cy', k32.LOCALE_SLANGUAGE), (len('Welsh (United Kingdom)') + 1, 'Welsh (United Kingdom)'))

    def test_a_code_windows_has_no_name_for_is_answered_as_windows_answers_it(self):
        self.assertEqual(self.k.LocaleNameToLCID('ak', 0), gen.LOCALE_CUSTOM_UNSPECIFIED)
        self.assertEqual(self.ask('ak', k32.LOCALE_SLANGDISPLAYNAME), (0, ''))
        self.assertEqual(self.k.report()['unknownLanguageCodes'], [])      # the table has it: Windows said it has no name

    def test_a_code_the_table_lacks_is_reported_not_guessed(self):
        self.assertEqual(self.k.LocaleNameToLCID('zz', 0), 0)
        with contextlib.redirect_stderr(io.StringIO()) as err: self.k.LocaleNameToLCID('zz', 0); self.k.LocaleNameToLCID('qq', 0)
        self.assertEqual(self.k.report()['unknownLanguageCodes'], ['qq', 'zz'])
        self.assertIn("'qq'", err.getvalue()); self.assertNotIn("'zz'", err.getvalue())      # logged once, on the first ask

    def test_every_code_asked_is_recorded_known_or_not(self):
        self.k.LocaleNameToLCID('cy', 0); self.k.LocaleNameToLCID('zz', 0)
        self.assertEqual(self.k.report()['languageCodes'], ['cy', 'zz'])

    def test_locale_names_are_not_case_sensitive(self):
        self.assertEqual(self.k.LocaleNameToLCID('CY', 0), self.k.LocaleNameToLCID('cy', 0))

    def test_a_string_the_buffer_cannot_hold_is_a_failure_and_size_zero_asks_for_the_length(self):
        buf = ctypes.create_unicode_buffer(3); lcid = self.k.LocaleNameToLCID('cy', 0)
        self.assertEqual(self.k.GetLocaleInfo(lcid, k32.LOCALE_SLANGDISPLAYNAME, buf, 3), 0)
        self.assertEqual(self.k.GetLocaleInfo(lcid, k32.LOCALE_SLANGDISPLAYNAME, None, 0), len('Welsh') + 1)

    def test_an_lcid_the_table_has_no_strings_for_is_a_failure_and_is_recorded(self):
        self.assertEqual(self.k.GetLocaleInfo(0x7777, k32.LOCALE_SLANGUAGE, ctypes.create_unicode_buffer(8), 8), 0)
        self.assertEqual(self.k.report()['unknownLanguageLcids'], [0x7777])

    def test_the_synthesizer_languages_are_the_fleets_voices(self):
        self.assertEqual(self.k.synthesizer_languages, {'en_GB'})

    def test_the_stand_in_is_the_module_boot_installs(self):
        boot = (ROOT / 'emu' / 'boot.py').read_text(encoding='utf-8')
        self.assertIn("sys.modules['winBindings.kernel32'] = winBindings.kernel32 = kernel32_standin.m", boot)
        self.assertEqual(k32.m.LocaleNameToLCID('cy', 0), 1106)


@unittest.skipUnless(HAVE_NVDA, "needs NVDA's source and the emulator's virtualenv (setup.sh)")
class NvdaThroughTheStandIn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.said = probe({'codes': ['en', 'cy', 'az', 'zu', 'ak', 'ceb', 'yue', 'no-such-locale'], 'supported': ['en', 'en_GB', 'cy', 'fr', 'es', 'la'],
                          'sequences': [[{'lang': 'cy'}, 'a'], [{'lang': 'cy'}, 'a', {'lang': 'en'}, 'b'], [{'lang': 'en'}, 'x'], [{'lang': 'ak'}, 'a'], [{'lang': 'fr'}, 'a'], [{'lang': 'en'}, 'a', {'lang': 'en'}, 'b']]})

    def test_getLanguageDescription_is_windows_display_name_for_a_bare_language(self):
        d = self.said['descriptions']
        self.assertEqual((d['en'], d['cy'], d['az'], d['zu']), ('English', 'Welsh', 'Azerbaijani (Latin)', 'isiZulu'))

    def test_getLanguageDescription_is_windows_language_for_a_language_with_a_region(self):
        with tempfile.TemporaryDirectory() as d:      # no code of the corpus has a region (NVDA reports the language: autoDialectSwitching is off), so a table of its own
            table = pathlib.Path(write_source(d, raw_of({'en-GB': answer(2057, 'English', 'English (United Kingdom)'), 'cy': answer(1106, 'Welsh', 'Welsh (United Kingdom)')}))) / 'table.json'
            table.write_text(gen.generate(pathlib.Path(d)), encoding='utf-8')
            said = probe({'codes': ['en_GB', 'cy'], 'table': str(table)})
        self.assertEqual(said['descriptions'], {'en_GB': 'English (United Kingdom)', 'cy': 'Welsh'})      # a bare language gets SLANGDISPLAYNAME, a language with a region SLANGUAGE

    def test_getLanguageDescription_has_nothing_for_a_code_windows_has_no_name_for(self):
        d = self.said['descriptions']
        self.assertEqual([d['ak'], d['ceb'], d['yue']], [None, None, None])      # NVDA falls back to the code

    def test_a_code_missing_from_the_table_is_reported_by_the_emulator(self):
        self.assertEqual(self.said['descriptions']['no-such-locale'], None)
        self.assertEqual(self.said['report']['unknownLanguageCodes'], ['no-such-locale'])

    def test_only_the_fleets_voice_language_is_supported(self):
        self.assertEqual(self.said['supported'], {'en': True, 'en_GB': True, 'cy': False, 'fr': False, 'es': False, 'la': False})

    def test_nvda_speaks_the_windows_name_with_not_supported_as_the_fleet_does(self):
        self.assertEqual(self.said['speech'][0], 'Welsh (not supported) a')

    def test_a_code_windows_has_no_name_for_is_spoken_as_the_code_as_the_fleet_does(self):
        self.assertEqual(self.said['speech'][3], 'ak (not supported) a')

    def test_a_language_the_spy_synthesizer_supported_is_not_supported_by_the_fleets(self):
        self.assertEqual(self.said['speech'][4], 'French (not supported) a')

    def test_english_is_spoken_when_the_language_changes_to_it(self):      # the fleet: `English, Government Digital Service, link`
        self.assertEqual(self.said['speech'][1], 'Welsh (not supported) a English b')
        self.assertEqual(self.said['speech'][2], 'English x')

    def test_english_is_spoken_once_for_a_run_of_english(self):
        self.assertEqual(self.said['speech'][5], 'English a b')


@unittest.skipUnless(HAVE_NVDA, "needs NVDA's source and the emulator's virtualenv (setup.sh)")
class TheMissesOfTheDriftFreeReScore(unittest.TestCase):
    """The 138 language misses among the ten commonest shapes (158 over every channel) that A11-155 left at the freeze, tied to the table. This reads the committed fleet speech against what NVDA's own
    speech says for each code of the table; it is a cross-check of the source, not an evidence figure: the re-score's runs are (q3/results/langnames)."""
    @classmethod
    def setUpClass(cls):
        cls.gate, cls.every = gate_language_rows()
        codes = sorted(TABLE['names'])
        said = probe({'supported': codes, 'sequences': [[{'lang': c}, 'a'] for c in codes]})
        cls.supported = said['supported']
        cls.spoken_name = {c: re.sub(r' (\(not supported\) )?a$', '', text) for c, text in zip(codes, said['speech'])}      # the name as the synthesizer is given it, NVDA's own speech processing included
        cls.fleet_says = re.compile(r'(?:^|, )([^,]+?) \(not supported\)')

    def test_there_are_138_language_misses_in_the_ten_shapes_and_158_over_all_channels(self):
        self.assertEqual((len(self.gate), len(self.every)), (138, 158))

    def test_every_name_the_fleet_spoke_with_not_supported_is_what_nvda_says_for_a_code_of_the_table(self):
        names = {self.spoken_name[c] for c in self.spoken_name if not self.supported[c]}
        for m in self.every:
            for name in self.fleet_says.findall(m['expected']): self.assertIn(name, names, m['expected'])

    def test_each_code_the_emulator_spoke_is_the_fleets_name_for_it(self):
        paired = 0
        for m in self.every:
            ours = {after: spoken for spoken, after in self.language_tokens(m['predicted'] or '')}
            for name, after in self.language_tokens(m['expected']):
                if after not in ours: continue      # the rows are not always aligned: a language is paired with the fleet's only by the page's own text that follows it, `after`
                code = ours[after]      # what the emulator spoke: a code, or a name NVDA had of its own (localesData)
                self.assertEqual(self.spoken_name.get(code, code), name, (code, m['expected'])); paired += 1
        self.assertGreater(paired, 100)

    @staticmethod
    def language_tokens(text):
        """(what is said before `(not supported)`, the token after it) for each language in a row's speech."""
        tokens = text.split(', ')
        return [(t[:-len(' (not supported)')], tokens[i + 1] if i + 1 < len(tokens) else '') for i, t in enumerate(tokens) if t.endswith(' (not supported)')]

    def test_english_is_what_nvda_says_for_en_and_it_is_supported(self):
        self.assertEqual(self.spoken_name['en'], 'English'); self.assertTrue(self.supported['en'])
        self.assertTrue(any(re.search(r'(^|, )English, ', m['expected']) and 'English' not in (m['predicted'] or '') for m in self.gate))      # the rows the name table and the settings fix


class Check(unittest.TestCase):
    def record(self, directory, name, **fields):
        (pathlib.Path(directory) / name).write_text(json.dumps({'url': 'https://example.test/'} | fields), encoding='utf-8')

    def test_a_record_that_names_an_unknown_code_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.record(d, 'a.run1.json', languageCodes=['cy', 'zz'], unknownLanguageCodes=['zz'])
            status, why = check.check_records(d, TABLE)
        self.assertEqual(status, check.FAIL); self.assertIn("unknown language codes ['zz']", why)

    def test_records_whose_codes_are_all_in_the_table_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self.record(d, 'a.run1.json', languageCodes=['cy', 'en'], unknownLanguageCodes=[]); self.record(d, 'a.run2.json', languageCodes=[], unknownLanguageCodes=[])
            self.assertEqual(check.check_records(d, TABLE)[0], check.OK)

    def test_a_record_made_without_the_stand_in_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.record(d, 'a.run1.json', structure={})
            status, why = check.check_records(d, TABLE)
        self.assertEqual(status, check.FAIL); self.assertIn('no languageCodes', why)

    def test_a_code_asked_about_that_the_table_lacks_fails_even_if_the_record_forgot_to_say_so(self):
        with tempfile.TemporaryDirectory() as d:
            self.record(d, 'a.run1.json', languageCodes=['zz'], unknownLanguageCodes=[])
            self.assertEqual(check.check_records(d, TABLE)[0], check.FAIL)

    def test_a_fault_is_counted_not_checked_and_an_empty_directory_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(check.check_records(d, TABLE)[0], check.FAIL)
            self.record(d, 'a.run1.json', fault='timeout 900s')
            status, why = check.check_records(d, TABLE)
        self.assertEqual(status, check.OK); self.assertIn('1 of the emulator', why)

    def test_main_exits_1_on_a_fail_and_0_on_a_pass(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            self.record(d, 'a.run1.json', languageCodes=['zz'], unknownLanguageCodes=['zz'])
            self.assertEqual(check.main([d]), 1)
            self.assertEqual(check.main([]), 0)


class CollectCodes(unittest.TestCase):
    def test_codes_are_taken_from_what_the_emulator_spoke_as_not_supported(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'misses.json'
            path.write_text(json.dumps([{'predicted': 'list, with 2 items, cy (not supported), Cymraeg, link'}, {'predicted': 'az (not supported), x'}, {'predicted': None}, {'predicted': 'English, x'}]))
            self.assertEqual(collect_codes.codes_of_misses([str(path)]), {'cy', 'az'})

    def test_a_locale_with_a_region_is_written_as_windows_is_asked(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / 'p.run1.json').write_text(json.dumps({'languageCodes': ['en_GB', 'cy']}))
            self.assertEqual(collect_codes.codes_of_records([d]), {'en-GB', 'cy'})


if __name__ == '__main__':
    unittest.main()
