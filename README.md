# announcement-emulator

**Status: a spike, not a product.** This predicts what NVDA would say when browsing a page in Chromium, on any OS (Linux CI included). It reads Chrome's own accessibility tree, applies Chromium's Windows (IA2) mapping, and runs NVDA's own Python, at a pinned release, above a rebuilt buffer.

**Its output is a prediction, never evidence.** Nothing here may fill an evidence field in a11ign (a11ign ADR 0021 and ADR 0047).

## Where it stands

The write-up is `docs/announcement-emulator-spike.md`, with Dates, Q1, Q2, Q3, Gate and Reproduction.

- **Q1, done.** The full tree through `chrome.automation`, in a Chrome 155 launched on Linux with a companion extension (`q1/`).
- **Q2, done.** NVDA's own Python runs on Linux with stand-ins for its Windows modules (`q2/`, `emu/`). On NVDA's own Chrome system tests: 44 of 47 run, 206 of 227 assertions exact, and every miss classified.
- **Q3, next.** Agreement with real-NVDA fleet transcripts on a real-page corpus. It waits for the fleet to capture on one Windows build and one Edge version.
- **Gate:** at least 98% exact agreement on the 10 most common announcement shapes, with every miss explained. Not measured yet.

## What is not in this repository

These are downloaded or built locally; see Reproduction in the write-up:
- the NVDA, Chromium and CLDR sources (`nvda-src`, `chromium-src`, `cldr-src`) and the `nvda-appdir` overlay;
- the Chrome 155 build;
- the libraries Chrome needs, unpacked without root;
- the Python toolchain and the virtualenv.

## Licence

GPL-3.0. NVDA is GPL-2.0-or-later, taken under version 3 here. Chromium's mapping logic that the tables are derived from is BSD-3-Clause.
