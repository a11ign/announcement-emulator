# @a11ign/foresay (a preview: private, published nowhere)

Predicts what the NVDA screen reader would say, built on NVDA's open-source code. Not affiliated with NV Access.

Playwright middleware. It latches onto the tests you already have and attaches, to each test in Playwright's report, **predicted NVDA speech**: what the announcement emulator
predicts NVDA would say while the test ran. No test is written twice.

**Predicted NVDA speech is advisory. It is not a reading of NVDA, and it is never evidence** (a11ign ADR 0047, Decision 2). It is the emulator's answer from Chromium's accessibility
tree and NVDA's own Python; the write-up (`docs/playwright-middleware-spike.md`) has the rate at which it agreed with a real NVDA on the same actions, and what it leaves out.

## Setup

```sh
npm i -D @playwright/test @a11ign/foresay@preview   # the preview: no release is on npm yet (the package stays private until a person chooses to publish), and every release is published under the `preview` tag, so a bare `npm i -D @a11ign/foresay` has no `latest` to resolve
npx playwright install chromium               # Playwright's own Chromium: the browser your tests, and the middleware, run in. Not `--only-shell`: see below
npx foresay install             # downloads the pinned, checksummed runtime bundle into a cache, as `npx playwright install` does for browsers
```

Until the first release nothing is on npm: install the tarball `npm pack` makes in `middleware/`, with the bundle served as a mirror (`middleware/release/install-check.sh` does exactly that).

`install` downloads the bundle from **the GitHub Release of the version you installed** (`<repository>/releases/download/v<version>/`, the `repository` of this package's `package.json`), refuses it unless its sha256 is the one this
package's `pins.json` names (nothing is unpacked, and the download is deleted), and unpacks it into the cache. A team that cannot reach github.com mirrors the Release: see `ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST` below.

Then **one line** in `playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";
import { withAnnouncements } from "@a11ign/foresay";

export default defineConfig(withAnnouncements({ /* your config, as it was */ }));
```

or **no line at all**: `npx foresay test [playwright test arguments]` writes a config beside yours that imports it and wraps it, runs `playwright test` with it, and removes it.

Nothing else changes: not a test, not a fixture, not another part of the config.

## The browser is Playwright's

The middleware downloads no browser and bundles none: it runs in **the Chromium your Playwright version installs** (`npx playwright install chromium`, the revision your `@playwright/test`'s
`playwright-core/browsers.json` names). The runtime bundle holds no browser and no browser library; `bundle/check_no_browser.py` fails the build on one. A chromium project is launched with
`--force-renderer-accessibility` and `--remote-debugging-port`, and nothing else: no extension is loaded, no `channel` is named and no default argument of Playwright's is switched off. Firefox and WebKit projects are left alone.

**The tree is read through the browser's DevTools port** (`Accessibility.getFullAXTree` and `DOMSnapshot`, A11-229), on Linux, macOS and Windows alike, and in whichever browser a launch gives: the headless shell
that Playwright 1.49 and later runs for a headless launch with no `channel`, the full Chromium, a branded Chrome or Edge, a browser at an `executablePath` you chose. The contexts a suite opens itself (`browser.newContext()`)
are read like any other page. A team's own `ANNOUNCEMENT_EMULATOR_TREE` setting from before there was one source is ignored, with one line that says so.

**What your config needs.** Only the one line (or none). Two things about the browser matter:

- **Install a Chromium.** `npx playwright install chromium` installs the full browser and the headless shell (`--only-shell` installs only the shell, which is enough). On Linux CI use `npx playwright install --with-deps chromium`,
  Playwright's own route to the browser's system libraries.
- **A `channel` or an `executablePath` you chose is yours.** The middleware does not change it.
- The team's Playwright is looked for from the working directory, then from where this package is installed.

`npx foresay doctor` prints your Playwright version, the Chromium build its `browsers.json` names, which of the full browser and the headless shell are installed, whether that build is on
the supported list below, and where the tree comes from.

## Supported Playwright versions

Predicted speech agrees with a real NVDA at a rate that depends on the browser, so the rate is **measured for each Chromium build** and listed in [`supported-versions.json`](supported-versions.json), which ships in the package:
each entry is a Chromium build, the Playwright versions that ship it, and the measured agreement for the DevTools tree on each operating system (`devtools-linux`, `devtools-macos`).

A version that is not on the list still runs and still gets predicted speech. Its report says **`agreement not measured for Chromium <build>`**, in the text, the JSON attachment and `run.json`; so does a listed build
with no figure for the operating system the run used. A listed build says `agreement measured for Chromium <build> (Playwright <versions>), devtools: <rate>% of <units> units on <n> held-out pages, <date>; the fleet agrees with itself on <ceiling>% (<figure>)`,
and each predicted utterance in the report names the rate of its shape (`NAME + ROLE: 86.0% of 57`), with `, low confidence` where the list marks the shape weak.

This is a **preview, improved every release, with no fixed gate**: each release prints the rate it measured, and a round is judged by the figures going up. The figure the list holds is the **held-out** one: measured on pages the emulator was not fitted against,
with the number of pages it could compare, and with the **ceiling**, the fleet's NVDA read twice against itself on the same units (the oracle's own noise: a rate above it cannot be told from that noise). A shape is **low confidence** when
the upper end of the 95% (Wilson) interval of its rate is below the reading's overall rate and some of its misses are the middleware's and not the oracle's (`results/agreement-round-1/rule.md`).

