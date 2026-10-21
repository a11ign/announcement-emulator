"""Generate language-names.json, the table `emu/kernel32_standin.py` answers NVDA's Windows locale calls from, out of what Windows itself answered.

    python3 gen_language_names.py            # write language-names.json next to this file
    python3 gen_language_names.py --check    # exit 1 unless the committed language-names.json is what the committed source generates, byte for byte

The source is `windows-locales.raw.json`, the output of `query-windows-locales.ps1` run over `codes.txt` on one fleet box (see README.md here). Nothing is added to it: an entry is either
a name Windows knows (its LCID and the two strings NVDA's getLanguageDescription reads) or a name Windows does not know (`known: false`, the LCID it answered). A name
that is in neither is not in the table at all, and the emulator reports it instead of guessing (emu/kernel32_standin.py)."""
import argparse, hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
LOCALE_CUSTOM_UNSPECIFIED = 0x1000      # LocaleNameToLCID's answer for a name Windows does not know (0 is the other)
RAW, SCRIPT, CODES, TABLE = 'windows-locales.raw.json', 'query-windows-locales.ps1', 'codes.txt', 'language-names.json'


def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def read_codes(path):
    return sorted({line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()})


def entry_of(answer):
    """One name's table entry from the script's answer for it."""
    lcid = answer['lcid']
    if lcid in (0, LOCALE_CUSTOM_UNSPECIFIED):
        return {'known': False, 'lcid': lcid}
    entry = {'known': True, 'lcid': lcid}
    for key in ('displayName', 'language'):
        reading = answer[key]
        if reading['result'] > 0 and reading['value']:      # a call that returned 0 gave NVDA no string
            entry[key] = reading['value']
    return entry


def generate(directory=HERE):
    """The table, as text, for the source files in `directory`."""
    raw = json.loads((directory / RAW).read_text(encoding='utf-8'))
    codes = read_codes(directory / CODES)
    if sorted(raw['names']) != codes:
        missing, extra = sorted(set(codes) - set(raw['names'])), sorted(set(raw['names']) - set(codes))
        raise ValueError(f'{RAW} answers another list than {CODES}: not asked {missing}, not in the list {extra}')
    voices = raw['voices']
    if voices['winrtError'] or not voices['winrt']:
        raise ValueError(f'{RAW} has no voices to take the synthesizer\'s languages from: {voices["winrtError"]!r}')
    names = {code: entry_of(raw['names'][code]) for code in codes}
    strings = {}
    for code, e in names.items():      # GetLocaleInfo is asked by LCID, so one LCID must have one answer
        if e['known'] and strings.setdefault(e['lcid'], {k: e.get(k) for k in ('displayName', 'language')}) != {k: e.get(k) for k in ('displayName', 'language')}:
            raise ValueError(f'{code!r} shares its LCID {e["lcid"]} with another name but Windows gave it other strings')
    table = {
        'generatedBy': 'emu/langnames/gen_language_names.py',
        'source': {'raw': RAW, 'rawSha256': sha256(directory / RAW), 'script': SCRIPT, 'scriptSha256': sha256(directory / SCRIPT), 'codes': CODES, 'codesSha256': sha256(directory / CODES)},
        'windows': raw['windows'] | {'worker': raw['worker']},
        'synthesizerLanguages': sorted({v['language'] for v in voices['winrt']}),
        'names': names,
    }
    return json.dumps(table, indent=1, ensure_ascii=False) + '\n'


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    text = generate()
    if a.check:
        if (HERE / TABLE).read_text(encoding='utf-8') != text:
            print(f'{TABLE} is not what {RAW} generates: run gen_language_names.py', file=sys.stderr); return 1
        print(f'{TABLE} is what {RAW} generates'); return 0
    (HERE / TABLE).write_text(text, encoding='utf-8'); print(f'wrote {TABLE}: {len(json.loads(text)["names"])} names'); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
