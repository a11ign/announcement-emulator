# The agreement measurement: the rules, fixed before the first fleet capture of A11-208

This file, `pages.json`, the runtime, the sample suite's corpus test and the scripts that make the figure (`agreement/measure.py` and the others `freeze.json` names) are committed, and
`freeze.json` names their git objects, before any page is captured on the fleet. `agreement/make_freeze.py check` fails if any of them has moved since, or if a fleet capture is dated
before the freeze.

## Which pages

`agreement/select_pages.py`, run once, gave `pages.json`:

1. Candidates are the corpus pages (`q3/results/corpus.json`) that were comparable in A11-166's freeze run: its `old60` set (the 60 pages of the earlier corpus, which that run measured again), less
   the seven that `q3/results/gate/measure-old60-freeze.txt` lists as not comparable, faulted or unstable. 53 candidates.
2. They are put in the order of the SHA-256 of their address read as a number, so that the order is a function of the address alone.
3. Each in turn is opened in a browser, and kept if its DOM, and nothing else, has at least ten tab stops and a text field (`agreement/dom_check.mjs`).
4. The first six that are kept are the sample. The one candidate that failed the check (`design-patterns.service.justice.gov.uk/components/filter/`, no text field) is listed in `pages.json`.

No page was read, on either side, before this rule ran. The emulator was fitted to these pages while A11-155 to A11-176 were done; they are **not held out** and the write-up says so.

## What the fleet is asked, and what the Playwright test does

The fleet is asked through the route A11-166 used, `q3/fleet_capture.mjs`, which sends the worker's own `/capture` body, with `--typing-dialog` added: the worker's `probeFocus`, `probeNavigation`,
`probeFocusContext` and `probeFocusReveal`, with `probeForms` off for third-party pages, and `probeTyping` and `probeDialog`. Nothing on any box is changed (A11-205).

The corpus test (`middleware/sample-suite/tests/corpus/corpus.spec.ts`) takes the steps of three of the worker's probes as ordinary Playwright calls. The probes were read in
`screenreader-worker` at `5cfcc5a` (the checkout on the control plane's machine; the boxes serve code hash `25bb45d9b38d7a62`, which `pnpm run fleet:status` prints and which is the same on the three boxes used):

| the worker's probe | what it does | the corpus test |
|---|---|---|
| `probeFocusOrder` (`capture-probes.mjs:1935`) | anchors to the top, blurs the focused element, presses Tab and asks NVDA to repeat the focus, until the last three stops equal the first three, 150 presses at most | blurs the active element, presses Tab, notes the active element, until the last three equal the first three, 150 at most |
| `probeDialogEscape` (`:3325`) | presses Escape twice where the walk ended | presses Escape twice |
| `probeTypedFeedback` (`:3180`) | goes to the first edit field, types `123456` | clicks the first visible text field, types `123456` |

The fleet does not say what the keys themselves made NVDA say: it records what NVDA says when asked to repeat the focus (NVDA+Tab) after each Tab. So the prediction of a stop is, for this measurement
only, what NVDA says when asked to repeat the focus on the node the page's `focusin` names (`ANNOUNCEMENT_EMULATOR_REPORT_FOCUS=1` makes the runtime also record it as `repeatFocus`).
The speech the middleware attaches to a test is what the focus event itself says; the two are different strings, and the write-up shows both.

## The boxes, and the runs

Boxes: `fleet:status` (read-only) on the control plane's machine, taking the largest group that agrees on the browser and the Windows build and matches the emulator's Chrome milestone:
`a11y-worker-13`, `-14` and `-16` (Edge 155.0.4283.62, Windows build 26300.9711). The fleet as a whole does not agree (eleven boxes are on Edge 156, one is on an older Windows), and nothing is
converged: A11-205 freezes it. Each page is captured twice, on two different boxes; the passive middleware is run twice on this machine, close in time to the captures. History stays on, so
`visited` misses are expected and attributed as the Gate attributed them.

## The figure

`agreement/measure.py` (definitions in its header): by channel and by shape, the passive predictions against the fleet, beside the fleet against itself and the passive runs against each other.
