# announcement-emulator

**Status: a spike, finished, and below its Gate.** This predicts what NVDA would say when browsing a page in Chromium, on any OS (Linux CI included). It reads Chrome's own accessibility tree, applies
Chromium's Windows (IA2) mapping, and runs NVDA's own Python, at a pinned release, above a rebuilt buffer.

**Its output is a prediction, never evidence.** Nothing here may fill an evidence field in a11ign (a11ign ADR 0021 and ADR 0047).

## Where it stands

The write-up is `docs/announcement-emulator-spike.md`, with Dates, Q1, Q2, Q3, Gate and Reproduction.

- **Q1, done.** The full tree through `chrome.automation`, in a Chrome 155 launched on Linux with a companion extension (`q1/`, `emu/ext2/`).
- **Q2, done.** NVDA's own Python runs on Linux with stand-ins for its Windows modules (`q2/`, `emu/`). On NVDA's own Chrome system tests: 44 of 47 run, 215 of 227 assertions exact, the other 12 attributed.
- **Q3, measured** (`q3/`): agreement with the fleet's NVDA transcripts on 102 real pages, by element kind and by announcement shape. The tables are in the write-up; the derived data is in `q3/results/`.
- **Gate: not passed.** At least 98% exact agreement on the 10 commonest shapes, every miss explained as an emulator bug or a Windows-only behaviour. See the write-up.

## What is in this repository

- `emu/` the emulator: the tree source, the Windows mapping (`standin.py`), the buffer builder, the harness around NVDA's code, and the system-test runner (`run_cases.py`).
- `emu/langnames/` the Windows language names NVDA speaks, as a table recorded on a fleet box and the stand-in that answers NVDA's locale calls from it (`emu/kernel32_standin.py`); see its `README.md`.
- `q1/`, `q2/` the first two questions' probes.
- `q3/` the third: the fleet's sweep re-implemented over the emulator (`sweep.py`, `emulate.py`), the measure (`measure.py`, `shapes.py`, `split.py`), and `results/`.
- `setup.sh` builds what is not here.

## What is not in this repository

These are downloaded or built locally by `setup.sh` into `$EMU_DOWNLOADS` (default `~/spikes/announcement-emulator-5661`):
- the NVDA, Chromium and CLDR sources (`nvda-src`, `chromium-src`, `cldr-src`) and the `nvda-appdir` overlay;
- the Chrome 155 build, and the libraries it needs, unpacked without root;
- the Python toolchain and the virtualenv.

The fleet's captures of the real pages are not here either (third-party pages): only what was derived from them, the agreement tables and each miss's two strings with its address.

## Licence

GPL-3.0. NVDA is GPL-2.0-or-later, taken under version 3 here. Chromium's mapping logic that the tables are derived from is BSD-3-Clause.
