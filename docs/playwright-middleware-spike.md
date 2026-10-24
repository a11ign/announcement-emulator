# Playwright middleware spike (row A11-208)

**Status: a spike, finished. Recommendation: go, conditionally (the last section); the chairman decides.**

Everything on this page is **predicted NVDA speech**: what the announcement emulator says NVDA would say. It is advisory, it is not a reading of NVDA, and it is never evidence (a11ign ADR 0047, Decision 2).
Nothing here fills an a11ign evidence field, and nothing is published: the package is private, the bundle is a workflow artifact, no registry has been written to.

**Where a number comes from is marked on the number**, as in `docs/announcement-emulator-spike.md`: *measured* (run in this row; output committed under `middleware/results/` or printed by the CI run named), *quoted* (copied, not re-run) or *not checked*.

**The questions, answered (details in the sections):**

- **Q1: yes.** One line, `defineConfig(withAnnouncements(config))`, or none: `npx announcement-emulator test`. No persistent context, no test changed. The browser is the bundle's Chrome 155 with the emulator's flags and extension.
- **Q2: yes**, with the limits listed there. Focus moves, typed characters, live regions and page loads are predicted by NVDA's own Python through layer 5, from the extension's tree and the page's own events. Content scripts cannot be used (not in Playwright's contexts); the DevTools port is.
- **Q3: yes.** `q3/sweep.py`, unchanged, at each document, route and dialog the test reaches, over a snapshot, sending no key to the test's browser.
- **Q4: yes.** Two attachments on every test in the HTML report, the three flags as annotations, everything labelled "predicted NVDA speech: advisory, not a reading of NVDA, never evidence".
- **Q5: 83.1%** (207 of 249 units) in the stable channels of six real pages, **85.7%** on the ten commonest shapes; **80.8%** over every unit. The Gate's bar is 98%, and the fleet's Edge was a milestone ahead of the emulator's Chrome. The first figure, at the freeze, was 71.4%. Not held out.
- **Q6:** about **+1.4 to +2.5 s** for a run of the 13-test sample suite and **+0.06 to +0.3 s** a test, on a plain runner. Fine on every short test; the runtime lags by minutes on a long walk of a big page.
- **Q7: yes on a plain `ubuntu-latest` runner with no container** (the sample suite passes after `npm i -D` and `npx announcement-emulator install`; 298 MB bundle). **macOS: no**, because `chrome.automation.getDesktop` never answers there. The bundle is not byte-for-byte reproducible yet (the check is in CI).
- **Recommendation: go, conditionally, as an advisory tool whose first release prints its measured rate (about 80% on this sample); the chairman decides. What a real version needs is the last section.**

## Q1. One line of setup, no test changes

