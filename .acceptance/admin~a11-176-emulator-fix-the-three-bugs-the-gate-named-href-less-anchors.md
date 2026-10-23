Fixes the three emulator bugs the Gate (A11-166) named and the `Alt plus, m` access key, each at the Chromium or NVDA source it was found against, and re-scores the Gate's ten misses (and the access-key rows beside them) on a fresh fleet reading, labelled **not held out**.

- An anchor with no `href` is `STATE_SYSTEM_LINKED` when its role is a link (`emu/standin.py`, `ax_platform_node_win.cc:8242-8245`): four Sheffield misses.
- The page is scrolled where NVDA's caret leaves it: `LiveDoc` keeps the last IA2 `scrollTo` request, `q3/sweep.py` delivers it once after the read-through (`q3/emulate.py`): two caselaw and two ICO misses.
- The caret follows its field when the buffer is rebuilt (`storage.cpp:677-686` and `:742-760`, with a stable node id from the extension, `emu/ext2/bg.js`): two Historic Environment misses.
- `accKeyboardShortcut` and the buffer's `keyboardShortcut` answer `Alt+<accesskey>` (`Blink ax_object.cc` `KeyboardShortcut`).

The tests are in `emu/gatefixes/` and read their expected strings from the Gate's committed evidence. `q3/gate/fixed_at_head.py` gives each of the 18 rows (the ten, and the eight access-key rows of the same pages) a status at the freeze re-run and at head; `q3/results/gate-fixes/` holds the readings.

Acceptance: bash -c 'python3 -m unittest discover -s emu/gatefixes -t emu/gatefixes && python3 -m unittest discover -s q3/gate -t q3/gate && python3 q3/gate/fixed_at_head.py q3/results/gate/misses-attributed.json q3/results/gate/misses-held-freeze.json q3/results/gate-fixes/misses-held-freeze.json q3/results/gate-fixes/misses-held-head.json'
