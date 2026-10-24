# Playwright middleware spike (row A11-208)

**Status: a spike, finished. Recommendation: @@RECOMMENDATION@@**

Everything on this page is **predicted NVDA speech**: what the announcement emulator says NVDA would say. It is advisory, it is not a reading of NVDA, and it is never evidence (a11ign ADR 0047, Decision 2).
Nothing here fills an a11ign evidence field, and nothing is published: the package is private, the bundle is a workflow artifact, no registry has been written to.

**Where a number comes from is marked on the number**, as in `docs/announcement-emulator-spike.md`: *measured* (run in this row; output committed under `middleware/results/` or printed by the CI run named), *quoted* (copied, not re-run) or *not checked*.

@@SUMMARY@@

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

@@Q2@@

## Q3. Automatic sweeps

@@Q3@@

## Q4. Output

@@Q4@@

## Q5. Agreement with the fleet

@@Q5@@

## Q6. Cost

@@Q6@@

## Q7. Packaging, the Playwright way

@@Q7@@

## What a real version needs, and the recommendation

@@RECOMMEND@@

## Decisions made without a person

@@DECISIONS@@

## Reproduction

@@REPRO@@
