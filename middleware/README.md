# @a11ign/announcement-emulator (a spike: private, published nowhere)

Playwright middleware. It latches onto the tests you already have and attaches, to each test in Playwright's report, **predicted NVDA speech**: what the announcement emulator
predicts NVDA would say while the test ran. No test is written twice.

**Predicted NVDA speech is advisory. It is not a reading of NVDA, and it is never evidence** (a11ign ADR 0047, Decision 2). It is the emulator's answer from Chromium's accessibility
tree and NVDA's own Python; the write-up (`docs/playwright-middleware-spike.md`) has the rate at which it agreed with a real NVDA on the same actions, and what it leaves out.

## Setup

```sh
npm i -D @playwright/test @a11ign/announcement-emulator   # the working name: the name and the licence are undecided (docs/release-decisions.md), and nothing is published until they are
npx playwright install chromium               # Playwright's own Chromium: the browser your tests, and the middleware, run in. Not `--only-shell`: see below
npx announcement-emulator install             # downloads the pinned, checksummed runtime bundle into a cache, as `npx playwright install` does for browsers
```

Until the first release nothing is on npm: install the tarball `npm pack` makes in `middleware/`, with the bundle served as a mirror (`middleware/release/install-check.sh` does exactly that).

`install` downloads the bundle from **the GitHub Release of the version you installed** (`<repository>/releases/download/v<version>/`, the `repository` of this package's `package.json`), refuses it unless its sha256 is the one this
package's `pins.json` names (nothing is unpacked, and the download is deleted), and unpacks it into the cache. A team that cannot reach github.com mirrors the Release: see `ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST` below.

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
with no figure for the tree source the run used. A listed build says `agreement measured for Chromium <build> (Playwright <versions>), <source>: <rate>% of <units> units, <date>`.

The list starts with the current Playwright release and the one before it: Playwright 1.64.x (Chromium 156.0.8078.4) and 1.63.0 (Chromium 153.0.8010.12). Each is measured by the method of [`results/playwright-versions/rule.md`](results/playwright-versions/rule.md), against the fleet's NVDA, on six real pages (not held out; a preview, with no target). Measured 2026-10-25:

| Playwright | Chromium | source | agreement | units | date |
|---|---|---|---|---|---|
| 1.64.0, 1.64.1 | 156.0.8078.4 | extension, Linux | 81.2% | 1072 | 2026-10-25 |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, Linux | 80.2% | 1072 | 2026-10-25 |
| 1.64.0, 1.64.1 | 156.0.8078.4 | DevTools, macOS | 85.1% | 960 | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | extension, Linux | 83.5% | 1072 | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | DevTools, Linux | 81.2% | 1072 | 2026-10-25 |
| 1.63.0 | 153.0.8010.12 | DevTools, macOS | 84.0% | 960 | 2026-10-25 |

The macOS rows are over four pages and the Linux rows over five (see the write-up), so they are not a comparison of the operating systems. Windows has no figure: it reads "not measured". To add a Playwright release, measure its Chromium by that rule and add it to the list.

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

## The runtime bundle is lean

`npx announcement-emulator install` downloads one archive, checks its sha256 against the pin in the package and unpacks it with the host's `tar -xf` (A11-231). What is in it:

- **Python**: python-build-standalone's `install_only_stripped` build (3.13), its standard library as bytecode, and only the modules the runtime was seen to import; the `encodings` package whole (a page's charset picks a codec at run time);
  the packages NVDA's source needs. No tests, `idlelib`, `tkinter`, `ensurepip`, `turtle`, headers, static libraries or `pip`.
- **NVDA's source**, one tree (`nvda-src/source`): the files the runtime was seen to import or read, `locale/en`, and the pinned CLDR names (`cldr.dic`) put over NVDA's own file in place. No other locale, no docs, images or tests, no second copy.
- **This repository's runtime** (the emulator, the sweep, the runtime process, `emu/tables.json`) and, until A11-229 removes it, the companion extension. The Chromium source files `emu/tables.json` was generated from are not shipped:
  nothing reads them at run time.
- No browser and no browser library (`bundle/check_no_browser.py`).

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
| This repository's runtime, the extension, the rest | | 0.4 | 0.4 | 0.4 | 0.4 |
| **Total unpacked** | **838.0** | **420.4** | **40.3** | **224.7** | **26.1** |
| **Archive** | 298.0 (gz) | 111.7 (gz) | **10.2** (xz) | 63.2 (gz) | **7.5** (xz) |

