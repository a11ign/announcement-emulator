"""winBindings.kernel32 for the emulator: the two locale calls NVDA's languageHandler.getLanguageDescription makes to Windows, answered from the table
`emu/langnames/language-names.json` that `emu/langnames/gen_language_names.py` generates from what Windows itself answered (`windows-locales.raw.json`). NVDA's own lookup order
(display name, then language, then `localesData`, then the code) and the "(not supported)" rule in `speech/languageHandling.py` stay NVDA's: this answers only what Windows would.

A name the table has no entry for is not guessed: it is answered as Windows answers a name it does not know (0), logged, and kept in `report()` for the page's record (q3/emulate.py),
which `emu/langnames/check.py` refuses. Every other `winBindings.kernel32` name is still a stub, as it was.
Set EMU_LANGUAGE_NAMES to read another table (the tests do)."""
import json, os, pathlib, sys
import stubs

TABLE = pathlib.Path(__file__).resolve().parent / 'langnames' / 'language-names.json'
LOCALE_SLANGUAGE = 0x2                  # winnls.h
LOCALE_SLANGDISPLAYNAME = 0x6f
WHICH_STRING = {LOCALE_SLANGDISPLAYNAME: 'displayName', LOCALE_SLANGUAGE: 'language'}


class Kernel32:
    def __init__(self, table_path):
        self._table_path = table_path
        self._loaded = None
        self._asked = {}            # every locale name NVDA asked about, as asked -> whether the table has it
        self._unknown_lcids = set()

    @property
    def _table(self):
        """The table, read on first use: Q2's processes import boot too and never ask about a language."""
        if self._loaded is None:
            table = json.loads(pathlib.Path(self._table_path).read_text(encoding='utf-8'))
            self._loaded = {'synthesizer_languages': {lang.replace('-', '_') for lang in table['synthesizerLanguages']},      # as NVDA's OneCore driver lists them (`en_GB`)
                            'by_name': {name.lower(): entry for name, entry in table['names'].items()},      # Windows locale names are not case-sensitive
                            'by_lcid': {entry['lcid']: entry for entry in table['names'].values() if entry['known']}}
        return self._loaded

    @property
    def synthesizer_languages(self): return self._table['synthesizer_languages']

    def LocaleNameToLCID(self, name, flags):
        entry = self._table['by_name'].get(name.lower())
        if entry is None and name not in self._asked:
            print(f'emu: language code {name!r} is not in the table of Windows language names; answered as Windows answers an unknown name', file=sys.stderr)
        self._asked[name] = entry is not None
        return entry['lcid'] if entry else 0

    def GetLocaleInfo(self, lcid, lctype, buf, size):
        """GetLocaleInfoW: the string's length with its NUL, the string written into `buf` (the caller reads `buf.value`); 0 when Windows had none."""
        entry = self._table['by_lcid'].get(lcid)
        if entry is None:
            self._unknown_lcids.add(lcid)
            return 0
        value = entry.get(WHICH_STRING.get(lctype))
        if value is None or (size and len(value) + 1 > size):
            return 0
        if size:
            buf.value = value
        return len(value) + 1

    def report(self):
        """What a page's record keeps of the language names: every name asked, the ones the table lacked, and the LCIDs it had no strings for."""
        return {'languageCodes': sorted(self._asked), 'unknownLanguageCodes': sorted(c for c, known in self._asked.items() if not known),
                'unknownLanguageLcids': sorted(self._unknown_lcids)}


instance = Kernel32(os.environ.get('EMU_LANGUAGE_NAMES') or TABLE)
m = stubs.StubModule('winBindings.kernel32')
m.LocaleNameToLCID = instance.LocaleNameToLCID
m.GetLocaleInfo = instance.GetLocaleInfo
report = instance.report
