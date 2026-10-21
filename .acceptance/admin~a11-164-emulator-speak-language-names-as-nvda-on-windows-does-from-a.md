A11-164. The emulator speaks a language change with the name NVDA on Windows speaks, from a table (`emu/langnames/language-names.json`) generated from what a fleet box's Windows answered (`windows-locales.raw.json`, made by `query-windows-locales.ps1`, all committed). Every locale name NVDA asks about on the corpus has an entry; a name the table lacks is reported (`unknownLanguageCodes`), not guessed. The missing `English` was `reportLanguage` under the wrong section of `q3/nvda-fleet.ini`. On the replay oracle the language misses are **0** (17 before at head), and the 138 of the drift-free reading are explained as fixed. The write-up is the `### Language names from a Windows table (not held out)` subsection of `docs/announcement-emulator-spike.md`; the evidence is in `q3/results/langnames/`.

Acceptance:

```bash
python3 -W error::ResourceWarning -m unittest discover -s emu/langnames -t emu/langnames      # 49 tests; the ones that run NVDA's own Python need `setup.sh`'s virtualenv and are skipped without it
python3 emu/langnames/gen_language_names.py --check                                           # the committed table is what the committed source generates, byte for byte
python3 emu/langnames/check.py                                                                # 135 names, every one of codes.txt among them; Windows has no name for 28
grep -E '^(GATE|pages|      misses over)' q3/results/langnames/measure-held-head.txt         # the held half at head: 4488 of 4491; misses over all channels: 12
cat q3/results/langnames/attribute.txt | head -2                                              # {'unexplained': 3} / {'unexplained': 12}: no `language`
python3 emu/langnames/fixed_misses.py q3/results/replay/misses-held-head.json q3/results/langnames/misses-held-head.json     # 17 language rows: {'fixed': 17}
cat q3/results/langnames/language-names-check.txt q3/results/langnames/archive-check.txt     # 200 records, none with an unknown code; 102 of 102 archives are the recorded bytes
python3 q3/remeasure/check.py                                                                 # the doc check: one subsection added at the end of `## Re-measure`, nothing else touched (the pending `oracle` line is as before)
python3 -W error::ResourceWarning -m unittest discover -s q3/replay -t q3/replay; python3 -m unittest discover -s q3/remeasure -t q3/remeasure      # unchanged
```

With the replay archive and oracle on this host (`$EMU_DOWNLOADS/q3/replay/a11-165-2026-10-21/`, A11-165's `$W/oracle`): re-run the re-score with `q3/replay/run_replayed.py <oracle> <out> --run <run dir> --root $PWD --split all --runs 2`, then `python3 emu/langnames/check.py <out>` (exit 0) and `q3/measure.py <oracle> <out> --split held --final` (no `language` misses).

## What changed

- `emu/langnames/` (new): the PowerShell script that asks Windows what NVDA asks it, the list of names it is given (`codes.txt`, made by `collect_codes.py`), its raw output, `gen_language_names.py` and the generated table, `check.py` (the table, and a re-score's records: any unknown code fails), `check_archives.py` (the replay archives against A11-165's manifest), `fixed_misses.py`, `probe_nvda.py`, the tests and a `README.md`.
- `emu/kernel32_standin.py` (new) and `emu/boot.py`: `winBindings.kernel32`'s `LocaleNameToLCID` and `GetLocaleInfo` answered from the table; everything else on that module is still a stub (and still in the ledger).
- `emu/driver.py`, `q3/emulate.py`, `q3/replay/start_state.py`: with `EMU_FLEET_VOICES` (Q3 only) the synthesizer's languages are the fleet's voices (`en-GB`), not the spy's; `q3/emulate.py` writes `languageCodes`, `unknownLanguageCodes` and `unknownLanguageLcids` into each page's record.
- `q3/nvda-fleet.ini`: `reportLanguage` moved from `[documentFormatting]` (no such key) to `[speech]`.
- `q3/results/langnames/`: the re-score's figures, misses, attribution, the check outputs and the language codes asked.
- `docs/announcement-emulator-spike.md`: one appended subsection; `README.md`: one line.
