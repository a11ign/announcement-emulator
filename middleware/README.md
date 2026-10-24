# @a11ign/announcement-emulator (a spike: private, published nowhere)

Playwright middleware. It latches onto the tests you already have and attaches, to each test in Playwright's report, **predicted NVDA speech**: what the announcement emulator
predicts NVDA would say while the test ran. No test is written twice.

**Predicted NVDA speech is advisory. It is not a reading of NVDA, and it is never evidence** (a11ign ADR 0047, Decision 2). It is the emulator's answer from Chrome's accessibility
tree and NVDA's own Python; the write-up (`docs/playwright-middleware-spike.md`) has the rate at which it agreed with a real NVDA on the same actions, and what it leaves out.

## Setup

```sh
npm i -D @playwright/test <this package>      # this spike: the tarball `npm pack` makes in middleware/
npx announcement-emulator install             # downloads the pinned, checksummed runtime bundle into a cache, as `npx playwright install` does for browsers
```

Then **one line** in `playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";
import { withAnnouncements } from "@a11ign/announcement-emulator";

export default defineConfig(withAnnouncements({ /* your config, as it was */ }));
```

or **no line at all**: `npx announcement-emulator test [playwright test arguments]` writes a config beside yours that imports it and wraps it, runs `playwright test` with it, and removes it.

Nothing else changes: not a test, not a fixture, not another part of the config. Playwright's own browsers are not used for chromium projects: the bundle's Chrome for Testing (155) is launched
instead, with `--force-renderer-accessibility`, `--load-extension`, `--allowlisted-extension-id`, `--disable-features=DisableLoadExtensionCommandLineSwitch` (Chrome 155 ignores `--load-extension`
without it) and `--remote-debugging-port`, and without Playwright's `--disable-extensions`. Firefox and WebKit projects are left alone.

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

## Licence

Undecided, and a decision the spike leaves to a person: the package is `UNLICENSED` and private. The runtime in the bundle is GPL-3.0 (`../LICENSE`).
