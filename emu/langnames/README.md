# Windows language names for the emulator (A11-164)

NVDA on Windows takes the spoken name of a language from Windows (`languageHandler.getLanguageDescription`: `LocaleNameToLCID`, then `GetLocaleInfoW` for `LOCALE_SLANGDISPLAYNAME`, or `LOCALE_SLANGUAGE` for a language with a region). The emulator runs NVDA's own
Python on Linux, which has no such source, so it spoke `cy (not supported)` where the fleet speaks `Welsh (not supported)`. `emu/kernel32_standin.py` answers those two calls from `language-names.json`, and NVDA's own function and speech filter run unchanged above it.

| file | what it is |
|---|---|
| `query-windows-locales.ps1` | the read-only script that asks Windows exactly what NVDA asks it, for a list of locale names, and lists the box's speech voices |
| `codes.txt` | the list it is given: every locale name NVDA asks Windows about on the corpus (`collect_codes.py`) |
| `windows-locales.raw.json` | what the script printed on `a11y-worker-2`, verbatim |
| `gen_language_names.py` | turns the raw output into the table, deterministically (`--check` fails unless the committed table is what the committed source generates) |
| `language-names.json` | the table: per locale name, either what Windows says (`known: true`, the LCID and the two strings) or that Windows has no name (`known: false`, the LCID it answered); and the languages of the fleet's voices |
| `check.py` | the table's own check, and a re-score's records against it: any record that names an unknown code fails |
| `probe_nvda.py`, `test_langnames.py` | NVDA's own function and speech over the stand-in, and the tests |

A name that is not in the table is **reported, not guessed**: the stand-in answers it as Windows answers a name it does not know (0), prints it, and `q3/emulate.py` puts it in the page's record as `unknownLanguageCodes`.
"No name in Windows" is a different thing and is an entry: the fleet itself speaks `ak (not supported)`, `ceb (not supported)` and `yue (not supported)`.

"(not supported)" is the synthesizer's answer, not Windows' (`speech/languageHandling.py`, `languageIsSupported`). The fleet's NVDA speaks with the OneCore voices of its box, which are all `en-GB`, so only English is supported and the fleet says
`Spanish (not supported)`; the spy synthesizer of Q2's system tests supports `es`, `fr` and `la` too. `emu/driver.py` gives the Q3 emulator (`EMU_FLEET_VOICES`, set by `q3/emulate.py`) the voices' languages from the table.

## Record it again

Every fleet step is Ansible from the control plane (`control/ansible`), on one box, as the worker's own account (no `-b`), and changes nothing on it.

```sh
python3 emu/langnames/collect_codes.py --misses $(ls q3/results/*/misses*.json q3/results/*/*/misses*.json q3/results/misses*.json) --records <the dirs of emulate.py outputs> -o emu/langnames/codes.txt
scp emu/langnames/query-windows-locales.ps1 root@<the control plane>:/tmp/langnames/
ssh root@<the control plane> "cd /root/control/ansible && ansible a11y-worker-2 -m ansible.builtin.script -a '/tmp/langnames/query-windows-locales.ps1 -Worker a11y-worker-2 -Codes $(paste -sd, emu/langnames/codes.txt)'"
# keep the JSON line of the answer's `stdout`, as it is, in emu/langnames/windows-locales.raw.json
python3 emu/langnames/gen_language_names.py
python3 emu/langnames/check.py <the dirs of a re-score's emulate.py outputs>
python3 -m unittest discover -s emu/langnames -t emu/langnames
```

The strings are in the box's UI language (`windows.uiCulture` in the table: `en-GB`, the fleet's), which is what NVDA on that box reads. The source is one box's: the twelve boxes of A11-165's run share a build and an image.
