# Playwright middleware spike (row A11-208)

> **Named for what it was when it was written.** The package this page calls `@a11ign/announcement-emulator` (command `announcement-emulator`) has been `@a11ign/foresay` (command `foresay`) since A11-353; see `docs/release-decisions.md`, "Decisions". The commands below are the record of what was run, and are not copied as they stand.

**Status: a spike, finished. Recommendation: go, conditionally (the last section); the chairman decides.**

Everything on this page is **predicted NVDA speech**: what the announcement emulator says NVDA would say. It is advisory, it is not a reading of NVDA, and it is never evidence (a11ign ADR 0047, Decision 2).
Nothing here fills an a11ign evidence field, and nothing is published: the package is private, the bundle is a workflow artifact, no registry has been written to.

**Where a number comes from is marked on the number**, as in `docs/announcement-emulator-spike.md`: *measured* (run in this row; output committed under `middleware/results/` or printed by the CI run named), *quoted* (copied, not re-run) or *not checked*.

**The tree has one source now (A11-229, step 3).** The chairman decided on 2026-10-25 that the DevTools port is the only tree source: the companion extension is removed from the middleware and from the bundle, there is no automatic pick, no
`tree` option and no fallback, and the middleware runs in whichever browser a launch gives (Playwright's headless shell included, with no `channel` added). This document is the spike's record: where a sentence below says the extension is the default on Linux and
Windows, that macOS gets the DevTools port as a fallback, or that the browser is the bundle's Chrome, it says what the spike did, and it is marked where it is overtaken. A setting of `ANNOUNCEMENT_EMULATOR_TREE` is ignored with one printed line. The extension's own
files that the spike emulator uses (`emu/ext2/bg.js`, `tree.js`, `manifest.json`, `q1/`) stay; its recordings stay as the test data the DevTools conversion is held to (`middleware/runtime/fixtures/structure/`). The measured figure of the DevTools tree alone, under a rule frozen
before its captures, is this ticket's last step.

**The questions, answered (details in the sections):**

- **Q1: yes.** One line, `defineConfig(withAnnouncements(config))`, or none: `npx announcement-emulator test`. No persistent context, no test changed. At the spike the browser was the bundle's Chrome 155 with the emulator's flags and extension; it is now the team's own Playwright Chromium with the two flags and no extension (A11-230, A11-229).
- **Q2: yes**, with the limits listed there. Focus moves, typed characters, live regions and page loads are predicted by NVDA's own Python through layer 5, from the tree and the page's own events. At the spike the tree came from the companion extension (Linux, Windows) or, where the browser gives the extension none (macOS), through the DevTools port, at lower fidelity; it comes through the DevTools port on every platform now (A11-229). Content scripts cannot be used (not in Playwright's contexts); the DevTools port is.
- **Q3: yes.** `q3/sweep.py`, unchanged, at each document, route and dialog the test reaches, over a snapshot, sending no key to the test's browser.
- **Q4: yes.** Two attachments on every test in the HTML report, the three flags as annotations, everything labelled "predicted NVDA speech: advisory, not a reading of NVDA, never evidence".
- **Q5: 83.1%** (207 of 249 units) in the stable channels of six real pages, **85.7%** on the ten commonest shapes; **80.8%** over every unit. The Gate's bar is 98%, and the fleet's Edge was a milestone ahead of the emulator's Chrome. The first figure, at the freeze, was 71.4%. Not held out. With the tree read through the DevTools port instead of by the extension, on the same day and the same fleet captures: **80.4%** over the same 1,131 units (the extension's: 81.4%).
- **Q6:** about **+1.3 to +2.0 s** for a run of the 13-test sample suite and **+0.07 to +0.24 s** a test, on a plain runner. Fine on every short test; the runtime lags by minutes on a long walk of a big page.
- **Q7: yes on a plain `ubuntu-latest` runner with no container** (the sample suite passes after `npm i -D` and `npx announcement-emulator install`; 298 MB bundle). **macOS: the extension's source produced 0 predictions** (`chrome.automation.getDesktop` answers "getDesktop is unsupported by this platform" there, and `chrome.automation.getTree` is not in Chrome 155's API at all), **and the DevTools source, which macOS took by default (every platform takes it now, A11-229), predicts: all 13 tests of the sample suite had their page load predicted, 17 sweeps and the 4 flags** (CI run 40125495459). The bundle is built twice on the linux-x64 runner, byte for byte the same (sha256 96ea8aaae874a1d8…; not checked on macOS or on two runners).
- **The tree sources, measured against the fleet (A11-229): the extension buys 0.7 points over the DevTools port on Linux (82.1% against 81.4% of 1,138 units, inside the frozen 1.0-point margin), so the recommendation by the rule is to drop it; DevTools on macOS 83.6% of 1,026. The chairman reads it** (the section after Q7).
- **The structure safeguard (A11-229, step 2): on table- and list-heavy pages the frozen gate says STOP AND REPORT (the extension leads by +1.8 points on the table pages, 6 units from 342), while DevTools leads by 4.9 points over all the units both read and the extension read 6 of 8 pages; the fields behind the table lead are `clickable`, a typed value and a link's description words. The chairman reads it** (the section after the tree sources).
- **Recommendation: go, conditionally, as an advisory tool whose first release prints its measured rate (about 80% on this sample); the chairman decides. What a real version needs is the last section.**

## Q1. One line of setup, no test changes