**Yes. One line, and with zero lines possible.** (*measured*, local and on GitHub's `ubuntu-latest`, run 40107916510)

What the user changes, exactly:

```sh
npm i -D @playwright/test <the package>
npx announcement-emulator install        # once; downloads the pinned, checksummed runtime bundle into a cache (Q7)
```
```diff
 // playwright.config.ts
 import { defineConfig } from "@playwright/test";
+import { withAnnouncements } from "@a11ign/announcement-emulator";

-export default defineConfig({ ...your config... });
+export default defineConfig(withAnnouncements({ ...your config... }));
```

**With zero lines:** `npx announcement-emulator test [playwright test arguments]` writes a config beside the user's, which imports it and wraps it, runs `playwright test --config` on that, and removes it. The user's files are not
touched. The sample suite's CI job runs both: `playwright.config.ts` has the one line, `playwright.plain.config.ts` has none, and `check-report.mjs` finds the same attachments in both reports.

What `withAnnouncements` does: it puts a reporter first in the reporter list (a config with none keeps Playwright's default, `list`, or `dot` on CI), and for each chromium project it sets `use.launchOptions`:
the bundle's Chrome for Testing 155.0.8059.84 as `executablePath`; `--force-renderer-accessibility`, `--load-extension=<copy of the companion extension>`, `--allowlisted-extension-id=<id>`, `--disable-features=DisableLoadExtensionCommandLineSwitch`
and `--remote-debugging-port`; and `--disable-extensions` added to `ignoreDefaultArgs`. Firefox and WebKit projects are left alone.

What the routes taught (all *measured*):

- **The persistent-context launch is not needed.** The ticket's premise, "Playwright loads extensions only in its own persistent-context launch", is about Playwright's defaults, which pass `--disable-extensions`. With that flag ignored, `chromium.launch()` and
  `browser.newContext()` load the extension, and `chrome.automation.getDesktop()` in its service worker sees the pages of those off-the-record contexts (13 nodes for a ten-element page, the same tree as in a session of `emu/session.mjs`).
  So the one-line route works with a suite's `page` fixture as it is.
- **The extension is on, in headless.** Chrome 155's `--headless` (Playwright passes it when it is given an `executablePath`) is the new headless of the full browser, which loads extensions; `chrome-headless-shell` does not and is not used. No `xvfb` is needed
  on the runner (CI ran without it).
- **A content script cannot be used to read the keyboard.** An extension's content scripts do not run in off-the-record contexts (`chrome.extension.isAllowedIncognitoAccess()` is `false`; a registered content script ran in no page), and Playwright's contexts are those. So the keys, and the page's own events, are read through the browser's
  DevTools port (`--remote-debugging-port` beside Playwright's pipe, which Chrome allows together). Nothing is sent to a page but one listener.
- **A reporter can add attachments the HTML and JSON reports show**, if it is first in the list and adds them in `onEnd`: those reporters build at the end. A reporter that writes at `onTestEnd` (the blob reporter) would not show them: *not checked*.
- **Limits of the line.** `--reporter=<x>` on the command line replaces the reporters of the config, ours with them: the launch options are then not added either (they need the reporter to have published its ports), and the run is a plain Playwright run, silently, which is a defect for a real version
  (*measured*: with `--reporter=list` the browser launched was Playwright's own). The `--disable-features` flag the extension needs replaces the one Playwright passes (Chrome takes the last of two): Playwright's list (Translate, a network-time query, and others) is off no longer; *not checked* whether anything in a test depends on it.
  The fallback of one changed import (`import { test } from ".../playwright"`) was not built: the first route worked.

## Q2. Passive capture

**Yes for focus moves, typed characters, live regions, dialogs and error messages, and page loads. Each is predicted by NVDA's own Python, through layer 5 of the emulator, on a browser the emulator did not launch.**

How it is fed (the model is stated in `middleware/runtime/predict.py`'s header):

| what the test does | what reports it | what NVDA is given | predicted by |
|---|---|---|---|
| a page loads or navigates | the extension: a tree after each change (`emu/ext2/passive.js`), the root's `docLoaded` | a new buffer, and the document taking the focus | `treeInterceptor_gainFocus` for the first time (`browseMode.py:1639-1700`): the title, then the line the caret starts on |
| Tab, a click that focuses, a dialog taking focus, `.focus()` | the page's own `focusin` (DevTools port), matched to the tree's node by tag, id and name | `event_gainFocus` through the browse-mode buffer | `LiveDoc.gain_focus`, as `emu/live.py` does for a key it sent itself |
| a key typed | the page's own `keydown` | the typed character, in focus mode on an editable field | `speakTypedCharacters` (`calculateCharacterBoundaries` was missing from the stand-in for NVDA's native code and is added, `emu/standin.py`) |
| a live region changes | the page's own mutation observer | the changed text | the rules of `nvdaHelper/remote/ia2LiveRegions.cpp` (polite or assertive, not editable, not busy, `aria-relevant`, `aria-atomic`: lines 147-189 and 233-255, cited in `ext` code), spoken as `nvdaControllerInternal_reportLiveRegion` speaks (`speech.speakText`, `NVDAHelper/__init__.py:268-300`) |
| something on the focus changes | the tree | `event_stateChange` on the focus and its ancestors | `LiveDoc.settle` |

What the emulator's layer 5 needed to change, and did not: `emu/live.py` gains an optional `session` argument (the runtime passes a session that serves one snapshot and refuses every key, focus, click and scroll); `emu/ext2/bg.js` is split in two (`tree.js` is the dump code, shared with the new `passive.js`) and
behaves as before; `emu/standin.py` gains the one native function above; `emu/winuser_standin.py` read NVDA's source from a path in one machine's home and now reads it from `$EMU_DOWNLOADS` like every other module (needed by a bundle unpacked into a cache). `emu/session.mjs` is unchanged: the plan's "attach mode" is not needed, because
the runtime hosts the collector itself (Python's `http.server`) and reaches the browser through the DevTools port.

**What the prediction is, and is not.** Playwright sends its keys to Chrome over the DevTools protocol, not through NVDA. So this is NVDA's answer to the browser's events, plus the echo a user's keystrokes would get. It leaves out, and the attachment does not say anything of:

- NVDA's own handling of the keys: the browse-mode Tab override (`_tabOverride`), a key NVDA would consume, and the Escape that leaves focus mode (the fleet's probe presses Escape twice for this reason);
- `fill()` and other programmatic changes: no key is pressed, so nothing is echoed (as NVDA would not);
- the speech of say-all, of the review cursor and of any key the test did not press;
- whatever Windows adds: the emulator's known differences are those of `docs/announcement-emulator-spike.md`.

Measured facts that shaped the design:

- **The tree alone loses stops.** On the sample sign-up form a test presses Tab seven times; the extension's tree updates showed the focus on six of the seven stops (the browser batches updates; `Basket` was never in one). The page's own `focusin` has all seven. (*measured*, Chrome 155, locally.)
- **The tree alone loses the end of a test.** The tree reaches the extension some tens of milliseconds after the page changes (*measured*: 18 to 65 ms after the key in the sample runs), and a test that ends on a change closes its page first: the live region, the alert, the dialog and the error message that a test ends on were not seen until the page itself reported them. (*measured*: the same fixtures, tree only and tree plus page.)
- **The first tests of a worker begin before anything is listening.** On `ubuntu-latest` the extension's service worker was up 1.1 to 1.3 s after the first test of each worker began, and the DevTools port was attached 0.8 to 0.9 s after (*measured*, run 40107916510; on this machine, warm: 0.4 s and 0.8 s). A test that finished inside that window has no speech (the check of the sample suite names them and does not hold them to what they should have heard). A real version needs the runtime ready before the first page: it cannot be done from a config; it needs a fixture or a launch the suite goes through (Q1).
- **A browser launched again is a new session.** Playwright replaces a worker after a timeout; the new extension numbers its snapshots and its pages from zero, and the runtime had dropped them as old (found by a real page whose test hung: the later pages of the run had no speech; fixed, with a test).
- **The tree is a model of the screen, not the screen.** The `focused` flag of the tree names a later stop than the event's when a test is fast, and `off screen` is true for a stop the browser has scrolled away from by the time the tree is read; each stop is read as the browser would have had it at the move (`focused_on`). That fix came from the first agreement figure (Q5).

## Q3. Automatic sweeps

**Yes: the emulator's existing sweep, `q3/sweep.py`, unchanged, runs at each state the test reaches, with no test code, and sends no key to the test's browser.**

- **When.** A state is a document (a load), a new address in the same document (a route change, a fragment too), or a dialog. A state is swept over the last tree it had before the test moved on, or it was quiet for 1.5 s: the first tree after a load has not got the page's frames or its late content (the first figure showed it:
  the frames list was empty on every page that has any). States are deduplicated by address and a hash of the tree's roles and names, and at most 12 are swept in a run.
- **How.** Over a `LivePage` (`q3/livepage.py`) whose session serves one snapshot. Each key the sweep presses (Escape, Ctrl+End, then the quick-navigation keys of each structural type) is NVDA's own script running on the buffer; whatever it would send on to the browser (a focus, a click, a scroll, a key) is refused and counted (`notDelivered` in the attachment). The sweep begins at the bottom, as the worker's begins after its read-through, so that "previous" collects the whole page.
- **What it leaves out, against the fleet's sweep.** It does not scroll the page to load lazy content, and it does not activate a control announced `collapsed` (`disclosure_probe` presses Enter on it): both would change the page under a running test. The write-up of the Gate's sweep (`docs/announcement-emulator-spike.md`) describes both. It reads the lists of a snapshot, not the page as the fleet's NVDA walked it.
- **What it produces.** Per state: headings, landmarks, form fields, graphics, links, lists and frames, each as the list of announcements, in the attachment of the test that reached the state (`predicted-nvda-speech.json`, `sweeps`; the text attachment has the lists too).

Time: Q6.

## Q4. Output

**Two attachments on each test in Playwright's report, and the flags as annotations on the test. Every output says what it is.**

- `predicted NVDA speech` (text) and `predicted-nvda-speech.json`, on every test, in the HTML report, the JSON report and any other reporter that builds its report when the run ends. The first line of the text is `PREDICTED NVDA SPEECH: ADVISORY, NOT A READING OF NVDA, NEVER EVIDENCE (A11IGN ADR 0047, DECISION 2)`; the JSON's `label` says the same; the README of the package says it first.
  The sample suite's CI run committed under `middleware/results/ci/` shows both on every test.
- **No evidence field name.** No key anywhere in the output is `transcript`, `structure`, `interaction`, `observed`, `media`, `formInputs`, `diagnostics`, `focusOrder`, `typedFeedback` or `dialogEscape` (a unit test walks the output for them: `src/format.test.ts`; the replay test walks the runtime's records; the sample suite's `check-report.mjs` checks every report of CI).
  The sweep's lists are `lists`, and the speech is `predictedSpeech`.
- **Three flags**, with rules written in `middleware/runtime/flags.py` before any corpus page was run, each with a case that must raise it and one that must not (`test_flags.py`, 16 cases; the sample suite's pages are the positive and negative fixtures, and `check-report.mjs` holds each to its flags):

| flag | raised when | the sample suite's positive page | its negative |
|---|---|---|---|
| `focus-without-name` | focus lands on a control (button, link, field, tab, ...) with no accessible name, and what is predicted for it has no name in it (no `NAME` token by `q3/shapes.py`) | an icon-only button | the same icon with an `aria-label` |
| `silent-dialog` | a dialog opened (the page reports it open and visible) and no focus move into it and no live-region speech was predicted from 20 ms before to 1000 ms after | a `role=dialog` panel that appears without taking the focus | a modal `<dialog>` whose button takes the focus |
| `unheard-error` | a field has `aria-invalid` and an error message (its `aria-errormessage`, or its `aria-describedby`) with text, and every word of the text is missing from the speech predicted from 20 ms before to 1000 ms after | the message appears and nothing moves the focus; and the focus moves to the field (the prediction says `invalid entry`, not the message: the emulator's buffer has the message, the focus announcement does not) | the message is in a `role=alert` |

The second positive of `unheard-error` is a finding about the emulator and not about NVDA: whether NVDA 2026.1.1 says the message of `aria-errormessage` when the field takes the focus is something only a fleet capture of that page can say, and none was taken (the fleet is frozen, and the probes do not reach it): *not checked*.

## Q5. Agreement with the fleet

**Measured on six real pages, against `a11y-worker-14` and `-16`, by announcement shape. The passive predictions agree with a real NVDA on 83.1% of the units (207 of 249) in the channels that were stable, and on 85.7% of the ten commonest shapes (132 of 154). That is far below the Gate's 98%, and the figure says what it is made of.**
(*measured* 2026-10-24; tables and every miss in `middleware/results/agreement/figure-4/`; the rule, the pages and the freeze in `rule.md`, `pages.json`, `freeze.json`.)

**How.** The sample suite's `corpus` project opens each page and does, as plain Playwright, what the fleet's three focus probes do (open, Tab until the last three stops equal the first three, Escape twice, type `123456` into the first text field; the table is in `rule.md`). The same page was captured twice on the fleet through A11-166's route
(`q3/fleet_capture.mjs --typing-dialog`, nothing on any box changed) and read twice by the middleware, close in time. The pages were chosen by a rule committed before any capture: the Gate's 60 `old60` pages less its seven not comparable, ordered by the SHA-256 of the address, the first six whose DOM has ten tab stops and a text field.
`freeze.json` names the git objects of the runtime, the extension, the sweep, the test, the pages and the measure before the first capture; `make_freeze.py check --head ca8145ad47 --fleet <dir>` passes (nothing moved, every capture is after the freeze). **These pages are not held out:** the emulator was fitted against them while A11-155 to A11-176 were done.

**What the fleet can be asked, and what is compared.** The fleet cannot be asked what the keys themselves made NVDA say: its probe presses Tab and then asks NVDA to repeat the focus (NVDA+Tab) and records that. So a stop is compared by what NVDA says when asked to repeat the focus on the node the page's `focusin` names (`repeatFocus`, recorded when
`ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1`). The speech the middleware attaches to the test is what the focus event says, a different string: **the figure is the agreement of the emulator's reading of the tree at the stops, not of the attached speech.** The channels: `title`, `stops`, `field` (the first text field when it has the focus), `typed` (the echo of the six digits), and the seven lists of the fleet's structure sweep against the first sweep the middleware ran
(headings, landmarks, form fields, graphics, links, lists, frames). A unit is *agreed* when it is in the longest order-preserving matching of the two lists by exact equality (`q3/measure.py`'s rule). The shape is `q3/shapes.py`'s shape of the fleet's string.

**Three honesty notes that bound the figure:**

1. **The oracle's Edge is one milestone ahead of the emulator's Chrome.** The three Edge-155 boxes took an update to 156.0.4314.42 between the rule and the captures (`boxes.md`); both boxes used say so in every capture. The Gate's oracle was the same milestone as the emulator.
2. **The pages differ between the readings.** The two captures of a page, on the two boxes, differ in some channel on five of the six pages, and the stable-channels table leaves those channels out. Over every stop unit they agree with each other on 95.2% (the fleet against itself, in the second table), which is the ceiling a page's own movement leaves; the two passive runs agree with each other on 95.2% too (on 100.0% in the stable channels).
3. **Two of the figure's corrections were made after the first reading of it (so it is not held out).** The first figure, taken at the freeze (`figure-1/`), was **71.4%** (142 of 199) over every channel and **76.2%** of the ten commonest shapes (99 of 130), with five of six pages comparable and the stop channel unstable on all but one. Its misses showed four faults of the middleware, each fixed with a test: a stop was read with the tree's `focused` flag on a later stop, and `off screen` for a stop the browser had scrolled away from
   (NVDA's `repeat focus` lacked "focused" on most stops); a state was swept over its first loaded tree, which has no frames; a browser launched again was dropped as old (after a test that hung on a cookie dialog); and a page of thousands of nodes posted megabytes for each change and was closed before its tree arrived (two of the six pages had no reading).

**The table** (the passive predictions against the fleet / the fleet against itself / the passive runs against each other; stable channels; page by page, six of six):

**By channel:**

| | the passive predictions | the fleet against itself | the passive runs against each other |
|---|---|---|---|
| title | 3 / 3 100.0% | 3 / 3 100.0% | 3 / 3 100.0% |
| stops | 31 / 37 83.8% | 37 / 37 100.0% | 33 / 33 100.0% |
| field | 0 / 2 0.0% | 2 / 2 100.0% | 4 / 4 100.0% |
| typed | 12 / 18 66.7% | 18 / 18 100.0% | 30 / 30 100.0% |
| headings | 11 / 11 100.0% | 11 / 11 100.0% | 11 / 11 100.0% |
| landmarks | 24 / 24 100.0% | 24 / 24 100.0% | 24 / 24 100.0% |
| formFields | 12 / 22 54.5% | 22 / 22 100.0% | 18 / 18 100.0% |
| graphics | 3 / 7 42.9% | 7 / 7 100.0% | 5 / 5 100.0% |
| links | 67 / 74 90.5% | 74 / 74 100.0% | 69 / 69 100.0% |
| lists | 27 / 30 90.0% | 30 / 30 100.0% | 29 / 29 100.0% |
| frames | 17 / 21 81.0% | 21 / 21 100.0% | 20 / 20 100.0% |

**By shape (the ten commonest of the fleet's units):**

| | the passive predictions | the fleet against itself | the passive runs against each other |
|---|---|---|---|
| NAME + ROLE | 49 / 57 86.0% | 57 / 57 100.0% | 54 / 54 100.0% |
| NAME | 15 / 22 68.2% | 22 / 22 100.0% | 33 / 33 100.0% |
| NAME + ROLE + STATE + STATE | 14 / 18 77.8% | 18 / 18 100.0% | 16 / 16 100.0% |
| ROLE + COUNT + NAME | 11 / 11 100.0% | 11 / 11 100.0% | 11 / 11 100.0% |
| NAME + ROLE + STATE | 10 / 10 100.0% | 10 / 10 100.0% | 10 / 10 100.0% |
| NAME + ROLE + ROLE + COUNT + NAME + ROLE | 8 / 10 80.0% | 10 / 10 100.0% | 9 / 9 100.0% |
| NAME + ROLE + STATE + NAME + ROLE + NAME + ROLE + NAME | 10 / 10 100.0% | 10 / 10 100.0% | 10 / 10 100.0% |
| NAME + STATE + ROLE | 6 / 6 100.0% | 6 / 6 100.0% | 6 / 6 100.0% |
| ROLE + NAME + ROLE + ROLE | 4 / 5 80.0% | 5 / 5 100.0% | 5 / 5 100.0% |
| NAME + ROLE + LEVEL | 5 / 5 100.0% | 5 / 5 100.0% | 5 / 5 100.0% |

Over every channel, comparing the first fleet capture against the first passive run whether or not the channel was stable (`figure-4/`, second block): **914 of 1,131 = 80.8%**, ten commonest shapes 79.7%; stops **290 of 393 = 73.8%** (the fleet against itself 95.2%). With the census rule as frozen (a heading or link count that differs by one excludes the page: three pages left) it is **165 of 201 = 82.1%** (`figure-5/`).

**Where the misses are** (`figure-4/misses.json` has each with both strings): of 42 in the stable channels, **30 have no counterpart** and 12 are unexplained.

- *Four stops on the Companies House page have no counterpart*: the page's links named by an extra `(link opens a new window)`, which the page script's candidate names cannot match to the tree's node (`unresolvedFocus`: 6 of 131 focus events on the run's busiest runtime). A real version matches by DOM node and not by name.
- *The TfL page is the largest source (29 of 42).* It opens a modal cookie dialog. The test's click on the first text field is blocked by it (the test passes the walk and times out in the click after 180 s: the typed channel, 6 units, is empty), the fleet's NVDA moved the focus to the field regardless; and the tree's last state of the load is the dialog alone (a modal hides the rest from the tree), so the sweep's lists are the dialog's.
- *The "same page" state of a link* (two stops): Chrome tells a link to the page's own address "same page"; the tree the middleware read had it for some and not others.
- *Frames*: the list is the fleet's quick-navigation to frames; four are missing on two pages.
- Not at all in the misses of the stable channels: `visited` (the fleet's history has not got these pages as the Gate's did), the language names, the image-description prompt.

## Q6. Cost

**The middleware adds a start-up of about a second and a half, a tenth to a third of a second to each short test, and, for a test that walks a long page, a lag of seconds to minutes in the runtime that costs the test nothing but the wait at the end of the run. It is acceptable to run on every test of a suite of short tests; it is not for a suite whose tests walk pages of thousands of nodes, and what would make it cheaper is known.**

*Measured* on `ubuntu-latest` in the run that named the freeze (run 40107916510; the sample suite's `fixtures` project, 13 tests of about 0.3 s, three runs for each cell, medians; `middleware/results/ci/linux-x64/cost.log`), against the same suite in the same Chrome with no extension, no flags and no runtime (`playwright.baseline.config.ts`):

| workers | without | with | with, no sweeps | added | of it, the sweeps |
|---|---|---|---|---|---|
| 1 | 5.47 s | 7.96 s | 6.90 s | +2.50 s | +1.07 s |
| 2 | 5.21 s | 7.34 s | 7.10 s | +2.13 s | +0.24 s |
| 4 | 6.01 s | 8.50 s | 8.13 s | +2.49 s | +0.37 s |

An earlier run on another runner (run 40105447525), same code: 3.95 s to 5.63 s (+1.69 s), 3.76 s to 5.33 s (+1.57 s), 3.85 s to 5.63 s (+1.78 s). On this machine, warm: +0.9 s, +1.0 s, +1.6 s. A runner is slower and noisier by a factor of two between runs; the added time is two to three seconds on it and one to one and a half on a quiet machine.

- **At start-up:** the runtime is ready 0.1 to 0.3 s after it is spawned warm, and 0.2 to 1.2 s on a runner (`bootMs` in `run.json`; NVDA's boot is not the cost: 240 ms). It is started before the workers and is on nobody's critical path. What costs is that **nothing listens for the first second:** the extension's service worker was up 1.1 to 1.3 s after the first test of a worker began on the runner (0.4 s warm), and the DevTools port 0.8 to 0.9 s after; a test that finished inside that window has no speech (Q2).
  The end of the run waits for the runtimes: 0.25 s at least (`drainMs`).
- **Per test:** the sum of the tests' own durations rose by 64 to 126 ms a test (1 worker), 139 to 175 ms (2) and 232 to 297 ms (4): the browser runs with accessibility on, the extension reads the tree, and on a two-core runner four workers compete with four runtimes. The "no sweeps" row is that without the sweeps.
- **Per sweep:** the runtime's time for a state of the fixtures' pages is 15 to 137 ms (median 60 to 97 ms, 231 ms with four workers competing); on the real pages of Q5, 0.2 s to 5.6 s (the GOV.UK tabs page, about 900 nodes with frames). Sweeps run in the runtime's idle time, during the test, and only at the end of a state.
- **Per focus event:** NVDA's work for a stop is 100 to 170 ms on a real page (`speechMs` of the runtime that took the 85 stops of the GOV.UK tabs page: 14 s), because the emulator rebuilds the buffer from the whole tree for each event. The test does not wait for it; the end of the run does: the `drainMs` of the real-page runs is 0.25 s (the runtimes had kept up), but the run of three long walks waited 10.9 s and 25 s at the end.
- **The extension:** reading a node's fields costs 0.65 ms the first time (*measured*: 190 ms for 282 nodes, 400 ms for 668), so the first tree of a 2,700-node page takes about 2 s; later trees cost a tenth of it, because only nodes that changed and their ancestors are read again. Each tree is posted whole: megabytes for each change on that page. Beyond a few thousand nodes the test is over before the first tree arrives, which is why one tree waits at a time.

**What would make it cheaper:** (1) an incremental buffer in the emulator, so that a stop costs milliseconds and not a rebuild; (2) trees posted as differences, with the fields the emulator reads and not every field; (3) the runtime and the extension ready before the first page (a fixture the suite goes through, not a config, or a launch wrapper that waits); (4) a smaller bundle (the Python is 278 MB unpacked of 838 MB: python-build-standalone's `install_only_stripped` and without the test suite and the static library); (5) sweeps on a coarser trigger than every state.

## Q7. Packaging, the Playwright way

**Yes, the Playwright way, with no Docker, on a plain `ubuntu-latest` runner. A probe on macOS: it does not work, and the reason is Chromium's, not ours.**

What the user does (the CI job `demo` does exactly this, run 40107916510, `.github/workflows/middleware-spike.yml`):

```sh
npm i -D @playwright/test <the package's tarball>      # npm pack, in this spike; npm i -D <name> when there is a registry
npx announcement-emulator install                        # fetch, check, unpack: 6 s on the runner, from a server on the runner itself
npx playwright test                                      # with the one line
```

- **The package** (`middleware/`, TypeScript, built with Rslib, tested with rstest, `private`, `UNLICENSED`): `withAnnouncements`, the reporter, `install`, `test`, `doctor`. It carries `pins.json`: for each platform, the bundle's file name, size and **sha256**. `install` downloads from `$ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST`
  (there is none: nothing is published), refuses the file unless its sha256 is the pinned one (a unit test: a file one byte longer is refused and nothing is unpacked), and unpacks it into `~/.cache/announcement-emulator/<version>-<platform>` (`ANNOUNCEMENT_EMULATOR_PATH` moves it, as `PLAYWRIGHT_BROWSERS_PATH` moves Playwright's).
- **The bundle**, one for each platform, built by `middleware/bundle/build.sh` from `pins.env` (the one file of revisions that `setup.sh` reads too): NVDA's source at `release-2026.1.1` (`5d92106f`, the part that runs, the spy synthesizer, and the three C++ files the live-region rules are read from), the CLDR names and the `nvda-appdir` overlay (copies, no links), the seven Chromium
  source files the tables are read from, Chrome for Testing 155.0.8059.84 (and, on Linux, the `.deb` libraries it needs, unpacked without root), python-build-standalone 3.13.16 (release `20261013`, refused unless its sha256 is the pinned one) with the emulator's packages installed straight into it (no virtualenv, so no absolute path),
  the emulator, the companion extension and the runtime. It holds neither the replay proxy (`mitmproxy`) nor `aria-practices`. *Measured:* linux-x64 298 MB as `tar.gz` (838 MB unpacked: Chrome 400 MB, Python 278 MB, NVDA's source 76 MB and its overlay 73 MB, the libraries 11 MB, the rest under 2 MB each), built in 116 s on the runner; darwin-arm64 242 MB, built in 83 s (run 40107916510). `install` took 6 s on the runner, from a server on the runner.
- **The runtime is a separate process**: this package starts it with the bundle's Python and reads its JSON lines, and never imports it (ADR 0047, Decision 3; the package's `files` hold none of the runtime, and no TypeScript file names a Python module).
- **Built in this repository's CI**, one job for each platform. TBD
- **On a plain runner, no container.** The jobs run on `ubuntu-latest` and `macos-latest` with no `container:`; nothing is installed on the runner (`apt-get download` only downloads). Playwright's own browsers are not installed: the tests ran in the bundle's Chrome. The bundle travels between jobs as a workflow artifact and is served to `install` from a static server on the runner (`python3 -m http.server`), so that the download, the checksum and the unpack are the real ones; a released version needs a host.
- **macOS, one probe, no promise.** The bundle builds (83 s) and installs (3 s), the tests run in its Chrome for Testing 155 (they pass), and the runtime starts. But the extension's `getDesktop` callback is never called: `chrome.automation` is an object in the service worker, and the desktop tree it would read is what the browser's Views toolkit exposes, which Chrome on macOS (Cocoa) does not.
  So no tree arrives (`snapshots: 0`, `extensionUpAfterFirstTestStartedMs: null` in `run.json`) and nothing is predicted. The page-side events (focus, keys, live regions) do arrive, but there is nothing to match the focus to or to build a buffer from. A macOS version would need another source of the tree (`Accessibility.getFullAXTree` over the DevTools port, which has fewer fields: ADR 0047's layer 1 says which), and is not attempted.
- **A container image** is not worth offering as well, for now: the bundle runs on any glibc Linux without one, a container adds a second thing to keep in step with the pins, and the only user it would serve is one whose CI cannot reach a bundle host. If a real version has such users, an image is the bundle plus a base: a dozen lines.

## What a real version needs, and the recommendation

**Go for building it properly, as an advisory tool with its measured rate printed first, if the chairman wants the product; the spike answers "can it be done the Playwright way" with yes and "how well" with "about four in five stops and lists, on a small sample, on one platform".** The decision is the chairman's.

For the go:

- The shape works end to end on a plain runner: one line (or none), a pinned and checksummed bundle fetched the way `playwright install` fetches a browser, a separate process that the package never imports, a report that carries the speech, the sweeps and the flags, and every output saying it is a prediction.
- Nothing about it needs a person to write a test twice, and it did not fail one test of the sample suite (a runtime that cannot start leaves the tests as they were).
- The cost on short tests is acceptable and its causes are known.

Against going as it stands:

- **The agreement is 83.1% and the Gate's bar is 98%.** Part of it is the oracle (an Edge milestone ahead, pages that move between readings: the fleet against itself is 95.2% on the stops) and part is the middleware's own faults, of which the measurement found five in a morning. ADR 0047 Decision 6 says a published package states its measured rate; on this evidence the honest sentence is "about 80% on six pages, not held out".
- **It sees nothing in the first second of a worker, and loses a page that is closed before its tree arrives.** A test that is short and quick is the one it misses.
- **It does not work on macOS and was not tried on Windows**; Chrome's tree through `chrome.automation.getDesktop` is a Linux, Windows and ChromeOS thing.

What a real version needs:

1. **A bundle host and a release pipeline** (the bundle is 298 MB; a registry-like store, a checksum in the package, retention), and the **bundle made byte-for-byte reproducible** (not byte-for-byte reproducible yet (the check is in CI)). Trim it: python-build-standalone's stripped build, the browser's unused locales.
2. **The package's name** (not "NVDA" in it: ADR 0047), the **NV Access question** (ceo's to send before the first public release), the **npm package's licence** (the runtime is GPL-3.0; the package is `UNLICENSED` here), and the **measured agreement rate** printed in its README (Decision 6), on a larger sample than six pages, from boxes on the same Edge milestone as the Chrome.
3. **The runtime and the extension ready before the first page.** A fixture the suite goes through, or a launch that waits, instead of a config that cannot; and a way to carry on when the user passes `--reporter` (the launch options must not depend on the reporter).
4. **Trees as differences and an incremental buffer.** Today each change posts the whole tree (megabytes on a 2,700-node page) and each stop rebuilds NVDA's buffer (100 to 170 ms); a test that walks a big page is the one that cannot be afforded.
5. **Matching a page's focus to the tree by DOM node** (`DOM.getNode` and the AX node's backend id over the DevTools port), not by tag and name: 6 of 131 stops of the busiest run could not be matched.
6. **A tree source for macOS** (or an honest "Linux and Windows only"), and the live-region and dialog rules checked against NVDA on the fleet with pages written for the purpose (the fixtures' pages are ready for it: `middleware/sample-suite/pages/`).
7. **Decide what the attached speech is.** Today it is what NVDA's focus event says; the fleet can only be asked what NVDA says when asked to repeat the focus. A guidepup-style API for writing screen-reader tests (the ticket: later, if at all) would put the fleet's own probes in a test; this spike's `repeatFocus` is the seed of it.

## Decisions made without a person

The plan was written by an unattended planning run, not agreed with a person. Each decision it made without a person, and each this run made where the plan could not be followed, for a reviewer to check against the code. (The same list is in the pull request.)

**From the plan, followed:**

- Packaging is the npm package plus a downloaded runtime bundle, with no Docker, and a container gets one paragraph (Q7). Evidence: Q7 and the Acceptance of the ticket.
- Attach order: zero lines, then one config line, then one import; the first that works answers Q1 (both of the first two work; the import was not built).
- The launch adds `--disable-features=DisableLoadExtensionCommandLineSwitch` and drops Playwright's `--disable-extensions` (`middleware/src/config.ts`, `extension.ts`).
- Sweeps run read-only on a snapshot (`SnapshotSession` refuses every key; `q3/sweep.py` and `q3/livepage.py` are unchanged).
- The corpus test repeats the fleet's probes as plain Playwright calls (`middleware/sample-suite/tests/corpus/corpus.spec.ts`, table in `middleware/results/agreement/rule.md`).
- `q3/fleet_capture.mjs` gains an opt-in `--typing-dialog` (`q3/test_fleet_capture.py`: the body without it is the old one, with it two more probes).
- Six corpus pages by a rule committed before any capture (`middleware/results/agreement/rule.md`, `pages.json`); the runtime frozen and named before the first capture (`freeze.json`, `agreement/make_freeze.py check`).
- The bundle travels as a workflow artifact and is served locally in CI; `linux-x64` and `darwin-arm64` only; python-build-standalone 3.13.16 with the packages installed straight into it (no virtualenv); no `mitmproxy`, no `aria-practices`.
- Pins move into `pins.env`, read by `setup.sh` and by the bundle build (`middleware/bundle/test_bundle.py`).
- The package is `@a11ign/announcement-emulator`, `private`, bin `announcement-emulator`, `no-release:`.
- The output is labelled "predicted NVDA speech", with a guard that no field is named for an evidence field.
- The three flags' rules are fixed, each with a positive and a negative fixture, before any corpus run.
- The write-up is a new `docs/playwright-middleware-spike.md`.
- The toolchain is TypeScript, `tsc`, rstest through `@a11ign/toolchain`, Rslib.

**Where the plan could not be followed, and what was done instead (each a technical decision, with its evidence above):**

- *Keys and focus are read through the DevTools port, not a content script.* Content scripts do not run in the off-the-record contexts Playwright makes (Q1).
- *`emu/session.mjs` has no attach mode.* The runtime hosts the collector itself; `emu/session.mjs` is unchanged. `emu/live.py` still gains its `session` seam.
- *Live regions, dialogs and error messages are reported by the page, not read as differences between two trees,* because the tree arrives after the page is gone when a test ends on the change (Q2). The rules are still `ia2LiveRegions.cpp`'s, applied to the DOM instead of to WinEvents.
- *Each focus move is the page's `focusin`, matched to a node of the tree,* because the browser batches tree updates (Q2). Where no page script is attached the runtime falls back to the tree's focus.
- *The extension is two files and not one.* `emu/ext2/tree.js` holds the dump code shared by `bg.js` and the new `passive.js`; `bg.js` behaves as before (the Q2 suite was not re-run: *not checked*; the replay and sweep tests of this row do not use `bg.js`, and the unchanged `emu/session.mjs` still loads it).
- *Two emulator stand-ins changed for reasons the plan did not foresee:* `calculateCharacterBoundaries` was missing (typed characters), and `emu/winuser_standin.py` read NVDA's source from one machine's home directory.
- *The boxes are `a11y-worker-14` and `-16`, on Edge 156,* not three boxes on Edge 155: the fleet moved under the rule (`middleware/results/agreement/boxes.md`).
- *Three corrections were made after the first figure was taken at the freeze, and are labelled "not held out" where they matter:* a stop is read with the focus on it (`focused_on`), a state is swept over its last tree, and a browser launched again is heard as the first was; then the extension keeps one tree waiting for a page and forgets a closed page. The first figure is kept (`middleware/results/agreement/figure-1/`), and `make_freeze.py check --head <freeze commit>` passes at the freeze commit.
- *The cost is measured on the sample suite's fixtures project, in the CI run, three times for each setting.* The corpus walks are timed from the runtime's own counts.

## Reproduction

Everything below is run from the repository root. `$EMU_DOWNLOADS` is `setup.sh`'s directory (or a bundle) for the tests that need NVDA.

```sh
# the package: lint, types, tests
( cd middleware && pnpm install --frozen-lockfile && pnpm run lint && pnpm run typecheck && pnpm test )
# the Python: pure, replayed over recorded sessions of the sample suite, the bundle's inputs, the agreement measure
python3 -m unittest discover -s middleware/runtime -t middleware/runtime
python3 -m unittest discover -s middleware/bundle -t middleware/bundle
python3 -m unittest discover -s middleware/agreement -t middleware/agreement
python3 -m unittest discover -s q3 -t q3 -p test_fleet_capture.py

# the bundle, and the sample suite on a plain runner: .github/workflows/middleware-spike.yml (jobs bundle and demo); locally
middleware/bundle/build.sh linux-x64 /tmp/bundle                       # about 2 minutes, 300 MB
node middleware/bundle/write-pins.mjs 0.0.0-spike.0 /tmp/bundle/pin-linux-x64.json > middleware/pins.json
( cd middleware && pnpm run build && npm pack )                        # then, in a project with @playwright/test: npm i -D the tarball; npx announcement-emulator install
cp -R middleware/sample-suite /tmp/project && cd /tmp/project && npx playwright test --project=fixtures && node check-report.mjs

# the agreement (the fleet's records are third-party pages and are not committed; the tables and each miss are)
python3 middleware/agreement/select_pages.py <chrome> middleware/results/agreement/pages.json     # the rule's page list
python3 middleware/agreement/make_freeze.py name middleware/results/agreement/freeze.json          # BEFORE any capture
python3 middleware/agreement/capture_fleet.py middleware/results/agreement/pages.json <dir> --workers a11y-worker-14=http://<host>:8765,...
( cd middleware/sample-suite && ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1 npx playwright test --project=corpus )   # twice; keep test-results/report.json of each
python3 middleware/agreement/measure.py --fleet <dir> --passive <report 1> <report 2> --pages middleware/results/agreement/pages.json [--include-unstable --tolerate-census]
python3 middleware/agreement/make_freeze.py check middleware/results/agreement/freeze.json --head <the freeze commit> --fleet <dir>
```
