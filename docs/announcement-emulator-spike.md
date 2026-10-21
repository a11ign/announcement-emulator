# Announcement-emulator spike (row A11-13, a11ign#5661)

**Status: finished. The Gate is not passed. The spike stops here and this page is the write-up.**

- **Q1: yes**, with named gaps. A Chrome 155 launched on Linux gives the full tree through `chrome.automation.getDesktop()` once a companion extension is allowlisted.
- **Q2: yes.** NVDA 2026.1.1's own Python runs unmodified on Linux with its Windows modules stubbed. 44 of the checkout's 47 system tests run, and **215 of 227 exact-speech
  assertions are exact**. The 12 that are not have two causes, both attributed to the Windows side (one read in Chromium's source, one measured on the fleet); no assertion is unexplained.
- **Q3: measured**, against 102 real pages the fleet captured on 2026-10-20, on the 12 boxes that agree on every version. Over the held-out half of the corpus the exact agreement on
  the ten commonest shapes is **97.61%** (4,497 of 4,607), below the 98% bar. After fixing the two emulator faults that reading revealed (so no longer held out) it is **98.37%** (4,341 of 4,413).
- **Why the Gate is not passed even where a figure clears 98%:** the Gate requires every miss to be explained as an emulator bug or a Windows-only behaviour, and the largest group of misses is
  neither: the word `visited`. The fleet's browsers keep their history, a link is announced `visited` when its address is in it, and the emulator cannot know a box's history (61 of the 110 held-out misses on the ten shapes at the freeze, 64 of 72 after the fixes). Section "Gate" has the figures and the evidence.

The spike's code is in this repository, not in any a11ign repository; nothing here is a prediction written into an evidence record. **The repository existed before this row's Gate, which the
ticket says should create it; that tension is the chairman's to resolve and nothing here moves, renames or publishes it.**

**Where a number comes from is marked on the number:** *measured* (run in this row, output pasted or committed under `q3/results/`), *quoted* (copied, not re-run) or *not checked*. A reading is
a moment. The architecture is [a11ign ADR 0047](https://github.com/a11ign/a11ign/blob/main/docs/adr/0047-an-nvda-faithful-announcement-emulator-is-a-separate-repository-and-its-predictions-are-advisory.md).

## Dates

| | |
|---|---|
| First commit (the import of the spike's code, `fbd0dd9`) | 2026-10-17 |
| Chairman's direction dropping the wait on #2568 | 2026-10-17, on #5661 |
| Budget | 3 weeks from the first commit: until 2026-11-07 |
| Q1 answered; Q2 stage 2 first measured (206 of 227) | 2026-10-17 |
| A11-31 (#5311, the staged 25H2) completed | 2026-10-19 16:36 UTC (Linear) |
| Readiness first read: 12 of 15 boxes agree on every version | 2026-10-20 21:12 UTC (see Q3); the whole fleet never agreed, and has not since |
| The fleet's real-page capture (102 pages, 12 boxes) | 2026-10-20 21:16 to 22:09 UTC |
| Stage A finished: Q2 at 215 of 227, every miss attributed | 2026-10-21 |
| The emulator frozen for the held-out reading (`5fbd726`) | 2026-10-21 00:44 UTC |
| Q3 finished; Gate measured | 2026-10-21 |
| **Days from the first commit to the Gate** | **4 (17 to 21 October), against a budget of 21** |

**The clock.** A11-13 carries no `blockedBy` edge in Linear (read 2026-10-20), so the product-manager ruling that the clock pauses while an edge is open has nothing to pause. The row did wait
for #5311 and the fleet: from 2026-10-17 to the readiness reading above. Counted as waiting, the work took **under 1 day**; counted from the first commit, **4 days**. Either way it is inside 3 weeks,
and the page does not claim a pause it has no edge for.

## Q1. Can a browser we launch on Linux give the full tree through `chrome.automation`?

**Yes, in a build with the allowlist switch, through `chrome.automation.getDesktop()`. Not through `getTree()`.** (*measured* 2026-10-17, unchanged since)

- **Browser.** Chrome for Testing **149.0.7827.55** and **155.0.8059.84** (*measured*, `--version`; 155 is the milestone of the fleet's Edge **155.0.4283.62**, whose build numbers differ because
  Edge and Chrome for Testing number their builds separately). Launched with `--headless=new`, so no X server is needed. Chrome 155 and 149 expose the same set of node fields
  (*measured*: union of enumerable fields over the same fixture).
- **The allowlist switch works, and is required.** The companion extension declares a top-level `automation` manifest key (a `permissions` entry silently gives no API). Launched with
  `--allowlisted-extension-id=<id>` the service worker sees `chrome.automation`; without it the extension loads and `chrome.automation` is `undefined` (*measured*, same extension, fresh profile).
- **`getTree(tabId)` is not in this build's API.** `Object.keys(chrome.automation)` lists `addTreeChangeObserver, getAccessibilityFocus, getDesktop, getFocus, removeTreeChangeObserver,
  setDocumentSelection` and the enums. `getDesktop()` with `"desktop": true` returns the whole browser, and the page's `rootWebArea` hangs under it with its full subtree, **including the
  documents of its iframes**. The ADR's layer 1 should say `getDesktop`, not `getTree`.
- **Fixture size.** A 10-element page gave 107 desktop nodes, 73 in the web area; a 30-element page with forms, a grid, a tree, live regions, an iframe and a contenteditable gave 127 (149) and 131 (155).
  On the real corpus a page is 600 to 2,500 nodes.
- **Fields present** (enumerated on live nodes): `role, name, nameFrom, value, description, descriptionFrom, state{focusable, focused, linked, visited, editable, required, expanded, collapsed,
  multiline, richlyEditable, invisible, offscreen, ...}, checked, hierarchicalLevel, setSize, posInSet, htmlTag, htmlId, inputType, display, language, detectedLanguage, placeholder,
  roleDescription, ariaCurrentState, invalidState, hasPopup, sortDirection, valueForRange/min/max, liveStatus, liveAtomic, liveRelevant, tableRowCount, tableColumnCount,
  tableCellRowIndex, tableCellColumnIndex, tableCellRowSpan/ColumnSpan, tableCellAriaRowIndex, tableCellAriaColumnIndex, tableCellRowHeaders/ColumnHeaders, lineStartOffsets,
  wordStarts/Ends, activeDescendantFor, controlledBy, describedBy, labelFor, indexInParent, bold, italic, underline, lineThrough, fontFamily, fontSize, color, backgroundColor, location,
  url (links and images), selected, textSelStart/End`, and events through `addEventListener`. These are the table indices, set position and size, `lang` and `display` that the ADR says
  `getFullAXTree` lacks.
- **Fields NOT present** (*measured*): a general `htmlAttributes` map (turning the browser's HTML accessibility mode on at `chrome://accessibility`, 2026-10-21, added none), so the author's `role`
  attribute, which IA2 exposes as `xml-roles`, is not available and is **reconstructed** (below); `textAlign`, `textDirection`, `keyShortcuts`, and a `hypertext` string (layer 2 builds it from
  `children`, `name` and `value`). `node.id` is not exposed either, so relations are resolved by object identity within one walk.
- **Sufficiency for layers 2 and 3.** For roles, states, names, descriptions, levels, links, landmarks, relations, table coordinates, spelling and grammar markers and text-field state the fields
  were enough to reproduce 215 of 227 exact-speech assertions (Q2) and, on real pages, the announcements of Q3. What the work found missing or different:
  1. **The author's `role` string** (no `htmlAttributes`). Three things were reconstructed from the automation role and are inferences, not reads: IA2 `xml-roles` for the landmark, article, figure,
     region and switch roles (and `header`, `footer`, below); whether an `image` is an ARIA image and so a leaf (`ax_node.cc:2449` looks at `role="img"`; an image that is not an `<img>` is
     taken to be one); and a canvas's fallback content (approximated by having children).
  2. **A page-level `<header>` and `<footer>` come through as roles `header` and `footer`**, and NVDA says "banner landmark" and "content info landmark" for them on Windows. The tree has no
     `banner` for them, so `xml-roles` banner and contentinfo are supplied for those two roles (read from the fleet's transcripts and a control page, not from Chromium's source).
  3. **Windows hands NVDA what Linux does not**: Chromium's image-description prompt and role text (Q2, Q3), the language names of the OS (Q3), and the browser's history (Q3).
- **Not run (as before):** the 507-test check of the Windows mapping against Chromium's `-expected-win.txt` files. It is not needed for the Gate and was not done.

## Q2. Does NVDA's own Python, at the fleet's release, run on Linux with stubs?

**Yes.** NVDA **2026.1.1** (the release every one of the fleet's boxes reports in `/health.environment.screenReaderVersion`, *measured* 2026-10-20) at tag `release-2026.1.1`, commit
`5d92106f17e461dac62aa48257bbbf4183e033d0`, **unmodified** (`git status` over the checkout is clean after every run). CPython **3.13.16**, which NVDA's `pyproject.toml` requires (`>=3.13,<3.14`).

**Stage 1 (import and speak)** passed on 2026-10-17: the Windows standard-library modules, `comtypes`, `wx`, NVDA's own Windows bindings, the generated COM interfaces, braille and GUI stack and the
object layer are replaced by a permissive stub (33 names, kept in `q2/stubs.py`'s ledger); `speech`, `browseMode`, `virtualBuffers`, `textInfos`, `documentBase`, `controlTypes`,
`characterProcessing`, `speechDictHandler` and `config` are NVDA's real code.

**Stage 2 (NVDA's own Chrome system tests).** The oracle is the tests' own: each test's page, keys and expected strings are read from `tests/system/robot/chromeTests.py` by AST, the page wrapper
is `ChromeLib._writeTestFile`, the settings are `standard-dontShowWelcomeDialog.ini`, speech is captured as `speechSpyGlobalPlugin` does, each test runs in a fresh process, and keys reach a live
Chrome 155 over the DevTools protocol.

**The population.** The ticket and the ADR quote *51 tests, about 220 exact-speech assertions*. The checkout (*measured*) holds **47** test cases in `chromeTests.robot` and **43** `def test_`
functions in `chromeTests.py`, and 219 assertion calls (160 `strings_match`, 31 `speech_matches`, 2 `speech_contains`, 24 `braille_matches`, 2 `braille_contains`): **193 speech assertions and 26 braille**,
against the quoted 220. The 51 may be another release; **this row's numbers are the checkout's.** The extractor unrolls a test's `for` loops, so it evaluates **227** assertion executions.

**How it is built** (the code is `emu/`):
- **Layer 0, driver:** a live Chrome 155 launched with the allowlisted companion extension, keys sent over the DevTools protocol (`Input.dispatchKeyEvent`), the tree and `getFocus()` re-read after each key
  that can change them.
- **Layer 2, Windows mapping** (`standin.py`): maps a `chrome.automation` node to what Chromium's `AXPlatformNodeWin` gives NVDA. The role tables are **generated** from Chromium 155.0.8059.84
  `ax_platform_node_win.cc` (`gen_tables.py`), the IA2 constants from `ia2_api_all.idl`, and the leaf, hypertext, state and attribute rules are ported with the C++ line cited. It is also presented
  as an IAccessible/IAccessible2 object (`objlayer.py`) so that NVDA's own `NVDAObjects.IAccessible` Chrome classes instantiate unmodified.
- **Layer 3, buffer builder:** a port of `gecko_ia2.cpp` `fillVBuf` and `vbufBase/storage.cpp` (markup, offsets, `getLineOffsets`, `findNodeByAttributes`, `nextNodeInTree`).
- **Layer 4, NVDA unmodified:** `ChromeVBuf`, `virtualBuffers`, `textInfos`, `cursorManager`, `browseMode`, `speech`, `speechDictHandler` and `characterProcessing` with the pinned `nvda-cldr` data.
- **Layer 5, event bridge, minimal:** after a key that moves focus the new tree is read, the buffer is rebuilt (not updated incrementally; the caret offset is carried over), and NVDA's own
  `event_gainFocus` runs.
- **Added after reading the expected strings** (so the Q2 figure is a fit to fixtures that were read, not a prediction, and not the Gate): the tests' NVDA settings, `description-from`, the `ChromeVBuf`
  buffer class, the pinned `cldr.dic`, related-element lookups, aria details and error messages, `IAccessibleText` and `IAccessibleHypertext`, non-atomic text fields, list markers, layout tables,
  spelling and grammar markers, the tree-selection caret, Chromium's text style attributes, `IAccessibleAction`, and the harness changes listed under "What was wrong" below. Faults the work found were
  in the stand-in or the harness, none in NVDA.

```
RESULT 215 / 227        44 of 47 tests run; 227 exact-speech assertion executions, 215 exact           (emu/results-final.txt, 2026-10-21)
```

| | tests | assertions |
|---|---|---|
| in the checkout | 47 | 193 speech by grep, 227 as executed |
| **run** | **44** | **227** |
| every assertion exact | 39 | |
| with a miss | 5 | **12** |
| not run, language names from Windows (`reportLanguage*`, 3 tests) | 3 | not counted |
| braille assertions | | 26 by grep, 43 as executed; not checked, there is no braille in the emulator |

The 12 misses, each listed (full output: `emu/results-final.txt`):

| test | assertion | cause |
|---|---|---|
| `announce_list_item_when_moving_by_word_or_character` | Ctrl+Right from "small cat" (expected `cat`, got `small`); the next Right (`a`, got `c`) | **Windows-only editing behaviour of Chromium**, read in source (below) |
| `test_mark_aria_details`, `test_mark_aria_details_FreeReviewCursor` | Ctrl+Right (expected `highlighted  has comment  cat  out of highlighted`, got `word`); the `NVDA+d` after it (`No additional details`) | the same: the caret sits one word earlier, so the details are looked up at the wrong place |
| `test_ariaRoleDescription_inline_browseMode` (3 assertions) | the line with the image: expected `Start  Unlabeled graphic  Our logo. To get missing image descriptions, open the context menu.  End`, got `Start  drawing  Our logo  End` | **Chromium's image-description prompt and the role text `Unlabeled graphic`, present in the fleet's tree and absent from this Linux one** |
| `test_ariaRoleDescription_inline_contentEditable` (3 of 5) | the same line in a contenteditable, and the two Ctrl+Right steps that count from it | the same |

- **Ctrl+Right (6 assertions).** `EditingBehavior::ShouldSkipSpaceWhenMovingRight()` is true only for `kEditingWindowsBehavior`; the header's own comment says Ctrl+Right moves to "abc |def" on Windows and to
  "abc| def" on Mac and Linux (`third_party/blink/renderer/core/editing/editing_behavior.h`, main; *read* 2026-10-17, not reproduced on a Windows Chrome, and the fleet's capture has no Ctrl+Right to reproduce it with).
- **The image-description prompt (6 assertions).** *Measured on the fleet*: the control pages of Q3 (a link whose only content is an `<img>` with no `alt`) are announced
  `To get missing image descriptions, open the context menu., Unlabelled graphic` by Edge 155 on Windows, and the same pages in Chrome 155 on Linux have neither. With `--force-renderer-accessibility`
  the browser's accessibility mode already includes `SCREEN_READER` (locked on at `chrome://accessibility`), so that is not the difference; **the switch that produces the prompt was not isolated.**
- **What was wrong on 2026-10-17 and is not now.** The earlier page counted **21** misses and attributed **10** to Ctrl+Right, **1** to the emulator being incomplete and **4** to causes it could not
  name. Re-measured: 12 misses. (a) `test_pr11606` (`NVDA+UpArrow` spoke `list`): the harness read the line from the browse-mode buffer, where NVDA's own `script_reportCurrentLine` reads the focus object in
  focus mode; the harness now runs that script (+1). (b) `getLineOffsets` was ported without its `maxLineLength` refinement and without walking control nodes, so an empty block did not end a line; ported as
  written (`storage.cpp:1066-1198`) it fixes `test_mark_browse`'s review-cursor step and **four** of the ten steps attributed to Ctrl+Right (+5): they were this, not a Windows behaviour. (c) The three
  table say-all steps were missing Chromium's `colindex`/`rowindex` attributes, which it exposes where the ARIA index differs from the physical one (`ax_platform_node_base.cc:1349`) and which NVDA reports as
  `table-columnnumber-presentational` (`gecko_ia2.cpp:984`): **after a cell that spans rows the Windows column is the ARIA one**, and the fleet confirms it (*measured* 2026-10-21: NVDA's own test table,
  captured by a worker with the table probe, reads `row 2, column 1, A 2; column 2, B 2; column 3, D 2`), +3. Total +9 on the 206 of 2026-10-17 (+1, +5, +3), 215.
- **No test was bent.** Every change above is to the stand-in or the harness, none to NVDA's source or to an expectation; `emu/results-final.txt` is the unedited run, and a clean build from `setup.sh`
  (below) reproduces it.
- **A fit to fixtures that were read, not a prediction, and not the Gate.** Everything listed under "Added after reading the expected strings" above still applies.
- **Reconstructed, not read:** `xml-roles` (above), `getTextFromIAccessible` and `findContentDescendant` (approximations of native routines), the Uniscribe word-break table (`textUtils.cpp`'s
  `ScriptBreak` is an OS text service; the break attributes are an approximation of Unicode word stops, so any word-unit result that differs is Windows-OS-dependent), and `cldr.dic`, which is the
  pinned `nvda-cldr` data and not an empty file.
- **What is not covered.** Three tests compare speech with Windows' own language names (`languageHandler.getLanguageDescription` calls `GetLocaleInfo`, `languageHandler.py:164`) and are out of scope;
  the braille assertions have no emulator counterpart.

## Q3. How closely does it agree with fleet transcripts on the real-page corpus?

**Measured: 97.61% exact on the ten commonest shapes over the held-out half of the corpus (4,497 of 4,607), 98.37% after the fixes the reading revealed (4,341 of 4,413). Figures, populations,
definitions and every miss follow. The Gate section says what that does and does not pass.**

### What was compared

- **The oracle** is the fleet's own capture record of a real page: the `structure` lists, one per quick-navigation sweep (`headings`, `landmarks`, `formFields`, `graphics`, `links`, `lists`, `frames`),
  each the phrases Guidepup logged for NVDA's answer to the next-element key, in the order the worker met them. (`tableCells` is not swept for real pages: the table probe is opt-in and the worker's
  own comment says not to use it as evidence yet.)
- **The emulator** repeats the worker's procedure on the same address (`q3/sweep.py`, a re-implementation of `capture-probes.mjs` and `capture-pure.mjs`, not an import): load the page, `Escape` and
  `Ctrl+Home`, read it line by line with Down Arrow until the worker's own stop rules end the read (page bottom, a wrap, silence, 600 lines), then sweep headings, landmarks, form fields (activating a
  control announced `collapsed` with Enter, `NVDA+Tab` and `Escape`, and none else, as `probeForms` off allows), graphics, links, then, after another `Escape`+`Ctrl+Home`, lists and frames, each
  backwards from where the caret stands and then forwards, deduplicating by the worker's `dedupeKey`, stopping on "no next", silence, 25 identical phrases or 250 steps. **What is logged for a key is
  what Guidepup 0.31.0 logs**: the strings of the *first* speech message NVDA's Remote Access sends after the key (capture mode `initial`, the default; `CAPTURE_OPTIONS` is undefined in
  `capture-setup.mjs`), trimmed, runs of white space collapsed, joined with `, `.
- **Exact** is byte-equal strings. Nothing else is applied: both sides are already what the worker records.
- **Unit and agreement.** One announcement is one entry of one channel of one page. It is **agreed** when it lies in the longest order-preserving matching of the fleet's list and the emulator's list by
  exact equality (so one element the emulator misses, or adds, costs one, not every element after it). The count of announcements that agree *by position* is printed beside it and is lower.
- **A shape** is the tuple of token kinds (ROLE, STATE, LEVEL, COUNT, POSITION, NAME) of an announcement split on `,`, by `classify()` of the fleet's `measure_announcement_shapes.py`, re-implemented in
  `q3/shapes.py` (not imported: ADR 0045) with the role and state words read from the NVDA source this spike runs. **The ten commonest are ranked over the comparable pages of the run measured**, in
  the channels that script reads (not frames).
- **Fixed before any figure existed:** these definitions, the dev/held split (below), and the rule that a page is compared only if its two emulator runs agree and its census matches.

### The oracle: the fleet, and the day it was read

Read-only, 2026-10-20 21:12 UTC, `fleet:status` and each box's `/health` (`q3/results/fleet-readings.txt`):

| | boxes | Windows | Edge | NVDA | worker code |
|---|---|---|---|---|---|
| **used** (workers 2 3 4 7 8 9 10 12 13 14 15 16) | **12** | 11 Pro 26300.9711 | 155.0.4283.62 | 2026.1.1 | `25bb45d9b38d7a62` |
| left out: worker 6 | 1 | 26300.9711 | **155.0.4283.45** | 2026.1.1 | `25bb45d9b38d7a62` |
| left out: worker 11 | 1 | **26200.9457** | **155.0.4283.45** | 2026.1.1 | `25bb45d9b38d7a62` |
| left out: worker 5 | 1 | **22631.6199** (23H2, a CPU limit) | **155.0.4283.45** | 2026.1.1 | **`8f07fd23dc694ef3`** |

The whole fleet never agreed (A11-31 closed on 2026-10-19 with the pin still at `.45` on three boxes; the Edge pin is control#116's, and this row changes none of it), so the rule set for this row applied: capture on
the largest group that agrees (at least three), name it, and say what was left out. Twelve boxes agree on build, Edge, NVDA release, provision revision (`a20963f766666de8`), Guidepup (0.31.0), capture protocol (24) and
window (1024x768, which the browser reports as 1008x729 inside). **Read again after the capture, unchanged** (the same table, `/health`, 2026-10-21 00:5x UTC). The NVDA settings, from the worker's
`/diagnostics`: the voice is the OneCore `MSTTS_V110_enGB_GeorgeM`, `documentFormatting.reportEmphasis` and `reportLanguage` are on, `autoLanguageSwitching` on, `autoDialectSwitching` off, the Speech
Viewer off, and everything else is NVDA's default (`q3/nvda-fleet.ini`). The system tests of Q2 use another file (`reportLinkType` off), which is why Q2 and Q3 are run under different settings.

**The capture.** `capture-real-pages.mjs --role=calibration`, `--role=training`, `--role=field` (the roles `lab:pipeline --pipeline=real-pages` names), from the a11ign checkout on this host, with
`A11Y_WORKERS` set to the twelve and the output kept outside every repository. The script's `assertFleetRunsThisCheckout` refused (this host's checkout expects worker code `dbe7c8cf55f930ba` from a layer
clone older than what control deploys), so **`--allow-stale-workers` was passed**; the script says so in its output, the fleet serves one code hash on all twelve, and the script is the same as
`a11ign/lab`'s apart from one import path. `lab:pipeline` itself could not be used: it runs from the control plane, which this host is not. Request body as the script sends it: `probeForms` false,
`probeFocus`, `probeNavigation`, `probeFocusContext`, `probeFocusReveal` on, `steps` 600. **102 pages (55 calibration, 41 training, 6 field), 21:16 to 22:09 UTC, 0 failed.** The lab's own identity check
found 101 of 102 described the page requested (not matched: `mailchimp.com`). Nothing was changed on any box.

**Two oracle faults found.** (1) **On four pages the fleet's browser was not on the requested page** when NVDA read it: `documentReady` reports the title `Microsoft Terms of Use ... Microsoft Edge` for
`components/error-message/` and `components/error-summary/` (every announcement of both records is Microsoft's), and `Copilot` for two W3C demo pages. A fifth, a control page of ours (below), came back as the page titled `Copilot` on its first request after a quiet period. Those pages are *not comparable*. (2) **The fleet's browser keeps its history**, and Chromium announces a link `visited` when its address is in it.
That is the largest source of misses (below), and it is not something this host can read: the Ansible route is not available here (no inventory on this host), and a worker's `/diagnostics`
reports only the profile's size.

### The emulator, as run for Q3

The code is Q2's, with the harness of `q3/` around it, **frozen at commit `5fbd726` before the held-out half was measured** (`q3/results/` has the runs; the Q2 suite at that commit is 215 of 227). What
differs from Windows, all of it deliberate and listed so a miss can be read against it: (a) Chrome 155.0.8059.84 for Testing on Linux, `--headless=new`, a Windows Edge user agent and a 1008x872 window
(the page gets the fleet's 1008x729); (b) the fleet's NVDA settings; (c) NVDA's `scrollIntoView` is **not** delivered to the browser per key (it costs a second a key; `LivePage.scroll_browser`); at the freeze nothing stood in for it, and
the **scroll pass** that now does (the page is scrolled to its end and back before the sweeps, so what loads on scroll has loaded) was added after the held-out reading; (d) the display model answers empty; (e) the browser's
history is modelled as the first link of each page of the corpus (`q3/make_history.py`: the route-change probe follows it), which is a guess about the fleet and is wrong in both directions (below);
(f) no OS language names, no Chromium image-description prompt, no `Ctrl+Right` quirk (Q2).

### The protocol: development half and held-out half

A page is **dev** when the SHA-256 of its address, read as a number, is even (42 pages) and **held** when odd (60 pages) (`q3/split.py`), a function of the address alone, fixed before any figure existed.
The emulator was fixed against the dev pages' fleet strings only (`measure.py` refuses to print a held page's strings without `--final`). At commit `5fbd726` it was frozen and run once on the held
pages, twice per page. Fixes made *after* reading the held-out misses (two) are marked and measured separately: that second figure is **no longer held out**.

| run | dev pages | held pages |
|---|---|---|
| first full dev reading, after the first fixes (`2341750`) | 97.02% (2,965 of 3,056, 32 comparable pages) | not read |
| **at the freeze** (`5fbd726`) | 98.37% (3,023 of 3,073, 30 pages) | **97.61% (4,497 of 4,607, 47 pages)** |
| after the held-out reading (`529e4ec`) | 98.37% (3,023 of 3,073) | 98.37% (4,341 of 4,413, 46 pages), **not held out** |

### The results

**At the freeze, held-out half** (`q3/results/measure-held-freeze.txt`; pasted):

```
pages 60 (held)  comparable: 47   unstable: 3   not comparable: 9   emulator fault: 1
   unstable: https://data.southwark.gov.uk/data-catalog-explorer/  [unstable: the two emulator runs differ]
   unstable: https://www.hubspot.com/  [unstable: the two emulator runs differ]
   unstable: https://www.leeds.ac.uk/undergraduate  [unstable: the two emulator runs differ]
   not comparable: https://european-union.europa.eu/index_en  [not comparable: link fleet 32 / emulator 31]
   not comparable: https://sheffield.ac.uk/postgraduate/taught/courses/2027  [not comparable: heading fleet 24 / emulator 25]
   not comparable: https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings  [not comparable: heading fleet 0 / emulator 24, link fleet 6 / emulator 8]
   not comparable: https://www.adobe.com/  [not comparable: heading fleet 25 / emulator 24, link fleet 30 / emulator 24]
   not comparable: https://www.historicenvironment.scot/visit/all/edinburgh-castle/  [not comparable: headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.nidirect.gov.uk/information-and-services/motoring/mot-and-vehicle-testing  [not comparable: headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.nrscotland.gov.uk/publications/  [not comparable: heading fleet 20 / emulator 1, link fleet 45 / emulator 1, headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.nrscotland.gov.uk/statistics-and-data/  [not comparable: heading fleet 3 / emulator 1, link fleet 37 / emulator 1, headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.w3.org/WAI/demos/bad/before/news.html  [not comparable: document title fleet 'Copilot' / emulator 'Welcome to CityLights! [Inaccessible New', headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   emulator fault: https://ico.org.uk/action-weve-taken/enforcement/  [emulator fault: timeout 900s]
agreement by element kind (47 comparable pages)
     exact / total       %  positional
      695 / 739       94.0%         614  headings
     3491 / 3602      96.9%        3406  links
      265 / 267       99.3%         252  buttons
      583 / 620       94.0%         565  formFields
      472 / 508       92.9%         460  landmarks
      494 / 503       98.2%         494  lists
      120 / 138       87.0%         104  graphics
       47 / 60        78.3%          47  frames

agreement by swept channel
     exact / total       %  positional
      695 / 739       94.0%         614  headings
      472 / 508       92.9%         460  landmarks
      848 / 887       95.6%         817  formFields
      120 / 138       87.0%         104  graphics
     3491 / 3602      96.9%        3406  links
      494 / 503       98.2%         494  lists
       47 / 60        78.3%          47  frames

shapes: 6377 announcements in 283 distinct shapes; top 10 cover 4607 = 72.2% (the fleet's script quotes 33 shapes, top 10 = 94.3%)

agreement by shape (top 10, ranked in this run)
     exact / total       %  positional
     2260 / 2274      99.4%        2191  NAME + ROLE
      455 / 467       97.4%         390  NAME + ROLE + LEVEL
      421 / 427       98.6%         416  NAME + ROLE + STATE
      321 / 321      100.0%         313  NAME + ROLE + ROLE + COUNT + NAME + ROLE
      286 / 286      100.0%         277  ROLE + COUNT + NAME + ROLE
      255 / 261       97.7%         251  NAME + NAME + ROLE
      189 / 248       76.2%         185  NAME + STATE + ROLE
      106 / 111       95.5%          96  NAME + ROLE + NAME + ROLE + LEVEL
      109 / 109      100.0%         107  NAME + ROLE + ROLE + LEVEL
       95 / 103       92.2%          86  NAME + ROLE + NAME + ROLE

GATE: 4497 of 4607 = 97.61% exact on the top 10 shapes   (positional: 4312 of 4607)   [BELOW 98%]
      with the not-comparable pages kept in: 4797 of 4955 = 96.81%
      emulator announcements with no counterpart in the fleet's lists (extras): 222
      top-10 misses by cause: history 61, unexplained 43, language 6
      the same, with the pages' `history` misses not counted as misses against us: 4558 of 4607 = 98.94%   (an upper bound if the fleet's browser history could be reproduced)
      misses over all channels: 270 of 6437; on top-10 shapes: 110
```

The measure's `unexplained 43` is split by `q3/attribute.py` (below) into 34 shown to be emulator bugs and 9 left; its `history` and `language` are rules in `measure.py`'s `classify`.

**After the held-out reading** (`q3/results/measure-held-post.txt`; pasted; not held out):

```
pages 60 (held)  comparable: 46   unstable: 4   emulator fault: 1   not comparable: 8   second run fault: 1
   unstable: https://data.southwark.gov.uk/data-catalog-explorer/  [unstable: the two emulator runs differ]
   unstable: https://design-system.service.gov.uk/components/radios/  [unstable: the two emulator runs differ]
   unstable: https://www.dropbox.com/  [unstable: the two emulator runs differ]
   unstable: https://www.leeds.ac.uk/undergraduate  [unstable: the two emulator runs differ]
   emulator fault: https://ico.org.uk/action-weve-taken/enforcement/  [emulator fault: timeout 600s]
   not comparable: https://sheffield.ac.uk/postgraduate/taught/courses/2027  [not comparable: heading fleet 24 / emulator 25]
   not comparable: https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings  [not comparable: heading fleet 0 / emulator 24, link fleet 6 / emulator 8]
   not comparable: https://www.historicenvironment.scot/visit/all/edinburgh-castle/  [not comparable: headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.hubspot.com/  [not comparable: link fleet 80 / emulator 81, document title fleet 'Hub Spot Software and Tools for your Bus' / emulator 'HubSpot | Software & Tools for your Busi']
   not comparable: https://www.nidirect.gov.uk/information-and-services/motoring/mot-and-vehicle-testing  [not comparable: headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.nrscotland.gov.uk/publications/  [not comparable: heading fleet 20 / emulator 1, link fleet 45 / emulator 1, headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.nrscotland.gov.uk/statistics-and-data/  [not comparable: heading fleet 3 / emulator 1, link fleet 37 / emulator 1, headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   not comparable: https://www.w3.org/WAI/demos/bad/before/news.html  [not comparable: document title fleet 'Copilot' / emulator 'Welcome to CityLights! [Inaccessible New', headings read fleet fleet names 1, 0% of them found in the emulator's / emulator a different document]
   second run fault: https://www.adobe.com/  [second run fault: timeout 600s]
agreement by element kind (46 comparable pages)
     exact / total       %  positional
      675 / 676       99.9%         675  headings
     3367 / 3480      96.8%        3282  links
      261 / 262       99.6%         253  buttons
      593 / 593      100.0%         588  formFields
      468 / 505       92.7%         456  landmarks
      483 / 492       98.2%         483  lists
      107 / 123       87.0%         107  graphics
       50 / 50       100.0%          50  frames

agreement by swept channel
     exact / total       %  positional
      675 / 676       99.9%         675  headings
      468 / 505       92.7%         456  landmarks
      854 / 855       99.9%         841  formFields
      107 / 123       87.0%         107  graphics
     3367 / 3480      96.8%        3282  links
      483 / 492       98.2%         483  lists
       50 / 50       100.0%          50  frames

shapes: 6131 announcements in 281 distinct shapes; top 10 cover 4413 = 72.0% (the fleet's script quotes 33 shapes, top 10 = 94.3%)

agreement by shape (top 10, ranked in this run)
     exact / total       %  positional
     2154 / 2155     100.0%        2102  NAME + ROLE
      419 / 420       99.8%         419  NAME + ROLE + LEVEL
      417 / 417      100.0%         414  NAME + ROLE + STATE
      316 / 316      100.0%         308  NAME + ROLE + ROLE + COUNT + NAME + ROLE
      280 / 280      100.0%         271  ROLE + COUNT + NAME + ROLE
      252 / 258       97.7%         248  NAME + NAME + ROLE
      187 / 249       75.1%         183  NAME + STATE + ROLE
      109 / 109      100.0%         107  NAME + ROLE + ROLE + LEVEL
      107 / 107      100.0%         105  NAME + ROLE + NAME + ROLE + LEVEL
      100 / 102       98.0%          96  NAME + ROLE + NAME + ROLE

GATE: 4341 of 4413 = 98.37% exact on the top 10 shapes   (positional: 4253 of 4413)   [AT OR ABOVE 98%]
      with the not-comparable pages kept in: 4695 of 4798 = 97.85%
      emulator announcements with no counterpart in the fleet's lists (extras): 191
      top-10 misses by cause: history 64, language 6, unexplained 2
      the same, with the pages' `history` misses not counted as misses against us: 4405 of 4413 = 99.82%   (an upper bound if the fleet's browser history could be reproduced)
      misses over all channels: 177 of 6181; on top-10 shapes: 72
```

**The whole corpus**, both halves, comparable pages: after the fixes **98.40% (7,357 of 7,477)**; at the freeze 98.02% (7,522 of 7,674). The dev half was developed against, so this is not a held-out figure.
On the ten shapes the corpus is not what the quoted 94.3% describes: on real pages the ten commonest shapes cover **72.8%** of announcements (384 distinct shapes, against 33 on the fleet's synthetic
dataset), so the Gate speaks for about three quarters of what NVDA says on these pages. Over **every** announcement of every channel (frames included) on the comparable pages, the agreement after the
fixes is **10,049 of 10,349 = 97.1%**.

**Not comparable, listed** (kept out of the denominators; with them in, the held-out figure at the freeze is 96.81% and after the fixes 97.85%): the pages in the headers above. Their reasons, as the
measure states them: the document title or the heading/link census differs from the emulator's (a live page that changed, or the fleet's browser on another document, or a bot-protection page for the
headless browser: `nrscotland.gov.uk` gave the emulator one heading and one link: probably a bot-protection page, not checked), or the two emulator runs disagree (a carousel or a feed). **Two comparability rules were corrected after the first held-out
reading** and both corrections are in the figures above, with the first reading kept: the title test compared what the fleet's NVDA *spoke* (`GOV dot UK Design System`) with the document's (`GOV.UK Design
System`), which excluded nine pages whose identity is not in doubt, and the graphic count was used although the fleet's census and the emulator count images differently (on W3C's demo pages, which do
not change, they differ by two), which excluded four more. **As first frozen, the held-out figure was 98.12% (3,071 of 3,130) over 34 pages**, and after the fixes 98.00% (2,995 of 3,056); the corrected rules put 13 more pages in
and the figure lower, not higher (`q3/results/measure-held-freeze-as-frozen.txt`, `measure-held-post-as-frozen.txt`).

**The control: static pages, no drift.** The control this row set is the synthetic dataset pages (1,715 cases, 3,430 pages, `runs/screenreader-dataset/pages`). Its fleet captures are not on disk, so a fixed
sample was captured on the fleet for this row: every 21st page of the sorted list, **160 pages**, served from `capture-host` (the machine this work ran on) and captured by the twelve boxes with the same request as the real pages
(`q3/control_capture.py`). The emulator, unchanged, on them (`q3/results/measure-control-freeze.txt`). Their strings were read while the emulator was developed, to see what the misses were (the image prompt, `visited`, and the order that follows a missing graphic), but **nothing in the emulator was changed because of them**:

```
agreement by element kind (159 comparable pages)
     exact / total       %  positional
      702 / 702      100.0%         702  headings
      916 / 938       97.7%         908  links
       92 / 92       100.0%          92  buttons
      107 / 107      100.0%         107  formFields
      184 / 184      100.0%         184  landmarks
      162 / 162      100.0%         162  lists
       23 / 33        69.7%          23  graphics

agreement by swept channel
     exact / total       %  positional
      702 / 702      100.0%         702  headings
      184 / 184      100.0%         184  landmarks
      199 / 199      100.0%         199  formFields
       23 / 33        69.7%          23  graphics
      916 / 938       97.7%         908  links
      162 / 162      100.0%         162  lists

shapes: 2218 announcements in 28 distinct shapes; top 10 cover 2122 = 95.7% (the fleet's script quotes 33 shapes, top 10 = 94.3%)

agreement by shape (top 10, ranked in this run)
     exact / total       %  positional
      707 / 721       98.1%         699  NAME + STATE + ROLE
      616 / 616      100.0%         616  NAME + ROLE + LEVEL
      211 / 211      100.0%         211  ROLE + NAME + ROLE + LEVEL
      192 / 192      100.0%         192  NAME + ROLE
      137 / 143       95.8%         137  ROLE + COUNT + NAME + STATE + ROLE
      142 / 142      100.0%         142  ROLE + COUNT + NAME + NAME
       38 / 38       100.0%          38  NAME + ROLE + STATE
       31 / 31       100.0%          31  ROLE + ROLE + NAME
       15 / 15       100.0%          15  ROLE + COUNT + NAME
       13 / 13       100.0%          13  ROLE

GATE: 2102 of 2122 = 99.06% exact on the top 10 shapes   (positional: 2094 of 2122)   [AT OR ABOVE 98%]
      with the not-comparable pages kept in: 2102 of 2122 = 99.06%
      emulator announcements with no counterpart in the fleet's lists (extras): 26
      top-10 misses by cause: prompt-downstream 16, history 4
      the same, with the pages' `history` misses not counted as misses against us: 2106 of 2122 = 99.25%   (an upper bound if the fleet's browser history could be reproduced)
      misses over all channels: 32 of 2218; on top-10 shapes: 20
```

All 20 misses on the ten shapes are accounted for: **16 are downstream of one prompt** (a page with an unlabelled image: the fleet's graphic sweep finds it, the emulator's does not, the link sweep begins
where the graphic sweep ended and so reaches the links in another order; inferred from the same page carrying the prompt miss) and **4 are `visited`**. On static pages the emulator agrees with the fleet
on every other announcement of the ten shapes.

### What the held-out reading found, and what was done

The 270 held-out misses of all channels at the freeze, and the 110 on the ten shapes (`q3/results/misses-held-freeze-attributed.json` has every one: page, channel, expected, predicted, cause):

| cause | on the ten shapes | all channels | evidence |
|---|---|---|---|
| **emulator bug, shown** by fixing it | 34 | 71 | agreed after the fix on the same page, comparable in both runs. Of the 71: 69 are **lazily loaded content** (four GOV.UK Design System component pages, and one line of `ofgem.gov.uk`, load what they show on scroll; the emulator read the page before it existed, and the fleet's NVDA scrolls the browser as the caret moves), 2 are a **toggle button announced `checked`** as well as `pressed` (`ax_platform_node_win.cc:8161`) |
| **history** (`visited`) | 61 | 137 | the only difference is where the word `visited` stands; below |
| **Windows-only: language names** | 6 | 20 | the fleet says `Welsh (not supported)`, the emulator `cy (not supported)`, or the fleet says `English` where the emulator says nothing; `languageHandler.getLanguageDescription` calls `GetLocaleInfo` (`languageHandler.py:164`) for the name; the fleet's transcripts show the Windows names |
| **unexplained** | 9 | 42 | below |

The unexplained nine at the freeze: six on `components/radios/` (the same missing frame contents as the lazy-loading group, but the page's two runs disagreed after the fix, so it is not shown), one each on
`bathingwaters.sepa.org.uk` (a cookie region the fleet's browser had and the emulator's did not), `dropbox.com` (an image the fleet announces, the emulator misses; unstable) and `notion.com`
(a hero line that rotates: the fleet read `Build together.`, the two emulator runs `Create` and `Jam`). **A miss that is explained by a live page is not accepted as an explanation** (a rule set for this row before anything was measured), so
these stay unexplained.

**After the fixes** (held, not held out), the 72 misses on the ten shapes are **64 history, 6 language names, 2 unexplained** (`bathingwaters` and `notion`, above).

### `visited`: the largest source of misses, and neither of the Gate's two classes

A link whose address is in the browser's history is announced with `visited`. The fleet's browsers keep their history across captures. It is **not an emulator bug** (a fresh Chrome has no history; the
emulator can only guess) and **not Windows-only** (any Chromium would say it with the same history). Of the held-out misses on the ten shapes, `visited` is 61 of 110 at the freeze and 64 of 72 after the fixes;
it alone makes the shape `NAME + STATE + ROLE` agree 73.0% (254 of 348) over the corpus, and every other shape of the ten at least 96.2%. The emulator's guess (a profile that has visited the first link of
each corpus page) is right on many pages (the cookie-settings link every GOV.UK Design System page opens) and wrong in both directions (W3C's home link is `visited` on the fleet and cannot be derived from
the corpus; a skip link is `visited` in the emulator and not on the fleet). **Leaving `visited` out of the comparison would put the held-out figure after the fixes at 99.82% (4,405 of 4,413) and the
whole corpus at 99.67%**; that is a statement about the emulator and not a Gate figure, because the Gate says nothing is left out.

### Reproduction of the measurement

`python q3/run_all.py <oracle_dir> <out_dir> --split held --runs 2 --history <history.json>` runs the emulator, `python q3/measure.py <oracle_dir> <out_dir> --split held --final` measures. The oracle
records are third-party pages and are not committed; `q3/results/` has the derived data: the corpus list with each page's split, the measure's output for each run, every miss with its two strings, the
fleet readings, and the control pages with the fleet's records of them.

## Gate

**Measured exact agreement on the ten commonest announcement shapes, held-out half of the real-page corpus, at the freeze: 4,497 of 4,607 = 97.61%. Below 98%. The Gate is not passed.**

| | exact / total | | pages compared | not comparable |
|---|---|---|---|---|
| **at the freeze (`5fbd726`), held out, rules as corrected** | **4,497 of 4,607 = 97.61%** | below 98% | 47 of 60 | 9, and 3 unstable, 1 timed out |
| the same, rules as first frozen | 3,071 of 3,130 = 98.12% | at or above | 34 of 60 | 22 |
| after fixing what the held-out reading showed (not held out) | 4,341 of 4,413 = 98.37% | at or above | 46 of 60 | 8, and 4 unstable, 2 timed out |
| the whole corpus, after the fixes (the dev half was developed against) | 7,357 of 7,477 = 98.40% | at or above | 76 of 102 | 19 |
| the control: 160 static synthetic pages (read, nothing fitted to it) | 2,102 of 2,122 = 99.06% | at or above | 159 of 160 | 1 |

**Each miss, as the ticket asks:** the ten shapes' 110 misses at the freeze are classed above and in `q3/results/misses-held-freeze-attributed.json` with their expected and predicted strings and addresses.
The ticket's Gate is "at least 98% exact agreement ... every miss explained as an emulator bug or a Windows-only behaviour"; this row read that as *at least 98% and no unexplained miss*, and took a miss on a page that changed as unexplained, not explained:

- **At the freeze, the Gate is not passed on the number (97.61%) and on the rule**: 34 misses are emulator bugs (fixed afterwards, shown by the same strings agreeing), 6 are Windows-only (language names, with
  the source line and the fleet's transcripts), **61 are `visited`, which fit neither class, and 9 are unexplained.**
- **After the fixes the number is 98.37% and the rule still fails**: 6 Windows-only, **64 `visited`**, 2 unexplained. That figure is not a held-out figure (the two faults were found by reading the held-out misses), and the rule fails on `visited`, which the two classes do not cover, whatever the number.
- **What a pass would need.** Either the Gate's wording accepts a third class for the oracle's own state (the fleet's browser history), or the oracle is re-captured on a browser with no history, which
  is a worker change (a clean or private profile) and not this row's, and which this host cannot do: the fleet is changed through Ansible from the control plane, and no inventory is available here.
  With `visited` removed the emulator is at 99.8% on the held-out half. **That decision is the chairman's, and this page does not make it.**

**What the number means.** After the two faults were fixed the emulator reproduces the exact words NVDA speaks for about 98.4% of the announcements of the ten commonest shapes on these real pages
(98.37% held out, 98.40% over the corpus), and 99.1% on static pages. It is not 98% of everything NVDA says: the ten shapes are 72.8% of the announcements on these pages, and over every announcement
the agreement is 97.1%. It was measured against twelve boxes of one fleet on one day, on pages that change, with a state of the fleet's own (browser history) that the Gate's two classes cannot absorb.

**Below the gate, the spike stops here.** Nothing beyond the spike is built: no CI engine, no listen mode, no extension. The repository, its name, its licence wording ("only" or "or later") and the
absorption of `nvda-speech` (ADR 0047, Decision 3) are the chairman's and are untouched.

## Re-measure

**Re-measured on 2026-10-21, with the fleet's browsers keeping no history: the held-out figure at the freeze is 4,426 of 4,480 = 98.79%, at or above 98%, and `history` is 0 of its 54 misses (it was 61 of 110). On the reading used above (at least 98% and no unexplained miss) the Gate is still not passed: 13 of the 54 misses are unexplained.** Nothing above this section is changed, and no emulator fix was made.

**The set-up.** The twelve boxes that agree on every version `fleet:status` prints (Edge 155.0.4283.62, Windows build 26300.9711): `a11y-worker-2`, `-3`, `-4`, `-7`, `-8`, `-9`, `-10`, `-12`, `-13`, `-14`, `-15`, `-16`; the page server is `capture-host`. (`a11y-worker-5`, `-6` and `-11` read other Edge or Windows builds and were not used.)
Each box, one at a time and the first alone, was given Edge's `SavingBrowserHistoryDisabled=1` through the fleet's own play, `provision-role.yml --tags policy`, with an extra-vars file that restates the declared `worker_edge_policy` and adds the one value
(`q3/remeasure/policy_override.py`; control is unchanged). The play's own task `Refuse to call this provisioned if a policy value did not land` was `ok` and its recap `failed=0` on every box (`fleet/plays/`); `win_reg_stat` then read the value `1`; the box's `History` and `History-journal` were removed by `win_file` as the worker's own account
(Edge was stopped first, by ad-hoc Ansible on the idle box: the worker keeps it alive between captures, which the plan had not expected; `q3/remeasure/RUNBOOK.md` has every command). The same play also converged the values the role already declares (the screensaver, OneDrive's run entries; `Evict OneDrive itself` reports `changed` on every run). The profile directory was kept: a new one brings back the first-run surface.
**The read-back is a capture:** `q3/remeasure/visited-probe.html`, a page of ours with a link to itself and a link to a page nobody opens, captured by each box before (the first capture visits the page, a later one reads it) and after the policy (a visit, then a read), and again after the corpus.
Before the policy the probe read the self link as `visited` on ten of the twelve boxes (not on `a11y-worker-10` or `-14`, in three reads each, `fleet/run-log.txt`: Edge writes its history in batches), so it can see history; after it, on **all twelve** boxes, at the end of the run too, it read neither link as `visited`.
Every reading is in `q3/results/remeasure/history-readback.json` (the probe records, with `capture-host` for the server, are in `fleet/probes/`), and every record of the new oracle carries a `history` block (the policy value, when it was read back, that the store was emptied, the probe) in `q3/results/remeasure/oracle-summary.json`.

**The capture.** The same 102 addresses (`q3/results/corpus.json`), the same request as before, by `q3/corpus_capture.py`: **102 captured, 0 failed, 11:03Z to 11:57Z.** The first attempt (11:03Z to 11:13Z) kept 3 records and lost the rest to the capture client, whose `fetch` gives up on a worker's answer after 300 s;
`fleet_capture.mjs` now waits with `node:http`, and the other 99 were captured from 11:14Z (`capture-run.json`, `capture-run-attempt1.json`, which counts 13 `UND_ERR_HEADERS_TIMEOUT` and 185 `429 a capture is already in progress` among its failures). The records name their worker and `capture-host`, never an address.
Two things the plan did not foresee. The worker **keeps Edge alive across captures** (`browserReused` in all 102 records, `oracle-summary.json`) rather than launching it once per page. And **7 `visited` announcements remain, on 4 pages** (`design-patterns.service.justice.gov.uk/components/filter/`, `european-union.europa.eu/index_en`,
`reports.ofsted.gov.uk/search?q=school`, `www.ons.gov.uk/economy/inflationandpriceindices`); each is a link that points at the page itself or into it (five of the seven are announced `same page`). The plan said a non-zero count stops the run. They are not history carried between captures: the emulator's Chrome, fresh, with no history model
and nothing visited before, announces **the same seven strings** (`q3/remeasure/explain_visited.py`, `visited-explained.json`), so the browser marks the page it is on, whatever its history holds. The check was made to say so rather than to count to zero, and it refuses any `visited` the emulator does not make.

**The figures** (`q3/results/remeasure/`, the split rule unchanged, `measure.py` at head with the corrected comparability rules, the emulator run without `--history`, two runs a page; the freezes were named in `freeze.json` and committed, at 08:54Z, before any record of the new oracle existed (the first was captured at 11:05Z)):

| | exact / total | | pages compared | not comparable |
|---|---|---|---|---|
| **Gate figure: held out, the emulator frozen at `5fbd726`** | **4,426 of 4,480 = 98.79%** | at or above 98% | 44 of 60 | 12, and 3 unstable, 1 timed out |
| the same, with the not-comparable pages kept in | 4,924 of 5,057 = 97.37% | | | |
| the emulator at head (`43b7fc1`, after the held-out reading fixed two faults; **not held out**) | 4,389 of 4,407 = 99.59% | at or above | 44 of 60 | 10, and 5 unstable, 1 timed out |
| for comparison, the spike's reading at the freeze (before) | 4,497 of 4,607 = 97.61% | below | 47 of 60 | 9, and 3 unstable, 1 timed out |

The shape that history had broken is now clean: `NAME + STATE + ROLE` is **185 of 185** (it was 189 of 248, 76.2%). The page population differs from the spike's (44 pages compared, not 47: pages changed in a day), so the rise from 97.61% is the removal of `visited` and the change of pages together; the `visited` misses alone were 61.

**The misses by cause**, the ten shapes at the freeze, 54 (`attribute.txt`, `misses-held-freeze-attributed.json`; the spike's classes):

| cause | now | spike |
|---|---|---|
| emulator bug, shown by a fix that already exists (agreed at head on the same page) | 35, all lazily loaded content | 34 |
| Windows-only (language names) | 6 | 6 |
| **history (`visited`)** | **0** | 61 |
| unexplained | **13** | 9 |

The 13 unexplained are 11 on `caselaw.nationalarchives.gov.uk/search?query=`, a live search page whose rows and page numbers moved between the fleet's capture and the emulator's run (a miss on a page that changed is unexplained under the rule above), 1 on `bathingwaters.sepa.org.uk` (the fleet's tree has a cookie-banner `region` before the logo, the emulator's does not) and 1 on `www.dropbox.com` (a graphic the fleet found and the emulator did not); the last two were not investigated. At head the ten shapes have 18 misses: the 6 Windows-only and 12 unexplained (`measure-held-head.txt`; the attribution above is of the freeze).

**Is the Gate passed?** On the number, yes: 98.79% is at or above 98% on a held-out half, and the browser's history, which made the first reading fail, accounts for none of the misses. On the reading this page has used (at least 98% and no unexplained miss), **no**: 13 misses are unexplained, 11 of them one page that changed.
Whether a page that moved between two captures counts against the emulator is the same call the Gate section left to the chairman; this section does not make it.

**The fleet was restored** through the same play on 12:04Z to 12:13Z, one box at a time: the play only sets values, so `SavingBrowserHistoryDisabled` was set to `0`, Edge's default (history is saved again), the play was `failed=0`, and `win_reg_stat` read `0` on all twelve boxes. The value stays in the registry, as 0, on those twelve boxes, which the role does not declare.
`fleet:status` read all twelve `ready` afterwards (`fleet-readings.txt`, before and after). `provisionRevision` was `a20963f766666de8` in all 102 records and in the first and the last probe of every box, so the setting did not move it; the split `fleet:status` reports across fifteen boxes (Edge and Windows builds, and one code hash on `a11y-worker-5`) is made of the boxes that were not used. Whether production captures should run with history off for good (declaring the value in `worker_edge_policy` and reporting it in `/diagnostics`) is a control and worker change and the chairman's call, not made here.

### Drift-free re-score: the same bytes on both sides

The 13 unexplained misses above include 11 on a live page that moved between the fleet's capture and the emulator's run, so a second comparison was made in which **nothing can move**: each page was saved once, the copy was served from `capture-host`, and **the fleet's NVDA and the emulator read that same file.** This was done for **all 102 pages**, not only those with an unexplained miss (the copying is cheap; the fleet run is the same length as the first).
`q3/remeasure/snapshot.mjs` loads the page in the emulator's own Chrome 155, as the emulator asks (Edge on Windows, the 1008x872 window), scrolls it to its end and back, and writes its DOM with the scripts, `<noscript>`, preloads and inline event handlers removed, every stylesheet inlined, every URL absolute, a link to the page's own address pointing at the copy (`index.html`, so "same page" stays "same page"), same-origin iframes written into their `srcdoc` and form values into attributes
(`q3/results/remeasure/static/static-pages.json`: 102 copies made 13:42Z to 13:47Z with the defaults `--frames srcdoc --lazy keep`; 39 of the pages have iframes). **What it does not freeze:** images, fonts and other-origin iframes are still fetched live, and shadow DOM is not serialised. Three of the copies are of sites that were down for maintenance that day (`primary-authority.beis.gov.uk`, `www.leeds.ac.uk/undergraduate`, `www.sportengland.org`), so those three are not the pages the first run read.

**On the fleet:** the same twelve boxes, with `SavingBrowserHistoryDisabled` set again through the same play, the first box alone and read back (assert task `ok`, `failed=0`, value 1, store emptied, `after` probe clean), 13:46Z to 15:00Z; `after-run` probes clean on all twelve at 15:50Z; **102 of 102 captured, none failed, 15:05Z to 15:48Z**; restored through the same play at 15:51Z to 16:01Z, `0` read back on all twelve (`q3/results/remeasure/static/`; `provisionRevision` `a20963f766666de8` in all 102 records again).
The emulator was frozen at `5fbd726` as before and read the copies from the same server on `capture-host`, two runs a page, no history; `measure.py` and `attribute.py` are unchanged, and the split is still that of the original address (`q3/remeasure/make_views.py`). 7 `visited` announcements remain on 4 pages and the emulator announces the same 7 (`static/visited-explained.json`).

| | exact / total | | pages compared | not comparable |
|---|---|---|---|---|
| **Gate figure, drift-free: held out, emulator frozen at `5fbd726`** | **4,828 of 4,977 = 97.01%** | below 98% | 57 of 60 | 2 (document titles differ in spelling: `hubspot.com`, a W3C demo), and 1 timed out (`ico.org.uk`) |
| the same, with the not-comparable pages kept in | 4,989 of 5,146 = 96.95% | | | |
| the emulator at head (not held out) | 4,828 of 4,977 = 97.01% | below | 57 of 60 | 2, and 1 timed out |
| for comparison, the live reading at the freeze (above) | 4,426 of 4,480 = 98.79% | at or above | 44 of 60 | 12, and 3 unstable, 1 timed out |

**The misses by cause**, the ten shapes at the freeze, 149 (`static/attribute.txt`, `static/misses-held-freeze-attributed.json`):

| cause | count | |
|---|---|---|
| history (`visited`) | 0 | |
| emulator bug, shown by a fix that already exists | 0 | |
| **Windows-only (language names)** | **138** | 133 on one page, `nidirect.gov.uk`, a list of its languages (132 of them in the shape `NAME + NAME + NAME + NAME + ROLE`, which is 14 of 147; the fleet says `English, Yoruba —, Yoruba (not supported), Yorùbá, link` where the emulator has `Yoruba —, yo (not supported), Yorùbá, link`); 2 + 2 on `www.gov.uk` and 1 on `ons.gov.uk` |
| **unexplained** | **11** | 10 form-field announcements on four GOV.UK Design System component pages (`accordion` 1, `checkboxes` 3, `radios` 4, `tabs` 2), 1 link on `nidirect.gov.uk` |

**The 11 unexplained.** On each of the four component pages the fleet's form-field sweep and the emulator's hold the same example frames, but not in the same order and not with the same entries: the frame headers fall at other places in the two lists, and the emulator's has one to three entries more (`static/evidence-form-field-order.json`: `checkboxes` 34 fleet entries against 36, `radios` 34 against 35, `accordion` 18 against 20, `tabs` 10 against 13).
On `checkboxes` the fleet reaches `Checkboxes with conditionally revealing content` first and `Checkbox items with error` last, where the emulator reaches the latter first; the matching is order-preserving, so a block that moved costs its fields. The frame lists, the headings and the links are identical.
Tried on that page (`static/diagnostic-checkboxes.json`, another box): the frames written as separate documents instead of `srcdoc`, and lazy loading taken off: the same five form-field differences (and two link differences once lazy loading was off), so it is neither of those.
On the live pages the two sweeps agreed on these frames. What differs is that the copy has no scripts, and GOV.UK's error-summary component is built to move focus to itself on load, which would start a sweep there; **I did not establish that this is the cause**, nor whether the fleet's NVDA or the emulator is the one that departs from NVDA's order, so these 11 stay unexplained, as the rule requires.
(Over all channels, not only the ten shapes, the 216 misses are 158 language, 55 unexplained and 3 emulator bugs already fixed; the ten shapes are the Gate's.)

**Is the Gate passed?** By the page's own reading (at least 98% and no unexplained miss), on the drift-free set: **no, on both counts**: 97.01% is below 98%, and 11 misses are unexplained. 138 of the 149 misses are the Windows-only language names, 133 of them on one page the first run could not compare; counting those as agreements, as this page did for `visited`, the figure is 4,966 of 4,977 = 99.78% (an upper bound, not the Gate's number). The Gate's number counts them as misses, and making the emulator say Windows' language names is an emulator change this ticket does not make.

**The other two misses of the live reading**, each shown by the same bytes: `www.dropbox.com` and `bathingwaters.sepa.org.uk` have **0 misses** on the copies at the freeze.
- *Dropbox*: an **emulator bug, the lazily loaded content already found in the first reading** (fixed at `529e4ec`, which the frozen emulator lacks). The frozen emulator's graphics list on the live page starts at `Security screen in Dropbox` and its census is 18 and 21 graphics in its two runs; the emulator at head lists `main landmark, Family taking a photo at a birthday party, graphic` and `Race car, graphic` first in both its runs, and the fleet's list has them there too (`static/evidence-sepa-dropbox.json`); the images load on scroll. `attribute.py` did not class it as fixed because the page is unstable between head's two runs (a different channel), not because the miss is still there.
- *sepa*: **neither an emulator bug nor Windows-only, as far as the evidence goes: a difference in the page's own state between the two live sessions.** Both live lists hold the same cookie-banner region (`This website uses cookies`) and logo; the fleet's landmark list has seven entries including `complementary landmark, Back to top, button` that the emulator's six lack, and its graphics sweep enters the banner from outside (`This website uses cookies, region, logo, graphic`) where the emulator's is already inside it (`logo, graphic`). Those are what a script-built banner and a back-to-top control do when a session differs; on the copy (no scripts) the fleet has six landmarks, the emulator six, and every channel agrees (`static/evidence-sepa-dropbox.json`). I did not trace which script. It is neither of the Gate's two classes, so it was unexplained at the first reading and the drift-free reading shows why it was not an emulator fault.

## What this page does not settle, and follow-ups

- **ADR 0047 quotes `51 tests, about 220 exact-speech assertions`** for Q2 and layer 1 as `getTree`; the checkout has 47 and 193 (227 as executed), and layer 1 is `getDesktop`. The ADR's "after #2568" wording
  is also stale. These are edits to an a11ign document, not made here.
- **The fleet's oracle has two faults a Gate would need removed**: browser history (above) and a first request that sometimes lands on the browser's own pages (Microsoft Terms, Copilot; 4 of 102, and 1
  of 4 on a control page). Both are worker-side. The Edge split on three boxes is control#116's.
- **The image-description prompt** (`To get missing image descriptions, open the context menu., Unlabelled graphic`) is in the fleet's tree and not the Linux one, and the switch that produces it was not
  isolated (Q2, Q3). It is the one Windows-side behaviour that moves a shape the Gate counts, on pages with unlabelled images.
- **Not run:** the 507-test check of the Windows mapping against Chromium's `-expected-win.txt` files; the 3 language-name tests; braille; the Ctrl+Right behaviour on a Windows Chrome.
- **The emulator's known gaps seen in the misses**: a modal dialog opened by the sweep's own activation seals NVDA's quick navigation inside it on Windows and the emulator has no tree interceptor
  for that (`gov.scot/publications`: a date picker; the dev half); the fleet's `visited` history; time-varying text.

## Reproduction

- **Build the downloads:** `EMU_DOWNLOADS=/some/dir ./setup.sh` (git, curl, python3, dpkg-deb, apt-get download; about 2.5 GB). It fetches NVDA `release-2026.1.1` (`5d92106f...`), `nvda-cldr` (`6d3ba86c...`), the
  W3C ARIA examples (`84b921a0`), the six Chromium files the tables are generated from (tag `155.0.8059.84`), Chrome for Testing 155.0.8059.84, the Chrome libraries as `.deb`s unpacked under `libs/root`,
  and Python 3.13.16 with its virtualenv. A clean build from this script, with the repository's code, runs the Q2 suite to the same 215 of 227 (*measured* 2026-10-21, `emu/results-final.txt`).
- **Q1:** `q1/run.mjs allow <out.json>` launches the browser with the extension and the allowlist switch and writes what the extension heard; the negative control is `run.mjs noallow`.
- **Q2:** `cd emu && $EMU_DOWNLOADS/q2/venv/bin/python run_cases.py` runs each in-scope test in its own process (`--one <test>` runs one; `classify.py` prints what the others need; `gen_tables.py`
  regenerates the role tables from the Chromium and NVDA sources).
- **Q3:** `q3/emulate.py <url> <out.json> [--history h.json]` is one page; `q3/run_all.py` is a directory of fleet records; `q3/measure.py` measures; `q3/attribute.py` joins two runs; `q3/fleet_capture.mjs`
  and `q3/control_capture.py` ask the fleet for a capture of an address of ours (they change nothing on a worker); `q3/firstlinks.py` and `q3/make_history.py` build the history guess.
- **The environment variables:** `EMU_DOWNLOADS` (where `setup.sh` put things), `EMU_NVDA_INI` (the settings file: `q3/nvda-fleet.ini` for Q3, the tests' own by default), `EMU_PORT`/`EMU_CDP` (per-session ports).

