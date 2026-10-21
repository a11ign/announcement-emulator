"""Check the table of Windows language names, and the records of a re-score against it.

    python3 emu/langnames/check.py [<dir of emulate.py outputs>...]

Always: the committed language-names.json is what the committed source generates (gen_language_names.py --check), and it has an entry for every name in codes.txt.
For each directory given: every `*.run*.json` was made by an emulator that reports its language names (a record has `languageCodes`), none names a code the table lacks
(`unknownLanguageCodes`: a name the emulator was asked about and had no answer for, so it spoke the code), and every code it was asked about is in the table. A record of a page the emulator
faulted on says nothing about names and is counted, not checked. Exit 1 on any FAIL: a miss can never be passed off with a name that was guessed."""
import glob, json, os, pathlib, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gen_language_names as gen

OK, FAIL = 'ok', 'FAIL'


def check_table(directory=HERE):
    table_path = os.path.join(directory, gen.TABLE)
    try: generated = gen.generate(pathlib.Path(directory))
    except (ValueError, KeyError, FileNotFoundError) as e: return FAIL, f'the table cannot be generated from its source: {e}'
    if pathlib.Path(table_path).read_text(encoding='utf-8') != generated: return FAIL, f'{gen.TABLE} is not what {gen.RAW} generates'
    table = json.loads(generated)
    lacking = [c for c in gen.read_codes(pathlib.Path(directory) / gen.CODES) if c not in table['names']]
    if lacking: return FAIL, f'{len(lacking)} names of {gen.CODES} have no entry: {lacking}'
    unknown = sorted(c for c, e in table['names'].items() if not e['known'])
    return OK, f'{len(table["names"])} names, every one of {gen.CODES} among them; Windows has no name for {len(unknown)} ({", ".join(unknown)}); generated from {gen.RAW} byte for byte'


def check_records(directory, table):
    paths = sorted(glob.glob(os.path.join(directory, '*.run*.json')))
    if not paths: return FAIL, f'no emulate.py output in {directory}'
    known = {name.lower() for name in table['names']}
    faulted, problems, asked = 0, [], set()
    for path in paths:
        record = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        if record.get('fault'):
            faulted += 1
            if record.get('unknownLanguageCodes'): problems.append(f'{os.path.basename(path)}: unknown language codes {record["unknownLanguageCodes"]} (the page faulted)')
            continue
        if 'languageCodes' not in record: problems.append(f'{os.path.basename(path)}: no languageCodes, so not made by an emulator that answers language names from the table'); continue
        if record.get('unknownLanguageCodes'): problems.append(f'{os.path.basename(path)}: unknown language codes {record["unknownLanguageCodes"]}')
        lacking = [c for c in record['languageCodes'] if c.lower() not in known]
        if lacking and not record.get('unknownLanguageCodes'): problems.append(f'{os.path.basename(path)}: asked about {lacking}, not in the table')
        asked.update(record['languageCodes'])
    if problems: return FAIL, '; '.join(problems[:5]) + (f' (and {len(problems) - 5} more)' if len(problems) > 5 else '')
    return OK, f'{len(paths) - faulted} records name {len(asked)} distinct codes, none unknown ({faulted} of the emulator\'s faults not checked)'


def main(argv):
    results = [('table', *check_table())]
    table = json.loads(pathlib.Path(HERE, gen.TABLE).read_text(encoding='utf-8')) if results[0][1] == OK else {'names': {}}
    results += [(f'records {d}', *check_records(d, table)) for d in argv]
    for name, status, why in results: print(f'{status:>4}  {name}: {why}')
    return 1 if any(status == FAIL for _, status, _ in results) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
