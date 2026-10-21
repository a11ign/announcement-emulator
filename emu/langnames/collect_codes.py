"""Collect the locale names the emulator needs an answer for: `codes.txt`, the input of `query-windows-locales.ps1`.

    python3 collect_codes.py --misses <misses.json>... --records <dir of emulate.py outputs>... [-o codes.txt]

Four sources, all of what NVDA itself looked up while reading the corpus:
  --records  the `languageCodes` of every emulate.py output (q3/emulate.py): each name `languageHandler.getLanguageDescription` asked Windows about;
  --misses   the committed misses (q3/results/**/misses*.json): the emulator, which had no Windows names, spoke each language as `<code> (not supported)`, so the code is in `predicted`.
  SPY_SYNTH   the languages the emulator's spy synthesizer supported (en, es, fr, la; its `availableLanguages`): the emulator spoke them with no name at all, so no miss has their code. The
              fleet speaks `Spanish (not supported)` for es, fr and la.
  NVDA'S OWN  the keys of `localesData.LANG_NAMES_TO_LOCALIZED_DESCS` (an, ckb, kmr, my, so), the names NVDA falls back on when Windows gives none: the emulator spoke those names, not a code, so no miss
              has the code either, and whether Windows has a name for them decides which of the two the fleet speaks.
Each is written as NVDA passes it to Windows: `normalizeLocaleForWin32`, the first `_` of a locale replaced by `-`."""
import argparse, ast, glob, json, os, pathlib, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from paths import DOWNLOADS
SPY_SYNTH = ('en', 'es', 'fr', 'la')      # speechSpySynthDriver.availableLanguages, bare languages (es_ES is a dialect: NVDA reports the language)
SPOKEN_CODE = re.compile(r'(?:^|, )([A-Za-z]{2,3}(?:[_-][A-Za-z0-9]+)?) \(not supported\)')


def win32_name(code): return code.replace('_', '-', 1)


def codes_of_misses(paths):
    found = set()
    for path in paths:
        for row in json.loads(pathlib.Path(path).read_text(encoding='utf-8')):
            if isinstance(row, dict) and row.get('predicted'): found.update(win32_name(c) for c in SPOKEN_CODE.findall(row['predicted']))
    return found


def codes_of_nvda_fallback(source):
    """The keys of `LANG_NAMES_TO_LOCALIZED_DESCS` in NVDA's source/localesData.py."""
    for node in ast.parse(pathlib.Path(source, 'localesData.py').read_text(encoding='utf-8')).body:
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0] if isinstance(node, ast.Assign) else None
        if getattr(target, 'id', None) == 'LANG_NAMES_TO_LOCALIZED_DESCS': return {win32_name(k.value) for k in node.value.keys}
    raise ValueError(f'no LANG_NAMES_TO_LOCALIZED_DESCS in {source}')


def codes_of_records(dirs):
    found = set()
    for d in dirs:
        for path in glob.glob(os.path.join(d, '*.run*.json')):
            found.update(win32_name(c) for c in json.loads(pathlib.Path(path).read_text(encoding='utf-8')).get('languageCodes', []))
    return found


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); ap.add_argument('--misses', nargs='*', default=[]); ap.add_argument('--records', nargs='*', default=[])
    ap.add_argument('--nvda-src', default=str(DOWNLOADS / 'nvda-src' / 'source'), help='NVDA\'s source directory'); ap.add_argument('-o', default=os.path.join(HERE, 'codes.txt'))
    a = ap.parse_args(argv)
    from_misses, from_records = codes_of_misses(a.misses), codes_of_records(a.records)
    from_nvda = codes_of_nvda_fallback(a.nvda_src)
    codes = sorted(from_misses | from_records | set(SPY_SYNTH) | from_nvda)
    pathlib.Path(a.o).write_text(''.join(c + '\n' for c in codes), encoding='utf-8')
    print(f'{len(codes)} names: {len(from_misses)} from {len(a.misses)} misses files, {len(from_records)} from the records of {len(a.records)} directories ({len(from_records - from_misses)} only there), the spy synthesizer\'s {len(SPY_SYNTH)}, NVDA\'s own fallback {len(from_nvda)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
