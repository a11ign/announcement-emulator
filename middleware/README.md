# @a11ign/announcement-emulator (a spike: private, published nowhere)

Playwright middleware. It latches onto the tests you already have and attaches, to each test in Playwright's report, **predicted NVDA speech**: what the announcement emulator
predicts NVDA would say while the test ran. No test is written twice.

**Predicted NVDA speech is advisory. It is not a reading of NVDA, and it is never evidence** (a11ign ADR 0047, Decision 2). It is the emulator's answer from Chromium's accessibility
tree and NVDA's own Python; the write-up (`docs/playwright-middleware-spike.md`) has the rate at which it agreed with a real NVDA on the same actions, and what it leaves out.

## Setup

```sh
npm i -D @playwright/test <this package>      # this spike: the tarball `npm pack` makes in middleware/
npx playwright install chromium               # Playwright's own Chromium: the browser your tests, and the middleware, run in. Not `--only-shell`: see below
npx announcement-emulator install             # downloads the pinned, checksummed runtime bundle into a cache, as `npx playwright install` does for browsers
```

Then **one line** in `playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";
import { withAnnouncements } from "@a11ign/announcement-emulator";

export default defineConfig(withAnnouncements({ /* your config, as it was */ }));
```

or **no line at all**: `npx announcement-emulator test [playwright test arguments]` writes a config beside yours that imports it and wraps it, runs `playwright test` with it, and removes it.

Nothing else changes: not a test, not a fixture, not another part of the config.

## The browser is Playwright's

The middleware downloads no browser and bundles none: it runs in **the Chromium your Playwright version installs** (`npx playwright install chromium`, the revision your `@playwright/test`'s
`playwright-core/browsers.json` names). The runtime bundle holds no browser and no browser library; `bundle/check_no_browser.py` fails the build on one. A chromium project is launched with
`--force-renderer-accessibility` and `--remote-debugging-port`, and, where the companion extension is the tree source, `--load-extension`, `--allowlisted-extension-id`,
`--disable-features=DisableLoadExtensionCommandLineSwitch` (without it a recent Chrome ignores `--load-extension`) and without Playwright's `--disable-extensions`. Firefox and WebKit projects are left alone.

**What your config needs.** Only the one line (or none). Two things about the browser matter:

- **Install the full Chromium, not only the headless shell.** Since Playwright 1.49 a headless launch with no `channel` runs `chromium-headless-shell`, which loads no extension.
  `npx playwright install chromium` installs both (`--only-shell` installs only the shell). Where the extension is the tree source and your launch is headless and left to Playwright (no `channel`, no `executablePath`),
  the middleware adds `channel: "chromium"`, which runs the full Chromium in the new headless mode. On Linux CI use `npx playwright install --with-deps chromium`, Playwright's own route to the browser's system libraries.
- **A `channel` or an `executablePath` you chose is yours.** The middleware does not change it. It cannot know whether that browser loads the extension, so it tries it: if the extension has said nothing
  five seconds after the browser's first page (`ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT`, in seconds), the runtime reads the trees through the DevTools port from then on, in whatever Chromium that is, and each report says
  so and why. Speech for what ran before the switch is lost. A source set with `ANNOUNCEMENT_EMULATOR_TREE` is never switched. Where it is known beforehand that the extension cannot load (only the headless shell is installed,
  or a Playwright older than 1.49 launched headless), the DevTools port is used from the start. Nothing breaks: the tests run as they did.
  The tree source is one for the whole run, and a project that is known not to load the extension puts every project on the DevTools source.
- The team's Playwright is looked for from the working directory, then from where this package is installed. The channel the middleware adds is visible to a test as `testInfo.project.use.channel`.

`npx announcement-emulator doctor` prints your Playwright version, the Chromium build its `browsers.json` names, which of the full browser and the headless shell are installed, whether that build is on
the supported list below, and the tree source the automatic pick takes.

## Supported Playwright versions

Predicted speech agrees with a real NVDA at a rate that depends on the browser, so the rate is **measured for each Chromium build** and listed in [`supported-versions.json`](supported-versions.json), which ships in the package:
each entry is a Chromium build, the Playwright versions that ship it, and the measured agreement for each tree source and operating system (`extension-linux`, `devtools-linux`, `devtools-macos`).

A version that is not on the list still runs and still gets predicted speech. Its report says **`agreement not measured for Chromium <build>`**, in the text, the JSON attachment and `run.json`; so does a listed build
with no figure for the tree source the run used. A listed build says `agreement measured for Chromium <build> (Playwright <versions>), <source>: <rate>% of <units> units on <n> held-out pages, <date>; the fleet agrees with itself on <ceiling>% (<figure>)`,
and each predicted utterance in the report names the rate of its shape (`NAME + ROLE: 86.0% of 57`), with `, low confidence` where the list marks the shape weak.