The list starts with the current Playwright release and the one before it: Playwright 1.64.x (Chromium 156.0.8078.4) and 1.63.0 (Chromium 153.0.8010.12). Round one ([`results/agreement-round-1/README.md`](results/agreement-round-1/README.md)) measured them (Playwright 1.64.1 and 1.63.0 were run; 1.64.0 ships the same Chromium and was not) on six held-out pages
(five were comparable on the Linux rows, four on macOS 153) against the fleet's NVDA, by the method of [`results/agreement-round-1/rule.md`](results/agreement-round-1/rule.md), which adopts [`results/playwright-versions/rule.md`](results/playwright-versions/rule.md) unchanged. Measured 2026-10-25:

| Playwright | Chromium | source | agreement | units | pages | the fleet against itself | date |
|---|---|---|---|---|---|---|---|
| 1.64.1 (1.64.0 not run) | 156.0.8078.4 | DevTools, Linux | 49.5% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.64.1 (1.64.0 not run) | 156.0.8078.4 | DevTools, macOS | 72.2% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | DevTools, Linux | 48.7% | 1046 | 5 | 99.9% | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | DevTools, macOS | 44.6% | 945 | 4 | 99.9% | 2026-10-25 |

Those are the readings of the DevTools tree as it was before A11-229 filled its missing fields and read it incrementally; the companion extension, which was the Linux source then and measured 75.0% and 75.7% on the same pages, has been removed, and its readings stay under `results/` as the record. A11-229's last step measures the tree again, under a rule frozen before the captures, and replaces these figures.

Five pages is a small population, and the rates move with a single page: on two of the five (caselaw and Sheffield) the passive browser's first stop is a cookie banner's button where the fleet's is the page's own first control; on one page the DevTools tree
on this host loses most of the page's nodes (the 49.5% and 48.7%). The write-up has the misses by cause and shape. On the six pages the emulator was fitted against (not held out; the like-for-like comparison with the previous release's figures) the same readings are
79.3% to 86.8%: up against the previous round on DevTools on Linux and at 153 on macOS, down on macOS at 156 (-0.7). Windows has no figure: it reads "not measured". To add a Playwright release, measure its Chromium by that rule and add it to the list.

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
starts it and reads its JSON lines and **never imports it** (the runtime is GPL-3.0, ADR 0047 Decision 3). The test's browser reports to the runtime through its DevTools port alone: the accessibility tree (read again from what changed after each change, `runtime/cdp.py`, `runtime/incremental.py`,
`runtime/axtree.py`) and the page's own focus moves, keys, live-region changes, dialogs and error messages.