The same bundle as gzip, xz and zstd (archive MB; median of three unpacks with the host's `tar -xf`): linux-x64 14.9 (0.28 s), **10.2 (0.65 s)**, 11.3 (0.09 s); darwin-arm64 10.3 (0.26 s), **7.5 (0.57 s)**, 8.3 (0.13 s).
The interpreter is 31.6 MB of the 40.3 on linux: python-build-standalone links OpenSSL, SQLite and the rest into it, and the stripped build still holds its symbol table (`strip --strip-unneeded` on it leaves an interpreter that fails to start with a symbol lookup error). Two builds of each platform's bundle are the same bytes (CI checks both).

**It is traced, not guessed.** `bundle/keep/<platform>.txt` lists every file of `python/` and `nvda-src/` that a run read. `bundle/trace.sh <platform>` makes it: it runs every recorded session under `runtime/fixtures/`
(with sweeps, without, and with `--report-focus`) and the sample suite's offline project live with each tree source, in the unpruned layout, with `runtime/import_trace.py` on (`ANNOUNCEMENT_EMULATOR_IMPORT_TRACE=<file>`
records the files imported or opened, and the imports that failed, which NVDA's own `try: import … except ImportError` would otherwise hide), and adds what NVDA's Chrome system tests read (`keep/nvda-system-tests.txt`,
made on Linux by `trace.sh --system-tests`). `bundle/lean.py` prunes to it, and `build.sh` refuses to build without it. **When the runtime starts to import or read something new, run `trace.sh <platform>` and commit
the list.** CI says when: the `demo` job runs the sample suite in the lean bundle and in the full layout with the trace on and fails on a file or import the lean run wanted and could not find (`compare_bundles.py misses`),
and the `trace` job fails when a run reads a file the committed list lacks.

**Unchanged behaviour.** `bundle-identical` replays every recorded session under the full layout and under the lean bundle, with sweeps, without and with `--report-focus`, on both platforms, and fails unless the outputs
are the same bytes (the clock, `ms`, is left out, because two runs of one layout differ in it). `demo` also reports, test by test, where the live suite's predicted speech or flags differ between the lean bundle and the full layout (`compare_live.py`; a report and not a failure, because a live run's timing moves a quick test's last event).

**Compression** is measured on every build (`bundle/sizes.py formats`): gzip, xz and zstd, each archive's size and its median unpack time with the host's `tar -xf`. The bundle ships in the smaller of xz and zstd that unpacks
in 5 s or less on both runners; `bundle-format` fails if `build.sh`'s default is any other. **`install` needs a `tar` that reads xz**: macOS's does, and a GNU tar needs the `xz` program (`xz-utils`), which a minimal container
such as `ubuntu:24.04` lacks (it has no zstd either; `bundle-format` reports what that image's tar does). The same inputs make the same archive (`mktar.py`): CI builds the linux-x64 bundle twice and compares the bytes.

## Environment

| variable | |
|---|---|
| `ANNOUNCEMENT_EMULATOR_PATH` | where the bundle is cached (default `~/.cache/announcement-emulator`, `~/Library/Caches/announcement-emulator` on macOS) |
| `ANNOUNCEMENT_EMULATOR_DOWNLOAD_HOST` | a mirror of the Releases, for a team that cannot reach github.com, as `PLAYWRIGHT_DOWNLOAD_HOST` is for browsers. It replaces `https://github.com/<owner>/<repository>/releases/download`: `install` fetches `<host>/v<version>/<file>`, so that one mirror holds every version a team pins. Fill it with `gh release download v<version> --dir <mirror>/v<version>`. The sha256 is checked against `pins.json` whatever the source, so a mirror cannot change what is installed |
| `ANNOUNCEMENT_EMULATOR_BUNDLE` | use this unpacked bundle instead of the cache |
| `ANNOUNCEMENT_EMULATOR_IMPORT_TRACE` | a file the runtime appends the files it read from the bundle to, and the imports that failed (`bundle/trace.sh` and the CI miss check use it; unset, nothing is recorded) |
| `ANNOUNCEMENT_EMULATOR_SWEEPS=0` | no sweeps |
| `ANNOUNCEMENT_EMULATOR_EXTENSION_WAIT` | seconds the runtime waits for an extension that has said nothing, after the first page, before it reads the trees through the DevTools port (default 5; 0 never) |
| `ANNOUNCEMENT_EMULATOR_TREE` | `extension` or `devtools`: where the accessibility tree comes from. Unset, the middleware picks: the extension where the browser gives it a desktop tree and it is expected to load (Linux, Windows), the DevTools port on macOS and wherever the extension cannot be expected to load |

## Releases

Each version is a GitHub Release `v<version>` of this repository (`middleware/release/`, `.github/workflows/release-bundles.yml`). It carries:

- the runtime bundle of each platform it supports (`linux-x64`, `darwin-arm64`), `announcement-emulator-bundle-<platform>.tar.xz`, built twice and compared (the linux build must be the same bytes both times; darwin's is reported, because the macOS linker's UUID is not controlled);
- `SHA256SUMS`, the sum of every bundle, which is also what the `pins.json` of that version's package names: `middleware/release/after-version.sh` writes it into the release commit from the very files attached to the Release, and fails the release if the two differ;
- notes that carry **the measured agreement of that version** (per Chromium build and tree source, with the units, the date and, where the figure has them, the pages and the rate of each announcement shape) and **the Playwright versions it supports**, as `supported-versions.json` lists them.

Nothing is published yet: the package is `private` until the name, the licence and the NV Access question are decided (`docs/release-decisions.md`), and the org's release workflow never publishes a private package. Until then `.github/workflows/release-dry-run.yml`
rehearses a release on every pull request that changes one: it builds the bundles, versions this branch's changesets on a scratch copy, packs the package and installs it with its bundle through the mirror variable on both platforms,
and shows every file with its size and sum. The same rehearsal runs on your machine with `middleware/release/dry-run.sh <release-files> <out>` (and `install-check.sh`) after `release-bundles.yml`'s legs are gathered by `middleware/release/gather.sh`.

## Licence

Undecided, and a decision the spike leaves to a person: the package is `UNLICENSED` and private. The runtime in the bundle is GPL-3.0 (`../LICENSE`).