This is a **preview, improved every release, with no fixed gate**: each release prints the rate it measured, and a round is judged by the figures going up. The figure the list holds is the **held-out** one: measured on pages the emulator was not fitted against,
with the number of pages it could compare, and with the **ceiling**, the fleet's NVDA read twice against itself on the same units (the oracle's own noise: a rate above it cannot be told from that noise). A shape is **low confidence** when
the upper end of the 95% (Wilson) interval of its rate is below the reading's overall rate and some of its misses are the middleware's and not the oracle's (`results/agreement-round-1/rule.md`).

The list starts with the current Playwright release and the one before it: Playwright 1.64.x (Chromium 156.0.8078.4) and 1.63.0 (Chromium 153.0.8010.12). Round one ([`results/agreement-round-1/README.md`](results/agreement-round-1/README.md)) measured them (Playwright 1.64.1 and 1.63.0 were run; 1.64.0 ships the same Chromium and was not) on six held-out pages
(five were comparable on the Linux rows, four on macOS 153) against the fleet's NVDA, by the method of [`results/agreement-round-1/rule.md`](results/agreement-round-1/rule.md), which adopts [`results/playwright-versions/rule.md`](results/playwright-versions/rule.md) unchanged. Measured 2026-10-25:

| Playwright | Chromium | source | agreement | units | pages | the fleet against itself | date |
|---|---|---|---|---|---|---|---|
| 1.64.1 (1.64.0 not run) | 156.0.8078.4 | extension, Linux | 75.0% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.64.1 (1.64.0 not run) | 156.0.8078.4 | DevTools, Linux | 49.5% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.64.1 (1.64.0 not run) | 156.0.8078.4 | DevTools, macOS | 72.2% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | extension, Linux | 75.7% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | DevTools, Linux | 48.7% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | DevTools, macOS | 44.6% | 945 | 4 | 99.9% | 2026-10-25 |

Five pages is a small population, and the rates move with a single page: on two of the five (caselaw and Sheffield, nine in ten of the extension's misses) the passive browser's first stop is a cookie banner's button where the fleet's is the page's own first control; on one page the DevTools tree
on this host loses most of the page's nodes (the 49.5% and 48.7%). The write-up has the misses by cause and shape. On the six pages the emulator was fitted against (not held out; the like-for-like comparison with the previous release's figures) the same readings are
79.3% to 86.8%: up against the previous round on DevTools on Linux and at 153 on macOS, down on macOS at 156 (-0.7) and on the 153 extension, within on the 156 extension. Windows has no figure: it reads "not measured". To add a Playwright release, measure its Chromium by that rule and add it to the list.

## What you get

For each test, two attachments (the HTML, JSON and any other report that is built when the run ends shows them):

- `predicted NVDA speech`: the speech in time order (the page load, each focus move, the echo of typed characters, live-region changes), each sweep, and the flags;
- `predicted-nvda-speech.json`: the same as data.

At each new state the test reaches (a document, a route change, a dialog) the emulator's structural sweep runs over a snapshot of the page, with no test code: headings, landmarks, form fields,
graphics, links, lists, frames. It sends no key to your browser.

Three flags, with rules that are written in `runtime/flags.py`, and shown as annotations on the test:

| flag | raised when |
|---|---|
| `focus-without-name` | focus lands on a control that has no accessible name, and what is predicted for it has no name in it |
| `silent-dialog` | a dialog opens and nothing is predicted for it (no focus into it, no live-region speech) within a second |
| `unheard-error` | an error message appears for a field and its words are in none of the speech predicted within a second |

## How it works

Three processes. Playwright's main process holds the reporter, which starts one **runtime** for each worker. The runtime is a separate program in the bundle (Python, NVDA's source, the emulator); this package
starts it and reads its JSON lines and **never imports it** (the runtime is GPL-3.0, ADR 0047 Decision 3). The test's browser reports to the runtime through the companion extension (the accessibility tree,
after each change) and through the DevTools port (the page's own focus moves, keys, live-region changes, dialogs and error messages).

## Environment

| variable | |
|---|---|
| `ANNOUNCEMENT_EMULATOR_PATH` | where the bundle is cached (default `~/.cache/announcement-emulator`, `~/Library/Caches/announcement-emulator` on macOS) |
| `ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST` | where `install` fetches the bundle from. This spike has none: nothing is published |
| `ANNOUNCEMENT_EMULATOR_BUNDLE` | use this unpacked bundle instead of the cache |
| `ANNOUNCEMENT_EMULATOR_SWEEPS=0` | no sweeps |
| `ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT` | seconds the runtime waits for an extension that has said nothing, after the first page, before it reads the trees through the DevTools port (default 5; 0 never) |
| `ANNOUNCEMENT_EMULATOR_TREE` | `extension` or `devtools`: where the accessibility tree comes from. Unset, the middleware picks: the extension where the browser gives it a desktop tree and it is expected to load (Linux, Windows), the DevTools port on macOS and wherever the extension cannot be expected to load |

## Licence

Undecided, and a decision the spike leaves to a person: the package is `UNLICENSED` and private. The runtime in the bundle is GPL-3.0 (`../LICENSE`).
