# announcement-emulator

**Status: a spike, finished. Below its Gate on the first reading; at or above it on pages the emulator was never fitted to (the last subsection of `## Re-measure`).** This predicts what NVDA would say when browsing a page in Chromium, on any OS (Linux CI included). It reads Chrome's own accessibility tree, applies
Chromium's Windows (IA2) mapping, and runs NVDA's own Python, at a pinned release, above a rebuilt buffer.

**Its output is a prediction, never evidence.** Nothing here may fill an evidence field in a11ign (a11ign ADR 0021 and ADR 0047).

## Where it stands

The write-up is `docs/announcement-emulator-spike.md`, with Dates, Q1, Q2, Q3, Gate and Reproduction.

- **Q1, done.** The full tree through `chrome.automation`, in a Chrome 155 launched on Linux with a companion extension (`q1/`, `emu/ext2/`).
- **Q2, done.** NVDA's own Python runs on Linux with stand-ins for its Windows modules (`q2/`, `emu/`). On NVDA's own Chrome system tests: 44 of 47 run, 215 of 227 assertions exact, the other 12 attributed.
- **Q3, measured** (`q3/`): agreement with the fleet's NVDA transcripts on 102 real pages, by element kind and by announcement shape. The tables are in the write-up; the derived data is in `q3/results/`.
- **Gate.** At least 98% exact agreement on the 10 commonest shapes, every miss explained as an emulator bug or a Windows-only behaviour. **Not passed** on the first reading (97.61%, held out); **passed** on a new, never-read batch of pages with consent given and the emulator frozen first (A11-166: 3,497 of 3,507 = 99.71%, ten misses, each an emulator bug, named and not fixed). See the write-up; what a pass opens (ADR 0047) is the chairman's.
- **The Gate's bugs, fixed (A11-176, not held out).** The three emulator bugs the Gate named (an anchor with no `href`, the page never scrolled, the caret after a menu closes) and the missing `Alt plus, m` access key are fixed in `emu/` with tests from the Gate's evidence (`emu/gatefixes/`); a fresh fleet reading of the nine pages shows 16 of the 18 rows agreed (`q3/results/gate-fixes/`, the last subsection of `## Re-measure`). The Gate's own figure and `q3/results/gate/` are unchanged.

## What is in this repository

- `emu/` the emulator: the tree source, the Windows mapping (`standin.py`), the buffer builder, the harness around NVDA's code, and the system-test runner (`run_cases.py`).
- `emu/langnames/` the Windows language names NVDA speaks, as a table recorded on a fleet box and the stand-in that answers NVDA's locale calls from it (`emu/kernel32_standin.py`); see its `README.md`.
- `q1/`, `q2/` the first two questions' probes.
- `q3/` the third (`q3/replay/` and `q3/gate/` have the procedures for the scripted replay and for the Gate's re-run, each with a `RUNBOOK.md`): the fleet's sweep re-implemented over the emulator (`sweep.py`, `emulate.py`), the measure (`measure.py`, `shapes.py`, `split.py`), and `results/`.
- `setup.sh` builds what is not here.

## What is not in this repository

These are downloaded or built locally by `setup.sh` into `$EMU_DOWNLOADS` (default `~/spikes/announcement-emulator-5661`):
- the NVDA, Chromium and CLDR sources (`nvda-src`, `chromium-src`, `cldr-src`) and the `nvda-appdir` overlay;
- the Chrome 155 build, and the libraries it needs, unpacked without root;
- the Python toolchain and the virtualenv.

The fleet's captures of the real pages are not here either (third-party pages): only what was derived from them, the agreement tables and each miss's two strings with its address.

## Licence

GPL-3.0. NVDA is GPL-2.0-or-later, taken under version 3 here. Chromium's mapping logic that the tables are derived from is BSD-3-Clause.