## The runtime bundle is lean

`npx foresay install` downloads one archive, checks its sha256 against the pin in the package and unpacks it with the host's `tar -xf` (A11-231). What is in it:

- **Python**: python-build-standalone's `install_only_stripped` build (3.13), its standard library as bytecode, and only the modules the runtime was seen to import; the `encodings` package whole (a page's charset picks a codec at run time);
  the packages NVDA's source needs. No tests, `idlelib`, `tkinter`, `ensurepip`, `turtle`, headers, static libraries or `pip`.
- **NVDA's source**, one tree (`nvda-src/source`): the files the runtime was seen to import or read, `locale/en`, and the pinned CLDR names (`cldr.dic`) put over NVDA's own file in place. No other locale, no docs, images or tests, no second copy.
- **This repository's runtime** (the emulator, the sweep, the runtime process, `emu/tables.json`); it carries no browser extension (A11-229). The Chromium source files `emu/tables.json` was generated from are not shipped:
  nothing reads them at run time.
- No browser, no browser library and no extension (`bundle/check_no_browser.py`, with `bundle/check_no_extension.py`).

**Measured** (CI, `middleware-spike.yml`; MB of 10^6 bytes; the spike is A11-208's bundle, which had Chrome and a full Python, and A11-230's had no browser):

| MB, unpacked | spike (linux-x64) | A11-230 linux-x64 | **lean linux-x64** | A11-230 darwin-arm64 | **lean darwin-arm64** |
|---|---|---|---|---|---|
| Chrome, and the libraries it needs | 411.0 | 0 | 0 | 0 | 0 |
| Python | 278.0 | 272.6 | **37.2** | 76.9 | **23.1** |
| &nbsp;&nbsp;interpreter | | 240.3 | 31.6 | 45.9 | 17.6 |
| &nbsp;&nbsp;standard library | | 17.0 | 4.4 | 14.1 | 4.4 |
| &nbsp;&nbsp;packages | | 15.3 | 1.2 | 17.0 | 1.0 |
| NVDA (the spike's and A11-230's hold it twice) | 149.0 | 146.1 | **2.6** | 146.1 | **2.6** |
| Chromium sources | | 1.2 | 0 | 1.2 | 0 |
| This repository's runtime, the rest (A11-230's also holds the companion extension, 14 KB) | | 0.4 | 0.4 | 0.4 | 0.4 |
| **Total unpacked** | **838.0** | **420.4** | **40.3** | **224.7** | **26.1** |
| **Archive** | 298.0 (gz) | 111.7 (gz) | **10.2** (xz) | 63.2 (gz) | **7.5** (xz) |