**Yes. One line, and with zero lines possible.** (*measured*, local and on GitHub's `ubuntu-latest`, run 40125495459)

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

What `withAnnouncements` did at the spike (now: the same reporter, and the launch options are the two flags `--force-renderer-accessibility` and `--remote-debugging-port` and nothing else, in the browser the config launches): it puts a reporter first in the reporter list (a config with none keeps Playwright's default, `list`, or `dot` on CI), and for each chromium project it sets `use.launchOptions`:
the bundle's Chrome for Testing 155.0.8059.84 as `executablePath`; `--force-renderer-accessibility`, `--load-extension=<copy of the companion extension>`, `--allowlisted-extension-id=<id>`, `--disable-features=DisableLoadExtensionCommandLineSwitch`
and `--remote-debugging-port`; and `--disable-extensions` added to `ignoreDefaultArgs`. Firefox and WebKit projects are left alone.

What the routes taught (all *measured*, with the extension, at the spike):

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
- **The first tests of a worker begin before anything is listening.** On `ubuntu-latest` the extension's service worker was up 0.4 to 1.5 s after the first test of each worker began (the more workers start together, the later: 0.4 s with one, 0.5 to 0.7 s with two, 0.9 to 1.4 s with four), and the DevTools port was attached 0.2 to 1.0 s after (*measured*, run 40125495459, `middleware/results/ci/linux-x64/cost.json`; on this machine, warm: 0.4 s and 0.8 s). A test that finished inside that window has no speech (the check of the sample suite names them and does not hold them to what they should have heard). A real version needs the runtime ready before the first page: it cannot be done from a config; it needs a fixture or a launch the suite goes through (Q1).
- **A browser launched again is a new session.** Playwright replaces a worker after a timeout; the new extension numbers its snapshots and its pages from zero, and the runtime had dropped them as old (found by a real page whose test hung: the later pages of the run had no speech; fixed, with a test).
- **The tree is a model of the screen, not the screen.** The `focused` flag of the tree names a later stop than the event's when a test is fast, and `off screen` is true for a stop the browser has scrolled away from by the time the tree is read; each stop is read as the browser would have had it at the move (`focused_on`). That fix came from the first agreement figure (Q5).

### The tree through the DevTools port (macOS at the spike; every platform since A11-229, step 3)

**Why.** On macOS the extension reads no tree: `chrome.automation.getDesktop` calls back with nothing and `chrome.runtime.lastError` says "getDesktop is unsupported by this platform" (*measured*, CI run 40125495459, `middleware/results/ci/darwin-arm64/probe-tree.log`); the desktop tree is built by Chromium's Aura/Views toolkit and macOS's browser UI is not one. The first thing tried instead was the per-tab tree the chairman named, `chrome.automation.getTree(tabId)`: **it is not in Chrome 155's API** on either platform (`typeof chrome.automation.getTree` is `undefined` on `ubuntu-latest` and on `macos-latest`; the API's keys are listed in the same log), so it cannot be used. The second is ADR 0047's fallback, `Accessibility.getFullAXTree`.

**How.** `middleware/runtime/axtree.py` reads the renderer's accessibility tree and the page's DOM through the DevTools port the runtime is already attached to (`Accessibility.getFullAXTree`, `DOMSnapshot.captureSnapshot`, the frames' trees, the viewport and the page's state: one round trip) and makes the node list that `emu/ext2/tree.js` makes from `chrome.automation`, so that the predictor and the emulator under it do not know which they were given. `middleware/runtime/cdp.py` reads again when the page says something changed (the same listener that reports keys and focus now also notes mutations, input, loads and route changes). A page is held until the listener is in (`waitForDebuggerOnStart`), so that a quick test still has its first tree read. macOS takes this source by default; the extension is not loaded then. Every output says where its tree came from (`treeSource` in the JSON, a line in the text) and that it is of lower fidelity.

**What is exact and what is not.** The roles are exact: `chromeRole` is Chromium's own number (`roles.json` names it, from `ax_enums.mojom` at the pinned tag). The names, values, states, levels, `checked`, `invalid`, the relations that are nodes (labelled by, details), the live-region properties and the frames are the AX tree's own. What the protocol does not say is worked out, and is where the fidelity goes (each marked *NOT PORTED* or *RECONSTRUCTED* in `axtree.py`): word and sentence starts by a pattern and not by ICU's rules; a text's line starts from its inline text boxes; the position in a set, the size of one and the table indexes counted from the tree and not read from Chromium; `default` (the form's first submit button) and `linked` (a link and its text) by rule; `offscreen` from the box and the viewport; the font from the computed style (the extension reports the font that was used, `DejaVu Sans`, where the style says `Times New Roman`); `visited` and the document's text selection not at all; the iframes of another site (their own browser targets) not at all.

**How close (*measured*, `fixtures` project of the sample suite).** Node for node, on the nine fixture pages and an iframe page, the two sources' trees differ in fields of the kinds above and in no role, name, state or relation (checked by comparing both trees field by field while this was written; the recordings of three pages are in `middleware/runtime/fixtures/devtools/` and `test_axtree.py` asserts what the extension's tree has). In CI the sample suite gives, on `ubuntu-latest`, 42 predicted utterances, 16 sweeps and 4 flags through the DevTools port against 37, 13 and 3 through the extension (the extension's run is not held to the tests that began before its service worker was up); on `macos-latest` 42, 17 and 4 through the DevTools port, and 0, 0 and 0 through the extension. Locally, three runs of the 13 tests, 6, 7 and 8 of the 13 transcripts are word for word the same as the extension's, and each of the three raised the same 4 flags. The ones that differ do so by what a quick test leaves the reader time for: the page of a test that ends within a few tens of milliseconds of the last action is gone before the tree after that action can be read, so the last focus move is sometimes missing (and, once in CI, the `silent-dialog` flag was raised for it, which is why `check-report.mjs --lower-fidelity` counts and prints a flag the extension's run does not raise and does not fail on it). On the six real pages of Q5 the two sources agree with the fleet to within a point (below).

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

**The same measurement with the tree read through the DevTools port (*measured* 2026-10-24; `figure-6/` is the extension's source and `figure-7/` the DevTools source, run in the same hour against the same fleet captures; **both not held out**).** For both, two runs of the corpus project, the first fleet capture against the first run, the channels as defined above:

| | the extension's tree (`figure-6/`) | the DevTools port's tree (`figure-7/`) |
|---|---|---|
| every channel, whether or not it was stable (the first block of `figure-4`'s second table) | **921 of 1,131 = 81.4%** | **909 of 1,131 = 80.4%** |
| ten commonest shapes, the same | 650 of 804 = 80.8% | 648 of 804 = 80.6% |
| stops, the same | 297 of 393 = 75.6% | 292 of 393 = 74.3% |
| the channels that were stable in both fleet captures and both runs (that set is smaller for the DevTools source: 149 units, 242 for the extension) | 206 of 242 = 85.1% | 128 of 149 = 85.9% |

So the lower-fidelity source costs a point on the same 1,131 units; which channels count as stable moves with the run (the pages move between readings, and so does a quick test's last event), so the first row is the one to compare. How the DevTools source got there is the same story as the extension's: the first reading of it, before any fix, was **73.4%** (179 of 244 units in its stable channels) and its misses showed faults of the conversion, six of which mattered most, each fixed with the conversion's own test or comparison against the extension's tree: the content of iframes (21 units, 0% before), a text inside a link marked `linked` (a leading empty utterance before the link's name), a node that has a click listener (`clickable`), an empty name kept as a name, a page with nothing in it yet read as the page, and the node that has the focus taken to be the document (which is also focused). Its stable-channel figure after them was 87.3% in one pair of runs and 85.9% in the next. **Fitted against these pages, as the extension's was.** The `typed` channel is 66.7% for both: the six digits are typed into a field on a page whose cookie dialog blocks the click (TfL), which the fleet's NVDA got through and the test did not.

**Where the misses are** (`figure-4/misses.json` has each with both strings): of 42 in the stable channels, **30 have no counterpart** and 12 are unexplained.

- *Four stops on the Companies House page have no counterpart*: the page's links named by an extra `(link opens a new window)`, which the page script's candidate names cannot match to the tree's node (`unresolvedFocus`: 6 of 131 focus events on the run's busiest runtime). A real version matches by DOM node and not by name.
- *The TfL page is the largest source (29 of 42).* It opens a modal cookie dialog. The test's click on the first text field is blocked by it (the test passes the walk and times out in the click after 180 s: the typed channel, 6 units, is empty), the fleet's NVDA moved the focus to the field regardless; and the tree's last state of the load is the dialog alone (a modal hides the rest from the tree), so the sweep's lists are the dialog's.
- *The "same page" state of a link* (two stops): Chrome tells a link to the page's own address "same page"; the tree the middleware read had it for some and not others.
- *Frames*: the list is the fleet's quick-navigation to frames; four are missing on two pages.
- Not at all in the misses of the stable channels: `visited` (the fleet's history has not got these pages as the Gate's did), the language names, the image-description prompt.

## Q6. Cost

**The middleware adds a start-up of about a second and a half, a tenth to a third of a second to each short test, and, for a test that walks a long page, a lag of seconds to minutes in the runtime that costs the test nothing but the wait at the end of the run. It is acceptable to run on every test of a suite of short tests; it is not for a suite whose tests walk pages of thousands of nodes, and what would make it cheaper is known.**

*Measured* on `ubuntu-latest` in the run of the final code (run 40125495459; the sample suite's `fixtures` project, 13 tests of about 0.3 s, three runs for each cell, medians; `middleware/results/ci/linux-x64/cost.log` and `cost.json`), against the same suite in the same Chrome with no extension, no flags and no runtime (`playwright.baseline.config.ts`):

| workers | without | with | with, no sweeps | added | of it, the sweeps |
|---|---|---|---|---|---|
| 1 | 4.32 s | 5.65 s | 6.10 s | +1.33 s | −0.45 s (noise: the run without sweeps was the slower) |
| 2 | 4.19 s | 5.66 s | 5.70 s | +1.46 s | −0.04 s (noise) |
| 4 | 4.60 s | 6.59 s | 6.36 s | +2.00 s | +0.24 s |

Earlier runs of the same measurement on other runners (their logs are in those runs' artifacts and are not committed): the same code, run 40115747087, +1.52 s, +1.76 s and +2.17 s; earlier code, run 40107916510, +2.50 s, +2.13 s and +2.49 s, and run 40105447525, +1.69 s, +1.57 s and +1.78 s. On this machine, warm: +0.9 s, +1.0 s, +1.6 s. A runner is slower and noisier by a factor of two between runs; the added time is one and a third to two and a half seconds on it and one to one and a half on a quiet machine.

- **At start-up:** the runtime is ready 0.1 to 0.3 s after it is spawned warm, and 0.13 to 0.49 s on a runner in the cost runs (1.2 s in an earlier demo run) (`bootMs` in `run.json`; NVDA's boot is not the cost: 240 ms). It is started before the workers and is on nobody's critical path. What costs is that **nothing listens for the first second:** the extension's service worker was up 0.4 to 1.5 s after the first test of a worker began on the runner (0.4 s warm), and the DevTools port 0.2 to 1.0 s after; a test that finished inside that window has no speech (Q2).
  The end of the run waits for the runtimes: 0.25 s at least (`drainMs`).
- **Per test:** the sum of the tests' own durations rose by 65 ms a test (1 worker), 96 ms (2) and 235 ms (4): the browser runs with accessibility on, the extension reads the tree, and on a two-core runner four workers compete with four runtimes. The "no sweeps" row is that without the sweeps.
- **Per sweep:** the runtime's time for a state of the fixtures' pages is 13 to 393 ms (median 34 to 52 ms; the slowest with four workers competing); on the real pages of Q5, 0.2 s to 5.6 s (the GOV.UK tabs page, about 900 nodes with frames). Sweeps run in the runtime's idle time, during the test, and only at the end of a state.
- **Per focus event:** NVDA's work for a stop is 100 to 170 ms on a real page (`speechMs` of the runtime that took the 85 stops of the GOV.UK tabs page: 14 s), because the emulator rebuilds the buffer from the whole tree for each event. The test does not wait for it; the end of the run does: the `drainMs` of the real-page runs is 0.25 s (the runtimes had kept up), but the run of three long walks waited 10.9 s and 25 s at the end.
- **The extension:** reading a node's fields costs 0.65 ms the first time (*measured*: 190 ms for 282 nodes, 400 ms for 668), so the first tree of a 2,700-node page takes about 2 s; later trees cost a tenth of it, because only nodes that changed and their ancestors are read again. Each tree is posted whole: megabytes for each change on that page. Beyond a few thousand nodes the test is over before the first tree arrives, which is why one tree waits at a time.

**The DevTools source** (*measured* locally, warm, the same machine and the same hour, three runs for each cell, medians of the wall time of the 13 tests; `middleware/results/cost-local/`): with the extension +1.5 s (2 workers) and +1.7 s (4 workers), through the DevTools port +0.85 s and +1.07 s (the one-worker baseline of the extension's set was disturbed: 5.1 to 7.2 s between its three runs, so that row is not quoted). It loads no extension and does its reading in the runtime's process; what it costs is a read of the page's tree and DOM after each change (15 to 50 ms for the fixtures' pages, a tenth of a second and more for a real one: `speechMs` and the tree reads of the Q5 runs), which the test does not wait for.

**What would make it cheaper:** (1) an incremental buffer in the emulator, so that a stop costs milliseconds and not a rebuild; (2) trees posted as differences, with the fields the emulator reads and not every field; (3) the runtime and the extension ready before the first page (a fixture the suite goes through, not a config, or a launch wrapper that waits); (4) a smaller bundle (the Python is 278 MB unpacked of 838 MB: python-build-standalone's `install_only_stripped` and without the test suite and the static library); (5) sweeps on a coarser trigger than every state.

## Q7. Packaging, the Playwright way

**Yes, the Playwright way, with no Docker, on a plain `ubuntu-latest` runner. A probe on macOS: with the extension's tree source it produced 0 predictions, and the reason is Chromium's (no desktop tree there); with the DevTools source, which macOS takes, it predicts, at lower fidelity.**

What the user does (the CI job `demo` does exactly this, run 40125495459, `.github/workflows/middleware-spike.yml`):

```sh
npm i -D @playwright/test <the package's tarball>      # npm pack, in this spike; npm i -D <name> when there is a registry
npx announcement-emulator install                        # fetch, check, unpack: 6 s on the runner, from a server on the runner itself
npx playwright test                                      # with the one line
```

- **The package** (`middleware/`, TypeScript, built with Rslib, tested with rstest, `private`, `UNLICENSED`): `withAnnouncements`, the reporter, `install`, `test`, `doctor`. It carries `pins.json`: for each platform, the bundle's file name, size and **sha256**. `install` downloads from the GitHub Release of the package's version, or from a mirror at `$ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST/v<version>/<file>` (A11-232; the spike itself had no host and published nothing), refuses the file unless its sha256 is the pinned one (a unit test: a file one byte longer is refused and nothing is unpacked), and unpacks it into `~/.cache/announcement-emulator/<version>-<platform>` (`ANNOUNCEMENT_EMULATOR_PATH` moves it, as `PLAYWRIGHT_BROWSERS_PATH` moves Playwright's).
- **The bundle**, one for each platform, built by `middleware/bundle/build.sh` from `pins.env` (the one file of revisions that `setup.sh` reads too): NVDA's source at `release-2026.1.1` (`5d92106f`, the part that runs, the spy synthesizer, and the three C++ files the live-region rules are read from), the CLDR names and the `nvda-appdir` overlay (copies, no links), the seven Chromium
  source files the tables are read from, Chrome for Testing 155.0.8059.84 (and, on Linux, the `.deb` libraries it needs, unpacked without root), python-build-standalone 3.13.16 (release `20261013`, refused unless its sha256 is the pinned one) with the emulator's packages installed straight into it (no virtualenv, so no absolute path),
  the emulator, the companion extension and the runtime. It holds neither the replay proxy (`mitmproxy`) nor `aria-practices`. *Measured:* linux-x64 298 MB as `tar.gz` (297.6 MB in the final run) (838 MB unpacked: Chrome 400 MB, Python 278 MB, NVDA's source 76 MB and its overlay 73 MB, the libraries 11 MB, the rest under 2 MB each), built in 116 s on the runner; darwin-arm64 242 MB, built in 83 s (run 40107916510, the first run of the same code; the linux job of the final run took 4 min 12 s for two builds, a comparison and the upload). `install` took 6 s on the runner, from a server on the runner.
- **The runtime is a separate process**: this package starts it with the bundle's Python and reads its JSON lines, and never imports it (ADR 0047, Decision 3; the package's `files` hold none of the runtime, and no TypeScript file names a Python module).
- **Built in this repository's CI**, one job for each platform. The linux-x64 job builds the bundle twice and compares the two files: they are the same bytes (sha256 `96ea8aaae874a1d827d8156f3f92bc489fb3ce48c00f2a0fa6214442daaa0e47`, run 40125495459; the pin the demo checked against). It took three changes to get there (a build id and the build directory in the compiled extension, and the interpreter's path in pip's scripts). The same build on another runner, or the darwin-arm64 bundle, was not compared.
- **On a plain runner, no container.** The jobs run on `ubuntu-latest` and `macos-latest` with no `container:`; nothing is installed on the runner (`apt-get download` only downloads). Playwright's own browsers are not installed: the tests ran in the bundle's Chrome. The bundle travels between jobs as a workflow artifact and is served to `install` from a static server on the runner (`python3 -m http.server`), so that the download, the checksum and the unpack are the real ones; a released version needs a host.
- **macOS: the extension's source reads nothing, the DevTools source predicts.** The bundle builds (83 s) and installs (3 s), the tests run in its Chrome for Testing 155 (they pass), and the runtime starts. **With the extension's source, macOS produced 0 predictions**: 0 snapshots, 0 focus events and 0 utterances on all 13 tests (*measured*, CI run 40125495459, `middleware/results/ci/darwin-arm64/announcement-emulator-run-extension/`). The reason is not a timing or a retry: `chrome.automation.getDesktop` is called back with no tree, and `chrome.runtime.lastError` is "getDesktop is unsupported by this platform" (`probe-tree.log`; an earlier version of the probe took a callback with no tree for no callback at all, and `passive.js` is written the same way: its callback reads `desktop.children`, which throws on a missing tree, so it never posts `ready`: the first reading of this was "never answers", and it was wrong). The desktop tree is built through Aura/Views, which macOS's browser UI does not use. The per-tab tree, `chrome.automation.getTree(tabId)`, is not in the API of Chrome 155 on any platform (same log). So macOS takes the DevTools source (Q2): on `macos-latest` the sample suite ran with the one line, the page load of all 13 tests was predicted, with 42 utterances, 17 sweeps and the 4 flags it is built to raise, labelled "lower fidelity" (`announcement-emulator-run/`), and the same suite with the extension's source is held to its 0 (`check-report.mjs --expect-no-tree`), so that the CI job fails if macOS starts to give a tree. **What was not tried on macOS:** the real pages of Q5 (the agreement figure is Linux's; Chrome's renderer builds the same tree on both, but the claim is not measured), and Windows.
- **A container image** is not worth offering as well, for now: the bundle runs on any glibc Linux without one, a container adds a second thing to keep in step with the pins, and the only user it would serve is one whose CI cannot reach a bundle host. If a real version has such users, an image is the bundle plus a base: a dozen lines.

## The tree sources, measured against the fleet (A11-229)

**By the rule frozen before the first capture, the extension buys 0.7 points over the DevTools port on Linux (82.1% against 81.4% of 1,138 units), which is inside the 1.0-point margin, so the recommendation by the rule is to drop the extension. The measurement cannot tell that lead from none: the discordant units are 23 for the extension and 15 for DevTools (an exact two-sided sign test gives p = 0.26), and the second capture read against the second run gives the extension a lead of −8.1 points, because its second run of one page had no sweep. On macOS the DevTools source agrees with the fleet on 83.6% of the units of the five pages the runner could open, 1.2 points above this host's DevTools reading of the same units. 81% to 84% of each Linux source's misses are misses of both: the tree source is not what limits the agreement.**
(*measured* 2026-10-24; everything under `middleware/results/tree-source/`; **not held out**: the pages are Q5's, which the emulator was fitted against.)

**Recommendation by the frozen rule; the chairman reads it, and decides. This ticket removes nothing.** The chairman's decision of 2026-10-24 stands in the code (both sources, DevTools the baseline and macOS's, the extension the default on Linux and Windows) until the chairman says otherwise.

### How it was measured

`middleware/results/tree-source/rule.md`, `compare_sources.py`, the two drivers and the macOS workflow were committed and named in `freeze.json` (`bcec5908e7`, named 2026-10-24 20:46:29 UTC) **before** the first fleet capture (20:49:41 UTC); `make_freeze.py check freeze.json --head bcec5908e7 --fleet <captures>` passes and says every capture is after the freeze. The rule adopts Q5's unchanged: the same six pages, the `corpus` project, channels, units, shapes and matching (`measure.py`, which gained only a refusal of a set of runs that mixes tree sources and `--second`).

| reading | source | where | what ran |
|---|---|---|---|
| `ext-linux` | extension | this host, Chrome for Testing 155 | two runs, interleaved with the next |
| `devtools-linux` | DevTools port | this host | two runs (order: extension, DevTools, extension, DevTools; 20:47 to 21:03 UTC) |
| `devtools-macos` | DevTools port | `macos-latest` (ARM64), workflow run 40131350746 | two runs, 20:49 to 20:52 UTC |
| `devtools-ubuntu-ci` | DevTools port | `ubuntu-latest`, the same workflow run | two runs: **a control**, for attribution only |

The fleet: each page twice on two of `a11y-worker-14`, `-15`, `-16` (12 captures, all status 200, 20:49 to 21:09 UTC), boxes chosen from the 12 that agree on code hash `25bb45d9b38d7a62`, Windows 26300.9711 and Edge 156.0.4314.42 (`boxes.md`). **Nothing on the fleet was changed.** Edge is one milestone ahead of Chrome 155, as in Q5. The headline is Q5's second block: every channel, stable or not, the first capture against the first run, with the census tolerance. Windows was not measured.

On `macos-latest` and `ubuntu-latest` the runner was served a bot check ("Just a moment") by `tfl.gov.uk`: that page was not seen, so those two readings have five pages (1,026 units). The reports travelled in a one-day artifact and were deleted once downloaded.

### The readings

| | units | agreed | headline | second capture against second run |
|---|---|---|---|---|
| `ext-linux` | 1,138 | 934 | **82.1%** | 74.7% (850) |
| `devtools-linux` | 1,138 | 926 | **81.4%** | 82.8% (942) |
| `devtools-macos` | 1,026 | 858 | **83.6%** | 82.8% (850) |
| `devtools-ubuntu-ci` (control) | 1,026 | 880 | **85.8%** | 83.0% (852) |

The readings do not have the same units (two do not have TfL). On the 1,026 units all four have, in the headline: extension 83.0%, DevTools on Linux 82.4%, DevTools on macOS 83.6%, the control 85.8% (`common_units.py`, read after the figure).

The extension's low second reading is one page: in its second run the TfL test (which times out on a cookie dialog in every run, as in Q5) ran the `dialog` sweep and no `load` sweep, so the page's seven lists were empty (9 of 112 units agreed there, against 82 in its first run and 81 in both DevTools readings). The first reading is the one the rule compares.

### What the extension buys (the units both Linux readings compare, 1,138)

| | extension | DevTools | lead (points) |
|---|---|---|---|
| everything | 934 (82.1%) | 926 (81.4%) | **+0.7** |
| the second capture against the second run | 850 (74.7%) | 942 (82.8%) | −8.1 |

The extension agrees and DevTools does not on 23 units; DevTools agrees and the extension does not on 15. The two leads differ by 8.8 points; the noise is larger than the margin, and the rule is applied as written.

By channel (agreed of units, extension / DevTools): title 5 / 6 of 6; stops 297 / 295 of 396; field 2 / 2 of 3; typed 12 / 12 of 18; headings 63 / 62 of 106; **landmarks 45 / 41 of 45 (+8.9)**; formFields 66 / 69 of 100 (−3.0); graphics 5 / 5 of 7; links 364 / 359 of 376 (+1.3); lists 57 / 58 of 61; frames 18 / 17 of 20.

By shape (the ten commonest of the paired units; the fleet against itself in brackets):

| shape | extension | DevTools | DevTools on macOS | control |
|---|---|---|---|---|
| NAME + ROLE | 273 / 288 94.8% (99.0%) | 274 / 288 95.1% | 245 / 248 98.8% | 247 / 248 99.6% |
| NAME + ROLE + STATE + STATE | 216 / 245 88.2% (95.1%) | 215 / 245 87.8% | 213 / 243 87.7% | 215 / 243 88.5% |
| NAME + ROLE + LEVEL | 44 / 82 53.7% (100%) | 44 / 82 53.7% | 42 / 80 52.5% | 42 / 80 52.5% |
| NAME + ROLE + STATE | 29 / 39 74.4% (79.5%) | 31 / 39 79.5% | 27 / 35 77.1% | 29 / 35 82.9% |
| NAME + ROLE + STATE + STATE + POSITION | 3 / 35 8.6% (100%) | 4 / 35 11.4% | 3 / 35 8.6% | 3 / 35 8.6% |
| NAME + STATE + ROLE | 23 / 25 92.0% (92.0%) | 23 / 25 92.0% | 19 / 21 90.5% | 19 / 21 90.5% |
| NAME | 17 / 24 70.8% (100%) | 18 / 24 75.0% | 17 / 17 100% | 15 / 17 88.2% |
| NAME + ROLE + STATE + STATE + STATE | 7 / 24 29.2% (66.7%) | 7 / 24 29.2% | 15 / 24 62.5% | 16 / 24 66.7% |
| NAME + NAME + ROLE | 22 / 22 100% | 22 / 22 100% | 21 / 22 95.5% | 22 / 22 100% |
| NAME + ROLE + STATE + NAME | 15 / 21 71.4% (100%) | 15 / 21 71.4% | 15 / 20 75.0% | 15 / 20 75.0% |

(`comparison.txt` has the full tables, including each reading's fleet against itself by channel and shape.) Units of the shapes with a position (`NAME + ROLE + STATE + STATE + POSITION`, 8.6% to 11.4%) and a level (53.7%) are where both sources lose most, and they lose the same units.

### The misses, every one attributed

Each miss has one cause from the rule's closed list (`figure-*/misses.json`), assigned mechanically in the rule's order. **`unexplained` is 0 in every reading.** `oracle milestone` and `focus match` can only be read by a person and were not assigned: no miss carries evidence of the field a milestone changes, and the run's `unresolvedFocus` is a count for a worker and not a unit (9 to 29 of a worker's focus events in each run, so some of the `emulator` misses on stops are that).

| cause | `ext-linux` | `devtools-linux` | `devtools-macos` | control |
|---|---|---|---|---|
| `emulator`: both sources miss the unit (for macOS and the control, this host's cause) | 171 | 171 | 93 | 100 |
| `history`: a `visited` token only | 15 | 15 | 12 | 12 |
| `page moved`: the two fleet captures differ there | 4 | 6 | 5 | 5 |
| the extension's own (`tree:`) | 14 | | | |
| DevTools's own (`conversion:` 19, `events:` 1) | | 20 | 9 | 9 |
| `network/runner` | | | 6 | 20 |
| `macos:` (macOS and the control predict different strings) | | | 43 | |
| **misses** | **204** | **212** | **168** | **146** |

**What each source gets wrong that the other does not** (this is what the extension buys, and what step 3 of A11-229 fixes in DevTools):

- The extension's: 9 units where it has no node (tab buttons of the Tabs and NHS table pages, a search combo box, a button), a focus stop it did not resolve, a tab's `selected` state, a title spoken with `document` and a list line that differs (`tree:` name, state, landmark+name+role+set size).
- DevTools's (the work list): the header text that NVDA speaks for a table cell (`row 2, Changed, column 2`) and `same page` on a link (`conversion: name`, 7 units); `clickable` on a landmark, which DevTools does not report (4); no node for 5 formFields and a heading (`conversion: node`, 5), among them the controls inside an iframe of the same site; the name, role and level of a frame (1); a tab's `selected` state (1); a stop that landed on another element (1); and a stop it predicted nothing for (`events: focus`, 1). The macOS reading and the control have 9 `conversion:` units each, of the first two kinds.
- On macOS, 43 units differ from the control: 22 are stops (mostly a tab button whose focus was matched to another link, or to nothing), 14 are formFields, 3 headings and 3 a frame's name (the same units macOS's tree lacked), 1 a typed field. Whether they are the macOS runner's tree or its focus matching is not separated by this measurement.

The causes by shape are in `comparison.txt`.

### The margin and the recommendation

**The margin is 1.0 point**, fixed in `rule.md` before the captures, and it decides only a recommendation: at most 1.0 point, drop the extension (one path is cheaper to keep); more, keep both. Why 1.0: (a) the same extension source on the same fleet captures read 80.8% and 81.4% in A11-208, 0.6 points of movement with nothing changed but the run; (b) one point is about 11 of the 1,131 units, fewer than the stop channel's movement of the fleet against itself (95.2%, 19 of 393); (c) the ticket proposes 1 point. This measurement's own noise is larger than (a) said: the second reading differs from the first by 8.8 points, from one page of one run.

**Recommendation by the frozen rule (the chairman reads it): DROP THE EXTENSION: its lead is +0.7 points (934 against 926 of 1,138 units), at most the 1.0-point margin.** What would change the reading, none of which the rule counts: (1) the lead is not distinguishable from zero here (p = 0.26) and the second reading goes the other way; (2) the corpus walks six pages by keyboard and types into a field, so it measures stops, typed echo and the load's lists, **not live-region or other change events**, which the extension reports from the browser and DevTools derives from a page listener, and that is where the extension may still buy something this measurement cannot see (A11-229 step 3 derives them from the tree and re-measures); (3) Windows was not measured; (4) six pages, not held out, an oracle one milestone ahead. The other side: 171 of the 204 misses of the extension are misses of DevTools too, and DevTools on macOS reads at the level of the Linux readings, so what the rule weighs is a second path for 20 units that only the extension gets right, against 14 that only DevTools does.

## The structure safeguard: table- and list-heavy pages (A11-229, step 2)

**By the gate frozen before the capture, the answer is STOP AND REPORT: on the table pages the extension leads DevTools by +1.8 points (323 against 317 of 342 units, 6 units), above the 1.0-point margin. Everywhere else the lead is the other way: on all the units both sources read, DevTools agrees with the fleet on 76.1% and the extension on 71.2% (−4.9 points, 1,492 units), and on the list pages DevTools leads by 6.9. The extension gave no reading of Beaufort scale in any run, and none of the legislation changes table in its first run (the run the headline reads): the two pages with the biggest tables. The fields that make the difference on the table pages are not table indices or set positions: they are `clickable` (6 units), a typed value in a text field (1) and the description words of a table cell's link (4).** The chairman reads it and decides whether step 3 (remove the extension) goes on.
(*measured* 2026-10-25, 09:33 to 10:09 UTC; everything under `middleware/results/tree-source-structure/`; **not held out**; an oracle of the same milestone as the browser, not the same build.)

`comparison.json`'s `extensionBuys.recommendation` is step 1's rule applied to these numbers (`compare_sources.py` was frozen with it); this measurement's decision is `extensionBuys.gate`, and `comparison.txt` prints only that.

### Why a second measurement

Step 1's six pages are light on tables and long lists, which is where the extension's extra fields (table indices, set positions) could matter. The chairman's decision of 2026-10-25 was to drop the extension, with one safeguard first: measure both sources on table- and list-heavy real pages, by a rule frozen before capture; if DevTools is within the 1.0-point margin there too, remove the extension; if the extension leads by more, stop and report which fields make the difference.

### How it was measured

`middleware/results/tree-source-structure/rule.md`, `candidates.json`, `pages.json`, `select_structure_pages.py`, `dom_check_structure.mjs`, `compare_sources.py` and the drivers were committed and named in `freeze.json` (`1cf8cd09f7`, named 09:33:30 UTC) **before** the first fleet capture (09:38:54 UTC); `make_freeze.py check freeze.json --head 1cf8cd09f7 --fleet <captures>` passes and says every capture is after the freeze. The rule is step 1's, and Q5's under it: the corpus walk, channels, units, shapes, matching, the headline (every channel, the first capture against the first run) and the 1.0-point margin. What is new is the pages and the gate.

After the freeze `compare_sources.py` was refactored on main (A11-229's sibling, the per-build measurement of A11-230, moved its tables into helpers); the merged script, re-run on the same inputs, writes `comparison.txt`, `comparison.json` and both `figure-*/` directories byte for byte as committed, and `make_freeze.py check … --head 1cf8cd09f7` still passes at the freeze commit.

**The pages.** 37 public pages named by hand, in two rounds (34 before the first run; after it three table pages were added: Beaufort scale, Companies House 00000086 and the legislation changes table, because the first pass found tables with links in their cells only on Wikipedia, and the Wikipedia ones were then over the size limit; three of the final four table pages come from that round, and `rule.md`'s sentence that the sample is the same ordering under the limit is imprecise on this: the ordering is over the widened list), of the shapes the chairman listed (data tables with headers, long navigation lists, nested lists, a grid, a tree view). Each in turn, in the order of the SHA-256 of its address, was opened and its DOM counted, and nothing else (`dom_check_structure.mjs`). A **table page** has at least 3 header cells, a table of at least 40 cells and at least 20 tab stops inside table cells; a **list page** has at least 20 tab stops inside list items and a list of at least 20 items or at least 3 nested lists; a page of more than 500 tab stops is neither. The first four of each class are the sample:

| class | page | tab stops | what the DOM has |
|---|---|---|---|
| table | legislation.gov.uk, Changes to Legislation affecting the Human Rights Act 1998 | 284 | one table of 462 cells, 243 tab stops in cells |
| table | Companies House, filing history of company 00000086 | 71 | a table of 78 cells, 26 tab stops in cells |
| table | Companies House, filing history of company 00000006 | 68 | a table of 78 cells, 25 in cells |
| table | Wikipedia, Beaufort scale | 293 | a table of 112 cells, 62 in cells |
| list | W3C APG, scrollable listbox example | 59 | a list of 27 items |
| list | Wikipedia, Outline of computer science | 409 | 7 nested lists, 349 tab stops in items |
| list | legislation.gov.uk, Human Rights Act 1998 contents | 125 | a list of 38 items, 10 nested lists |
| list | GOV.UK Design System, Table | 100 | a list of 39 items |

**The first freeze and why it was replaced.** The rule was first frozen (`89ca720fff`, 08:50:50 UTC) without a limit on the size of a page, and its sample held four Wikipedia tables of 963 to 1,770 tab stops and the Equality Act 2010's contents (705). On the first of its four runs the middleware predicted nothing for those five pages, and a DevTools run of the small listbox page alone waited 69 s at its end for 59 focus events, so that the same run on pages of that size would have taken hours. Fifteen fleet captures of that sample were taken and discarded unread; no figure of any reading had been computed. The limit of 500 tab stops was chosen after seeing that, and says so in `rule.md`. A page with more than 500 tab stops is a page this middleware cannot yet predict at all, with either source; that is a finding of its own, and not a finding about tables.

**The readings.** The extension and DevTools on this host, in Playwright 1.64.1's Chromium 156.0.8078.4, two runs each, interleaved (extension, DevTools, extension, DevTools; 09:33 to 09:52 UTC), in the `structure` project (the corpus walk, held equal to the corpus test by `test_structure_walk.py`). The fleet: each page twice on two of `a11y-worker-14`, `-15`, `-16` (16 captures, all 200, 09:38 to 10:08 UTC), boxes that agree on code hash `25bb45d9b38d7a62`, Windows 26300.9711 and Edge 156.0.4314.42 (`boxes.md`). **Nothing on the fleet was changed.** macOS and a control were not run: macOS takes DevTools whatever this finds. Windows was not measured.

### The readings, and the gate

| | pages read | units | agreed | headline |
|---|---|---|---|---|
| `ext-linux` | 6 of 8 | 1,492 | 1,062 | 71.2% |
| `devtools-linux` | 8 of 8 | 2,199 | 1,609 | 73.2% |

The headline rows are over different units, because the extension read six pages. The rule compares the units both read (1,492):

| | extension | DevTools | lead (points) |
|---|---|---|---|
| **all pages** | 1,062 (71.2%) | 1,135 (76.1%) | **−4.9** |
| **table pages** (2 pages read by both) | 323 (94.4%) | 317 (92.7%) | **+1.8** |
| **list pages** (4 pages) | 739 (64.3%) | 818 (71.1%) | **−6.9** |
| the second capture against the second run, all pages | 1,234 (66.3%) | 1,308 (70.2%) | −4.0 |

**Gate by the frozen rule (the chairman reads it): STOP AND REPORT: the extension leads by more than the 1.0-point margin on table pages (+1.8).** Step 3 goes on only if the lead is at most the margin overall and on each class.

How much weight the stop carries: the table lead is 6 units from 342, on two filing-history pages that share one template (the discordant units are 11 for the extension and 5 for DevTools; an exact two-sided sign test gives p = 0.21, not distinguishable from none). Over all pages the discordant units are 23 for the extension and 96 for DevTools (p < 10⁻¹¹), and on the list pages 12 and 91. The rule is applied as written; these are the facts beside it.

By page (agreed of units; the extension's reading is empty where it has none):

| page | class | extension | DevTools |
|---|---|---|---|
| legislation.gov.uk, changes affecting the HRA | table | **no reading** | 220 of 378 |
| Companies House 00000086 | table | 166 of 173 | 161 of 173 |
| Companies House 00000006 | table | 157 of 169 | 156 of 169 |
| Wikipedia, Beaufort scale | table | **no reading** | 254 of 329 |
| APG scrollable listbox | list | 58 of 159 | 137 of 159 |
| Wikipedia, Outline of computer science | list | 190 of 454 | 185 of 454 |
| legislation.gov.uk, HRA contents | list | 286 of 303 | 293 of 303 |
| GOV.UK Design System, Table | list | 205 of 234 | 203 of 234 |

**The extension's coverage.** On Beaufort scale the extension source gave one snapshot, no key and no focus event in both runs and in a third run alone (not diagnosed: the page loads and the walk completes in the browser); on the legislation changes table it gave nothing in the first run and 46 utterances in the second (against DevTools's 142 to 152). With the extension's units on those two pages counted as misses, its agreement over all eight pages would be 1,062 of 2,199 (48.3%). The pairing leaves them out.

### The fields that make the difference

Read after the figure (`fields_after_the_figure.py`, `fields-after-the-figure.txt`; not part of the frozen rule and labelled so): where the sources disagree on a unit, the field in which the loser's string differs from the fleet's.

| | the extension agrees and DevTools does not | DevTools agrees and the extension does not |
|---|---|---|
| table pages | `clickable` 6, name 5 | no prediction 4, name 1 |
| list pages | name 10, name+role+state 1, no prediction 1 | no prediction 85, set size 3, name 1, landmark+level+name 1, landmark+name+role+set size 1 |

On the table pages the 11 units of the extension are:

- **`clickable`, 6 units**, on the Companies House pages: DevTools says `clickable` on a landmark (the search landmark), a form field (a check box), and a grouping; the fleet and the extension do not. `axtree.py` takes `clickable` from `DOMSnapshot`'s `isClickable` (a node with a click listener); the extension's tree does not report it on these nodes.
- **name, 5 units**: a typed value (`Search for a company or officer, edit, 12345`: DevTools's string has the digits the test typed into the field, the fleet's and the extension's do not: 1 unit); the words of a cell's link (`View / Download (PDF file, link opens in new window)`, 3 units) and the description of the document filed that a column's header carries (1 unit), which DevTools's tree does not name.

The table index (`row 2, column 3`) and the set position are **not** among them. They agree with the fleet where DevTools reads the page: the only `set size` units (3) are ones where the extension is wrong. Where the DevTools source does lose table units is the header text NVDA speaks with a cell: on the two pages the extension did not read, **163 of DevTools's 233 misses are the fleet's string with words missing** around the `row N` or `column N` (`Made by, column 6, 2013 c. 22, link` against `column 6, 2013 c. 22, link`; 143 on the legislation changes table and 20 on Beaufort scale). They were given the cause `conversion: name` by a reader's note (`attribution-notes.json`), with the evidence in each reason: no source agrees where DevTools does not, since the extension has no reading, so whether the extension would have spoken the header text is not known from this measurement. `axtree.py` builds a cell's row and column indexes by counting; the header text is the field step 3 would need from `DOMSnapshot`, the table's `th` cells or `getPartialAXTree`.

### The misses, every one attributed

Each miss has one cause from step 1's closed list (`figure-*/misses.json`), assigned mechanically in the rule's order, and the reader's notes above. `unexplained` is 0 for the extension and 9 of 590 for DevTools, each with its reason (a stop that landed on another element, a combo box named `pane`, a skip link; `comparison.txt`).

| cause | `ext-linux` | `devtools-linux` |
|---|---|---|
| `emulator`: both sources miss the unit | 315 | 315 |
| `history` | 18 | 18 |
| the extension's own (`tree:` node 58, focus 31, set size 3, name and others 4) | 96 | |
| DevTools's own (`conversion:` name 177 of which 163 by a reader's note, clickable 6, others 2) | | 185 |
| `prompt` (the image description prompt: Beaufort scale's pictures) | | 53 |
| `no counterpart` 8, `unexplained` 9, `page moved` 1, `quick test` 1 | 1 | 19 |
| **misses** | **430** | **590** |

### Cost, which is also a finding

The runtimes' time (`passive-runs.json`): the extension's runs took 113 to 130 s (the runtimes' speech time 136 to 167 s over 549 to 589 focus events), DevTools's 415 to 450 s (566 to 603 s over 890 to 892 events), **3.5 to 3.7 times as long for the same walks**, because DevTools reads and converts the whole tree again at each event. Pages of more than 700 tab stops produced no prediction with the extension in the first freeze's run, and were not run with DevTools. A DevTools-only middleware needs its tree read made cheaper before it can serve large pages.

### What this measurement does not see

The channels are step 1's. The walk presses Tab, so a grid or tree that moves focus by the arrow keys is entered once: the APG grid, treegrid and treeview pages had 1 to 7 tab stops in cells and were not in the sample. The structure sweep has no table channel. A table index reaches a figure through the focus phrase of a stop inside a cell and through the `lists` channel; set positions through stops inside list items. Change events (live regions) are not in the corpus walk. Two of the four table pages are one template. The gate cannot trip on a class of which the extension read no page, because the pairing leaves the class out (`lead_by_class` in the frozen `compare_sources.py`); here it read two pages of each class, so every class has units. The pages are public and move: `page moved` is 1 miss. The oracle's Edge (156.0.4314.42) is the same milestone as the runs' Chromium (156.0.8078.4), not the same build.

### What I recommend, and what the chairman decides

By the gate, step 3 (remove the extension) does not go on until the chairman reads this. The numbers beside the gate: DevTools is ahead overall and on lists by far more than the margin, the table-page lead of the extension is 6 units on one template (p = 0.21), and the fields that make it up are three that DevTools can work on without the extension: why `isClickable` marks a landmark, a check box and a grouping that the fleet does not call clickable (6 units); the typed digits in a field's string (1); and a link's and a header cell's description words (4). **My recommendation, which the chairman may overrule: take the stop as a work list rather than as a veto: fix those three and the header text in DevTools, re-run this measurement under a fresh freeze, and remove the extension once the table pages are within the margin.** If the chairman prefers to remove the extension now, step 3 carries the same work list. Either way the cost finding applies to DevTools alone.

## What a real version needs, and the recommendation

**Go for building it properly, as an advisory tool with its measured rate printed first, if the chairman wants the product; the spike answers "can it be done the Playwright way" with yes and "how well" with "about four in five stops and lists, on a small sample, on one platform".** The decision is the chairman's.

For the go:

- The shape works end to end on a plain runner: one line (or none), a pinned and checksummed bundle fetched the way `playwright install` fetches a browser, a separate process that the package never imports, a report that carries the speech, the sweeps and the flags, and every output saying it is a prediction.
- Nothing about it needs a person to write a test twice, and it did not fail one test of the sample suite (a runtime that cannot start leaves the tests as they were).
- The cost on short tests is acceptable and its causes are known.

Against going as it stands:

- **The agreement is 83.1% and the Gate's bar is 98%.** Part of it is the oracle (an Edge milestone ahead, pages that move between readings: the fleet against itself is 95.2% on the stops) and part is the middleware's own faults, of which the measurement found five in a morning. ADR 0047 Decision 6 says a published package states its measured rate; on this evidence the honest sentence is "about 80% on six pages, not held out".
- **It sees nothing in the first second of a worker, and loses a page that is closed before its tree arrives.** A test that is short and quick is the one it misses.
- **macOS has only the lower-fidelity source, and Windows was not tried.** The extension's tree (`chrome.automation.getDesktop`) is a Linux, Windows and ChromeOS thing; macOS gets the tree through the DevTools port, which agreed with the fleet to within a point of the extension's on Linux (not measured on macOS), has no iframes of another site, and loses the last event of a very quick test.

What a real version needs:

1. **A bundle host and a release pipeline** (the bundle is 298 MB; a registry-like store, a checksum in the package, retention), and the **bundle's reproducibility checked across runners and on macOS** (built twice on the linux-x64 runner, byte for byte the same (sha256 96ea8aaae874a1d8…; not checked on macOS or on two runners)). Trim it: python-build-standalone's stripped build, the browser's unused locales.
2. **The package's name** (not "NVDA" in it: ADR 0047), the **NV Access question** (ceo's to send before the first public release), the **npm package's licence** (the runtime is GPL-3.0; the package is `UNLICENSED` here), and the **measured agreement rate** printed in its README (Decision 6), on a larger sample than six pages, from boxes on the same Edge milestone as the Chrome.
3. **The runtime and the extension ready before the first page.** A fixture the suite goes through, or a launch that waits, instead of a config that cannot; and a way to carry on when the user passes `--reporter` (the launch options must not depend on the reporter).
4. **Trees as differences and an incremental buffer.** Today each change posts the whole tree (megabytes on a 2,700-node page) and each stop rebuilds NVDA's buffer (100 to 170 ms); a test that walks a big page is the one that cannot be afforded.
5. **Matching a page's focus to the tree by DOM node** (`DOM.getNode` and the AX node's backend id over the DevTools port), not by tag and name: 6 of 131 stops of the busiest run could not be matched.
6. **The DevTools source measured on macOS** (its agreement was measured on Linux), made the one source if its fidelity is enough (it has no extension to load, no service worker to wait for and no desktop to need), with the iframes of other sites (their own targets) and DOM-node matching of the focus; and the live-region and dialog rules checked against NVDA on the fleet with pages written for the purpose (the fixtures' pages are ready for it: `middleware/sample-suite/pages/`).
7. **Decide what the attached speech is.** Today it is what NVDA's focus event says; the fleet can only be asked what NVDA says when asked to repeat the focus. A guidepup-style API for writing screen-reader tests (the ticket: later, if at all) would put the fleet's own probes in a test; this spike's `repeatFocus` is the seed of it.

## Decisions made without a person

The plan was written by an unattended planning run, not agreed with a person. Each decision it made without a person, and each this run made where the plan could not be followed, for a reviewer to check against the code. (The same list is in the pull request.)

**From the plan, followed:**

- Packaging is the npm package plus a downloaded runtime bundle, with no Docker, and a container gets one paragraph (Q7). Evidence: Q7 and the Acceptance of the ticket.
- Attach order: zero lines, then one config line, then one import; the first that works answers Q1 (both of the first two work; the import was not built).
- At the spike the launch added `--disable-features=DisableLoadExtensionCommandLineSwitch` and dropped Playwright's `--disable-extensions` (`middleware/src/config.ts`, `extension.ts`); neither is done now (A11-229, step 3).
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
- *The extension is two files and not one.* `emu/ext2/tree.js` holds the dump code shared by `bg.js` and the new `passive.js`; `bg.js` behaves as before (*measured* 2026-10-24 on the final code: the Q2 suite, `emu/run_cases.py`, which drives the emulator's own session and so loads `bg.js` and `tree.js`, gives 215 of 227, as before the split; `middleware/src/extension.test.ts` checks that `tree.js` lists a node's fields in the order `bg.js` did).
- *Two emulator stand-ins changed for reasons the plan did not foresee:* `calculateCharacterBoundaries` was missing (typed characters), and `emu/winuser_standin.py` read NVDA's source from one machine's home directory.
- *The boxes are `a11y-worker-14` and `-16`, on Edge 156,* not three boxes on Edge 155: the fleet moved under the rule (`middleware/results/agreement/boxes.md`).
- *Three corrections were made after the first figure was taken at the freeze, and are labelled "not held out" where they matter:* a stop is read with the focus on it (`focused_on`), a state is swept over its last tree, and a browser launched again is heard as the first was; then the extension keeps one tree waiting for a page and forgets a closed page. The first figure is kept (`middleware/results/agreement/figure-1/`), and `make_freeze.py check --head <freeze commit>` passes at the freeze commit.
- *The cost is measured on the sample suite's fixtures project, in the CI run, three times for each setting.* The corpus walks are timed from the runtime's own counts.

**Decisions of the feedback round (made without a person; the feedback was that the macOS job failed):**

- *The macOS job is made to pass by what it proves, not by being allowed to fail.* The Linux report check wants flags that a run with no tree cannot raise; the job was `continue-on-error`, so the failure was a red check on a green run. Now each platform is run with both tree sources and each run is held to what the write-up says of it: the extension's source on macOS to 0 (`--expect-no-tree`), the DevTools source to a page load for three tests in five, a sweep and one of the flags (`--lower-fidelity`).
- *The per-tab tree was probed first and does not exist* (`chrome.automation.getTree` is `undefined` in Chrome 155), *so the DevTools fallback was built, not written up as impossible*, because it could be validated entirely on Linux (the renderer's tree is the same on both platforms) by comparing it with the extension's tree node by node, and measured on the same pages.
- *The DevTools source is macOS's default; `ANNOUNCEMENT_EMULATOR_TREE=extension|devtools` overrides it.* The extension stays the default elsewhere because it is what the Q5 figure was taken with. (Overtaken by A11-229, step 3: there is one source and no override; the variable is ignored.)
- *A flag the extension's run does not raise is counted and printed, not a failure of the lower-fidelity check,* because it is a flag made of a missing event (above), which is a limit of the source and not a fault of the sample suite.
- *The chairman's comment said "never calls back"; it was a call back with no tree.* Corrected in Q7 with the probe's output, and the earlier sentences of this page that said the same are gone.

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
# the DevTools tree source: ANNOUNCEMENT_EMULATOR_TREE=devtools npx playwright test (in the project below); the comparison with the extension's is the two runs of the corpus project and measure.py for each (figure-6, figure-7)

# the bundle, and the sample suite on a plain runner: .github/workflows/middleware-spike.yml (jobs bundle and demo); locally
middleware/bundle/build.sh linux-x64 /tmp/bundle                       # about 2 minutes, 300 MB
node middleware/bundle/write-pins.mjs 0.0.0 /tmp/bundle/pin-linux-x64.json > middleware/pins.json   # (the spike's was 0.0.0-spike.0)
( cd middleware && pnpm run build && npm pack )                        # then, in a project with @playwright/test: npm i -D the tarball; npx announcement-emulator install
cp -R middleware/sample-suite /tmp/project && cd /tmp/project && npx playwright test --project=fixtures && node check-report.mjs

# the agreement (the fleet's records are third-party pages and are not committed; the tables and each miss are)
python3 middleware/agreement/select_pages.py <chrome> middleware/results/agreement/pages.json     # the rule's page list
python3 middleware/agreement/make_freeze.py name middleware/results/agreement/freeze.json          # BEFORE any capture
python3 middleware/agreement/capture_fleet.py middleware/results/agreement/pages.json <dir> --workers a11y-worker-14=http://<host>:8765,...
( cd middleware/sample-suite && ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1 npx playwright test --project=corpus )   # twice; keep test-results/report.json of each
python3 middleware/agreement/measure.py --fleet <dir> --passive <report 1> <report 2> --pages middleware/results/agreement/pages.json [--include-unstable --tolerate-census]
python3 middleware/agreement/make_freeze.py check middleware/results/agreement/freeze.json --head <the freeze commit> --fleet <dir>

# the tree sources (A11-229): freeze, capture, the four interleaved runs on this host, the workflow for macOS and the control, measure, compare
python3 middleware/agreement/make_freeze.py name middleware/results/tree-source/freeze.json --also middleware/results/tree-source/rule.md --also middleware/agreement/compare_sources.py \
  --also middleware/agreement/run_linux_readings.sh --also middleware/agreement/measure_readings.sh --also middleware/agreement/export_misses.py --also .github/workflows/tree-source-agreement.yml   # BEFORE any capture
sh middleware/agreement/run_linux_readings.sh <project with the package installed> <runs dir>        # then commit a new stamp in middleware/results/tree-source/ci-run.txt: tree-source-agreement.yml runs macOS and the control
sh middleware/agreement/measure_readings.sh <fleet dir> <work dir> ext-linux=<r1>,<r2> devtools-linux=<r1>,<r2> devtools-macos=<r1>,<r2> devtools-ubuntu-ci=<r1>,<r2>
python3 middleware/agreement/compare_sources.py --work <work dir> --out middleware/results/tree-source [--notes attribution-notes.json]
python3 middleware/agreement/make_freeze.py check middleware/results/tree-source/freeze.json --head bcec5908e7 --fleet <fleet dir>
python3 middleware/agreement/common_units.py <work dir> ext-linux devtools-linux devtools-macos devtools-ubuntu-ci
# the structure safeguard (A11-229, step 2): select the pages, freeze, capture, run, measure, compare, read the fields after the figure
python3 middleware/agreement/select_structure_pages.py middleware/results/tree-source-structure/candidates.json middleware/results/tree-source-structure/pages.json   # once; DOM counts only
python3 middleware/agreement/make_freeze.py name middleware/results/tree-source-structure/freeze.json --also middleware/results/tree-source-structure/rule.md --also middleware/results/tree-source-structure/candidates.json \
  --also middleware/results/tree-source-structure/pages.json --also middleware/agreement/select_structure_pages.py --also middleware/agreement/dom_check_structure.mjs --also middleware/agreement/compare_sources.py \
  --also middleware/agreement/run_linux_readings.sh --also middleware/agreement/measure_readings.sh --also middleware/sample-suite/tests/structure --also middleware/sample-suite/base.config.ts --also middleware/results/tree-source/rule.md   # BEFORE any capture
python3 middleware/agreement/capture_fleet.py middleware/results/tree-source-structure/pages.json <fleet dir> --workers a11y-worker-14=http://<host>:8765,a11y-worker-15=...,a11y-worker-16=...
sh middleware/agreement/run_linux_readings.sh <project with the package installed> <runs dir> structure
PAGES=middleware/results/tree-source-structure/pages.json sh middleware/agreement/measure_readings.sh <fleet dir> <work dir> ext-linux=<r1>,<r2> devtools-linux=<r1>,<r2>
python3 middleware/agreement/compare_sources.py --work <work dir> --out middleware/results/tree-source-structure --classes middleware/results/tree-source-structure/pages.json --notes middleware/results/tree-source-structure/attribution-notes.json
python3 middleware/agreement/fields_after_the_figure.py --work <work dir> --classes middleware/results/tree-source-structure/pages.json     # after the figure; --write-notes wrote attribution-notes.json
python3 middleware/agreement/make_freeze.py check middleware/results/tree-source-structure/freeze.json --head 1cf8cd09f7 --fleet <fleet dir>
```