The same bundle as gzip, xz and zstd (archive MB; median of three unpacks with the host's `tar -xf`): linux-x64 14.9 (0.28 s), **10.2 (0.65 s)**, 11.3 (0.09 s); darwin-arm64 10.3 (0.26 s), **7.5 (0.57 s)**, 8.3 (0.13 s).
The interpreter is 31.6 MB of the 40.3 on linux: python-build-standalone links OpenSSL, SQLite and the rest into it, and the stripped build still holds its symbol table (`strip --strip-unneeded` on it leaves an interpreter that fails to start with a symbol lookup error). Two builds of each platform's bundle are the same bytes (CI checks both).

**It is traced, not guessed.** `bundle/keep/<platform>.txt` lists every file of `python/` and `nvda-src/` that a run read. `bundle/trace.sh <platform>` makes it: it runs every recorded session under `runtime/fixtures/`
(with sweeps, without, and with `--report-focus`) and the sample suite's offline project live, in the unpruned layout, with `runtime/import_trace.py` on (`ANNOUNCEMENT_EMULATOR_IMPORT_TRACE=<file>`
records the files imported or opened, and the imports that failed, which NVDA's own `try: import … except ImportError` would otherwise hide), and adds what NVDA's Chrome system tests read (`keep/nvda-system-tests.txt`,
made on Linux by `trace.sh --system-tests`). `bundle/lean.py` prunes to it, and `build.sh` refuses to build without it. **When the runtime starts to import or read something new, run `trace.sh <platform>` and commit
the list.** CI says when: the `demo` job runs the sample suite in the lean bundle and in the full layout with the trace on and fails on a file or import the lean run wanted and could not find (`compare_bundles.py misses`),
and the `trace` job fails when a run reads a file the committed list lacks.

**Unchanged behaviour.** The `transcripts` job (A11-260: it was `bundle-identical`, and takes the `bundle` job's full layout as an artifact instead of building it again) replays every recorded session under the full layout and under the lean bundle, with sweeps, without and with `--report-focus`, on each platform it builds (both in the nightly run, Linux in a pull request), and fails unless the outputs
are the same bytes (the clock, `ms`, is left out, because two runs of one layout differ in it). `demo` also reports, test by test, where the live suite's predicted speech or flags differ between the lean bundle and the full layout (`compare_live.py`; a report and not a failure, because a live run's timing moves a quick test's last event).

**Compression** is measured on every build (`bundle/sizes.py formats`): gzip, xz and zstd, each archive's size and its median unpack time with the host's `tar -xf`. The bundle ships in the smaller of xz and zstd that unpacks
in 5 s or less on both runners; `bundle-format` fails if `build.sh`'s default is any other. **`install` needs a `tar` that reads xz**: macOS's does, and a GNU tar needs the `xz` program (`xz-utils`), which a minimal container
such as `ubuntu:24.04` lacks (it has no zstd either; `bundle-format` reports what that image's tar does). The same inputs make the same archive (`mktar.py`): the release's `release-bundles.yml` builds each linux bundle twice and compares the bytes.

## Environment

| variable | |
|---|---|
| `ANNOUNCEMENT_EMULATOR_PATH` | where the bundle is cached (default `~/.cache/announcement-emulator`, `~/Library/Caches/announcement-emulator` on macOS) |
| `ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST` | a mirror of the Releases, for a team that cannot reach github.com, as `PLAYWRIGHT_DOWNLOAD_HOST` is for browsers. It replaces `https://github.com/<owner>/<repository>/releases/download`: `install` fetches `<host>/v<version>/<file>`, so that one mirror holds every version a team pins. Fill it with `gh release download v<version> --dir <mirror>/v<version>`. The sha256 is checked against `pins.json` whatever the source, so a mirror cannot change what is installed |
| `ANNOUNCEMENT_EMULATOR_BUNDLE` | use this unpacked bundle instead of the cache |
| `ANNOUNCEMENT_EMULATOR_IMPORT_TRACE` | a file the runtime appends the files it read from the bundle to, and the imports that failed (`bundle/trace.sh` and the CI miss check use it; unset, nothing is recorded) |
| `ANNOUNCEMENT_EMULATOR_SWEEPS=0` | no sweeps |
| `ANNOUNCEMENT_EMULATOR_TREE` | ignored: the DevTools port is the only tree source, on every operating system (A11-229). A run that finds it set prints one line saying so, and goes on |

## Releases

Each version is a GitHub Release `v<version>` of this repository (`middleware/release/`, `.github/workflows/release-bundles.yml`). It carries:

- the runtime bundle of each platform it supports (`linux-x64`, `linux-arm64`, `darwin-arm64`), `announcement-emulator-bundle-<platform>.tar.xz`, built twice and compared (the linux builds must be the same bytes both times; darwin's is reported, because the macOS linker's UUID is not controlled). `linux-arm64` is built on GitHub's arm runners and its keep list is checked there; no agreement has been measured on it, so its speech is as unmeasured as any platform's that `supported-versions.json` has no figure for;
- `SHA256SUMS`, the sum of every bundle, which is also what the `pins.json` of that version's package names: `middleware/release/after-version.sh` writes it into the release commit from the very files attached to the Release, and fails the release if the two differ;
- notes that carry **the measured agreement of that version** (per Chromium build and operating system, with the units, the date and, where the figure has them, the pages and the rate of each announcement shape) and **the Playwright versions it supports**, as `supported-versions.json` lists them.

**Nothing is published yet.** The name, the licence and the NV Access question are decided (`docs/release-decisions.md`), and the package stays `"private": true` in `package.json` until a person chooses to publish a first release.
That field is the one switch between a dry run and a release, and it has two guards behind it: `.github/workflows/release.yml` stops at its `plan` job with a dry-run message while the package is private (no bundle is built, nothing is
versioned), and the org's release workflow never publishes a private package. Until then `.github/workflows/release-dry-run.yml` rehearses a release on every pull request that changes one, and nightly: it builds the bundles,
versions this branch's changesets on a scratch copy, packs the package and installs it with its bundle through the mirror variable on each platform, and shows every file with its size and sum. The same rehearsal runs on your
machine with `middleware/release/dry-run.sh <release-files> <out>` (and `install-check.sh`) after `release-bundles.yml`'s legs are gathered by `middleware/release/gather.sh`.

**What a release does, once the field is dropped.** `release.yml` runs on a push to `main` that carries a changeset no tag has consumed (there is no dispatch, on purpose). It builds the bundles (`release-bundles.yml`) and runs the full spike
(`middleware-spike.yml`: every platform, every row), and when both pass it calls a11ign/toolchain's `release-per-merge.yml`: the version is whatever the pending changesets compute, `after-version.sh` writes `pins.json` (the sums of the very
files attached) and the measured agreement into the release commit, the package is published to npm with provenance by **trusted publishing** (OIDC, no stored token) under the dist-tag **`preview`**, never `latest`, and the tag
`v<version>` and its GitHub Release are made with the bundles and `SHA256SUMS` attached. The first `latest` needs NV Access to have been asked first (`docs/release-decisions.md`, "NV Access"); moving to it is an edit of `dist-tag` in
`release.yml`. The `-preview.N` version suffix that decision defines is not built: the org's release workflow takes plain `MAJOR.MINOR.PATCH` only, so the first versions are plain `0.x.y` under the `preview` tag.

**Before the first publish, a person sets up npm's side:** the `npm-publish` GitHub environment of this repository (limited to `main`), and a trusted-publisher entry for `@a11ign/foresay` naming repository `a11ign/announcement-emulator`
(the repository's name until it is renamed, and the entry names it too), workflow `release.yml` and environment `npm-publish`. The workflow's file name is part of that entry: renaming `release.yml` breaks the publish.

## Licence

**The package is Apache-2.0** (`LICENSE`, with a `NOTICE`; `license` in `package.json`). It holds no file of the runtime: the tarball is `dist`, `pins.json`, `supported-versions.json`, the changelog, this README, `LICENSE` and `NOTICE`, and a test (`src/package-files.test.ts`) fails if a file of the runtime gets into it. The package starts the runtime as a separate program and exchanges JSON lines with it over a pipe; it copies nothing out of the runtime and rewrites nothing in it.

**The runtime is GPL-3.0-or-later.** It is a separate download (`npx foresay install`), never part of the npm package, and it is a combined work with NVDA's code (GPL-2.0-or-later). Its bundle carries the GPL text (`LICENSE`), NVDA's licence file (`nvda-src/copying.txt`), and `NOTICES`: the offer of the corresponding source and the notices of the other components (Chromium's mapping tables, the CLDR names, Python and its packages). `bundle.json` says `"license": "GPL-3.0-or-later"`. Its source is this repository (`../LICENSE`), at the commit `bundle.json` names.

The name, the licence and the NV Access requirement were decided by the chairman on 2026-10-27: see `../docs/release-decisions.md`, "Decisions".
