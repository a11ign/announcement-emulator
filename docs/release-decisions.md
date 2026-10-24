# Release decisions for the chairman: the name, the licence, and the NV Access requirement

Prepared for A11-233 (child 5 of A11-228, the Playwright middleware as a real package). **This document prepares three decisions and makes none.** They are the chairman's.
**Nothing was published, sent or reserved to write it:** no npm name is reserved, no repository was created, no trademark was filed and nobody was contacted. Every check below was made read-only.

Where a result comes from is marked on it, as in `docs/playwright-middleware-spike.md`: **checked** (the author ran the command or read the page, on the date given), **quoted** (copied from a source, not re-run) or **not checked** (with the reason). All dates are UTC. A reading is a moment: a name that is free on 2026-10-24 can be taken tomorrow.

After the chairman decides, a follow-up records the choices in this file and applies them (`middleware/package.json` `name`, `license` and `private`; a `LICENSE` for the package; the README; ADR 0047 in the `a11ign` repository).

## 1. Wording

The chairman's direction of 2026-10-24 allows the package to say it is *based on the NVDA screen reader*, within ADR 0047. The description the rest of this document uses:

> Predicts what the NVDA screen reader would say, built on NVDA's open-source code. Not affiliated with NV Access.

Never, in a name, a description, a README, a report or a release note (ADR 0047, "The name, and NV Access's position", item 1, and the chairman's direction):

- that it **is** NVDA, or a reading of NVDA;
- that NV Access **endorses** it, or is affiliated with it;
- that it is "**NVDA-compatible**";
- the **NVDA logo** (ADR 0047 records that the NV Access and NVDA logos are registered trade marks of NV Access Limited, quoted from nvaccess.org on 2026-10-16, and that no published rule for using them was found).

And, from ADR 0047 Decision 2, on every surface that shows the output: **the speech is a prediction, advisory, and never evidence.** Every candidate name below is judged against this: none contains "NVDA", and none says or implies NVDA, endorsement or compatibility.

## 2. Name

The chairman wants a better name than `announcement-emulator`. Six were asked for: Hearsay, Earshot, Readout, Foresay, Forehear and Echo. Two are the worker's own: **Prespeak** and **Forespeak**. (Overhear, Foretell, Sayso and a few others were also looked at and left out: Overhear, Foretell and Sayso are taken on npm; Overhear is a placeholder package, "Agent infrastructure package name held for future use", published 2026-04-27.)

### How each column was checked

| column | command or source | notes |
|---|---|---|
| npm, unscoped | `npm view <name> name` | an `E404` means the name is free. If taken: the latest version's publish date and last week's downloads (`https://api.npmjs.org/downloads/point/last-week/<name>`) |
| npm, `@a11ign/<name>` | `npm view @a11ign/<name> name` | an `E404` means unused. The scope is live: `@a11ign/toolchain` (0.10.2), `@a11ign/evidence` (0.5.0) and `@a11ign/scorer` (0.3.7) all resolve on 2026-10-24. **Who owns the `@a11ign` npm organisation and who may publish into it: not checked** (`npm org ls a11ign` lists no one without a login). |
| GitHub | `gh api repos/a11ign/<name>`, `gh repo list a11ign --limit 100`, and `gh search repos <name> --match name --sort stars --limit 5` | a 404 on the first, and no match in the 17 repositories of the second (private ones included), means `a11ign/<name>` is free. The third lists the best-known repositories with the same name elsewhere; GitHub names are per owner, so those do not block `a11ign/<name>`. |
| Trademark | **the registers were not queried.** UK IPO, EUIPO/TMview and USPTO answer only to an interactive search in a browser, and this run has no browser. What is recorded is a **web search on 2026-10-24** for the word in software, accessibility, speech and testing, with the registrations that search surfaced (through third-party mirrors such as Justia, not the registers themselves). | **A web search is not a register check.** A clean row here means "no clash surfaced", never "clear". Whether a clash matters is a legal question this document does not answer. |

### Candidates

| # | Name | npm, unscoped | npm, `@a11ign/` | GitHub `a11ign/` | Obvious trademark clash (web search, not a register) | Checked |
|---|---|---|---|---|---|---|
| 1 | **Hearsay** | **taken.** `hearsay` 3.0.0, "Library for observing things", last version published 2015-08-25, 5 downloads last week | free | free. Elsewhere: `hearsayit/HearsayRequireJSBundle` ★129, `parkscloud/Hearsay` ★15 (a transcription app) | **Yes, likely.** HEARSAY SYSTEMS is a US registered word mark (Reg. 5336733, 2017-11-14) for messaging, scheduling and social-media management software and SaaS, owned by a software company (Justia mirror, not the register). Same field as the product (software for teams); the classes of the registration were not read. | 2026-10-24 |
| 2 | **Earshot** | free | free | free. Elsewhere: `Leonxlnx/earshot` ★2610 ("Ears for coding agents"), `pykeio/earshot` ★234 (voice activity detection) | No registration surfaced. **Same name in use** by at least two unrelated accessibility apps on iOS (a live-transcription app, a VoiceOver-first podcast player) and by a popular repository in the coding-agent space. | 2026-10-24 |
| 3 | **Readout** | **taken.** `readout` 2.0.0, a Readme generator, last version published 2014-11-05, 2 downloads last week | free | free. Elsewhere: unrelated (ML and sensor repositories) | None surfaced. An ordinary English word ("readout"), so a weak mark and easy to collide with; the register was not queried. | 2026-10-24 |
| 4 | **Foresay** | free | free | free. Elsewhere: `Foresay-app/.github` ★0 (an organisation of that name exists, with only a `.github` repository) | None surfaced. An archaic English verb, "to say beforehand; predict" (dictionary entries). | 2026-10-24 |
| 5 | **Forehear** | free | free | free. Elsewhere: nothing relevant (a furnace-schedule repository) | None surfaced. Not found as a word or a product. | 2026-10-24 |
| 6 | **Echo** | **taken.** `echo` 0.1.9, "Echo library for node", last version published 2011-02-02, 109 downloads last week | free | free. Elsewhere: `labstack/echo` ★32777 (a Go web framework), many more | **Yes.** AMAZON ECHO and AMAZON ECHO DOT are active US class 9 marks (Justia mirrors). Echo is also a Go framework name. | 2026-10-24 |
| 7 | **Prespeak** (own) | free | free | free. Elsewhere: `dmastr123/PreSpeak` ★0, "AI-powered AAC word prediction" (accessibility-adjacent) | None surfaced. A coined word. | 2026-10-24 |
| 8 | **Forespeak** (own) | free | free | free. Elsewhere: `mleiseca/forespeak` ★1, a prediction market | None surfaced. An archaic English verb, "to foretell, to predict". | 2026-10-24 |

**Taken names on npm.** `hearsay`, `readout` and `echo` have not published for 11 to 15 years, with a handful of downloads a week (109 for `echo`). npm has a dispute process for names; it is an option for the chairman and it is **not a claim**: it was not read for this document, and the scoped name `@a11ign/<name>` needs none of it. **Not checked:** why `hearsay` and `readout` show a registry `time.modified` of 2022 although their last version is older (the author did not look into it).

**Reservation.** A free name stays free only until someone takes it. Reserving one is an outward-facing act, and not part of this ticket.

### The name in use

| Name | Reads in `npx <name> install` | Says "predicts what a screen reader would say, advisory" |
|---|---|---|
| Hearsay | good | very well: hearsay is what was heard second-hand and is not admissible as evidence, which is exactly the product's rule (ADR 0047 Decision 2) |
| Earshot | good | "within earshot", a listener's range; says hearing, not prediction |
| Readout | good | says speech output, not prediction |
| Foresay | good | "say beforehand": prediction, plainly; unusual word, easy to misspell as "forsay" |
| Forehear | awkward ("fore-here") | "hear beforehand": prediction, but the pronunciation invites a typo |
| Echo | very short | says repetition, which is the opposite of predicting; crowded name |
| Prespeak | good | "speak before": prediction; a coined word, with a clean field |
| Forespeak | good | "speak before": prediction; the older English form |

For the comparison, the working name **`announcement-emulator`** (not a candidate and not counted above): `npm view announcement-emulator` and `npm view @a11ign/announcement-emulator` are both `E404` (free) on 2026-10-24; `a11ign/announcement-emulator` exists, being this repository; trademark: not checked. It is accurate and long, and says nothing about Playwright or about prediction. ADR 0047 marks its availability *not checked*; this row settles it for npm and GitHub on this date.

## 3. Licence

**This is not legal advice.** It is a reading of the sources cited, by a worker who is not a lawyer, so that the chairman and counsel can decide. Where a point is a legal question that only a court settles, it says so.

### What there is to license

- **The npm package** (`middleware/`: the TypeScript, 20 files in `src/`; the reporter, `install`, `test`, `doctor`). It holds no NVDA code. No TypeScript file imports a Python module; it starts the runtime with `child_process.spawn` and reads JSON lines from it (`middleware/src/runtime.ts:33`, README "How it works"). Today `middleware/package.json` says `"license": "UNLICENSED"` and `"private": true`; the repository's `LICENSE` is GPL-3.0, and the README says "GPL-3.0. NVDA is GPL-2.0-or-later, taken under version 3 here."
- **The runtime bundle**: downloaded by the install command into a cache, pinned and checksummed (A11-228). It holds NVDA's Python source at `release-2026.1.1` (`pins.env`), the emulator's Python that **imports NVDA's modules into one process**, the CLDR names, the companion extension, a Python build and the packages NVDA imports. NVDA's `copying.txt`: "NVDA is available under the GNU General Public License version 2 or later, with two special exceptions" (plugins and drivers may use components under other licences; Microsoft's redistributable DLLs). The emulator's runtime is a combined work with NVDA's code, so **it is GPL in every option below**, and "2 or later" is what lets it be combined under version 3: "if code is released under GPL 'version 2 or later,' that is compatible with GPLv3" (GNU GPL FAQ, `#v2v3Compatibility`).

So the options differ in two places only: **the package's licence**, and **whether the runtime is "GPL-3.0-only" or "GPL-3.0-or-later"**.

### The options

| | the npm package | the runtime bundle |
|---|---|---|
| **A** (the chairman's lean) | Apache-2.0, spawning a separately downloaded runtime across the process boundary (ADR 0047 Decision 3, in the shape of ADR 0032) | GPL-3.0 |
| **B** | GPL-3.0, with everything else (ADR 0047 Decision 3 as written) | GPL-3.0 |
| **C** | MIT (or another permissive licence) on the same boundary as A | GPL-3.0 |

Within each: **"only" or "or later" for the runtime.** ADR 0047 Decision 3 leaves it open. `nvda-speech`, which the emulator absorbs, declares `GPL-3.0-or-later` (ADR 0047, quoted), and NVDA's own code is "2 or later"; the SPDX identifiers are `GPL-3.0-only` and `GPL-3.0-or-later`. "Or later" keeps the way open to a later GPL version without relicensing; "only" ties the project to the text of version 3.

### What each means for a team that runs `npm i -D`, installs the runtime, and uses it in CI

**Running it for the team's own tests is not distribution under any option.** The GPL FAQ: an organisation "can make a modified version and use it internally without ever releasing it outside the organization" and making copies for itself is not distribution (`#InternalDistribution`, `#GPLRequireSourcePostedPublic`). A team that installs the package and the runtime on its laptops and its CI runners, and ships a product that does not include them, takes on no GPL obligation. The package is a `devDependency`; it does not reach the team's own shipped product.

**What changes when a team redistributes.** Obligations attach to whoever *distributes* the runtime, whatever the package's licence: for example a team that bakes the runtime cache into a container image it publishes or hands to a contractor, who must offer the corresponding source under GPL-3.0 (the FAQ: "providing copies to contractors for use off-site is distribution", `#InternalDistribution`; "If you make object code available on a network server, you have to provide the Corresponding Source", `#DistributingSourceIsInconvenient`). Under A and C the *package* in that image has only its permissive terms (keep the licence text and, for Apache-2.0, the NOTICE file). Under B the package is GPL-3.0 too.

| | A: package Apache-2.0 | B: everything GPL-3.0 | C: package MIT |
|---|---|---|---|
| The team's dependency policy | A permissive licence on the `license` field, which licence-policy tooling reads from the installed package's `package.json` (npm documents `license` as an SPDX expression; `UNLICENSED` for no grant). | The tool reads GPL-3.0, which many corporate policies list as "reject" or "review", even for a `devDependency` that never ships. **A mechanical block on adoption**, not a legal one. | As A. |
| The runtime | A separate download in a cache outside `node_modules` and outside the lockfile, so a scanner of the lockfile does not list it. A scanner of the filesystem or of an image that contains the cache *would* see GPL files. *(An inference about how such tools work. No scanner was run.)* | As A. | As A. |
| A team that wants to write its own tool around the package | May combine it with proprietary code. | Anything that links to it must be GPL-compatible (`#IfLibraryIsGPL`, `#GPLInProprietarySystem`). | As A. |
| a11ign's own Apache-2.0 packages | May depend on it. | May not: "GPLv3 software cannot be included in Apache projects" (ASF). They may still spawn it (ADR 0047 Decision 3). | May depend on it. |
| The licence boundary has to hold | **Yes**: the argument that the package is not a derivative of the GPL runtime. | No. | **Yes**, as A. |
| Patents and marks | Express patent grant and a patent-termination clause; no use of a11ign's marks. | GPL-3.0 has its own patent terms. | No express patent grant. |

*(Apache-2.0 is compatible with GPL version 3 and has "never been considered compatible with GPL version 2 by the FSF", ASF page. MIT's position was not checked here.)*

### What the process boundary and the separate download settle, and do not settle

Settled by the sources:

- **A tarball with no GPL code in it is not a GPL distribution.** Under A and C the npm package contains none of the runtime (`files` in `middleware/package.json` is `dist`, `pins.json` and the README). The runtime reaches the team through the install command, from wherever a11ign hosts it, and *that* download is where a11ign distributes GPL code and owes the source.
- **The FAQ's test for two programs or one** is the mechanism and the meaning of the communication: "pipes, sockets and command-line arguments are communication mechanisms normally used between two separate programs... But if the semantics of the communication are intimate enough, exchanging complex internal data structures, that too could be a basis to consider the two parts as combined" (`#MereAggregation`). Simple fork-and-exec with no intimate communication gives separate programs (`#GPLPlugins`). The package starts the runtime with command-line options and reads JSON lines of predicted speech: no shared address space, no linked code.

**Not settled:** "This is a legal question, which ultimately judges will decide" (`#MereAggregation`). The FAQ's criterion is met on the facts above as the worker reads them; that is a reading, not a ruling. If a court disagreed, the cost under A and C would be that the package had to be GPL-3.0 (option B), and a11ign is the copyright holder of the package (the author did not check who holds the copyright in `middleware/`; the history of `middleware/src` shows one author and ten commits).

**Not settled either:** whether the *output* (the predicted speech) carries any GPL. The FAQ says "copyright law does not give you any say in the use of the output people make from their data using your program" unless "substantial parts of the output are copied (more or less) from text in your program" (`#GPLOutput`). The output is mostly the page's own text and short role and state phrases from NVDA's tables. Counsel may want to read that point.

### What the repository has to change after the choice

Apply nothing until the chairman decides.

- **A or C:** a `middleware/LICENSE` (Apache-2.0 or MIT text), `"license": "Apache-2.0"` (or `"MIT"`) in `middleware/package.json`, `"private"` removed when the package is first published, and the README's licence section rewritten so the repository says "the package under X, the runtime under GPL-3.0". Today `LICENSE` at the root is GPL-3.0 and covers everything; per-directory licences make the split visible. Apache-2.0 also asks for a `NOTICE` file.
- **B:** `"license": "GPL-3.0-only"` or `"GPL-3.0-or-later"` in `middleware/package.json`; `"private"` removed; no new `LICENSE` file.
- All options: the runtime's licence field, in the bundle's own notices (below), `GPL-3.0-only` or `GPL-3.0-or-later`.

### The notices the bundle needs

Under the lean-bundle plan (A11-228: no Chrome, a stripped Python, only the NVDA modules the emulator imports), the bundle holds the following. The notices are what each licence asks for, and the GPL's source obligation covers the whole runtime a11ign ships.

| component | licence | what it asks of the bundle | source |
|---|---|---|---|
| NVDA's Python modules, at `release-2026.1.1` | GPL-2.0-or-later with two exceptions | the licence text and copyright notices; the corresponding source offered with the runtime, under GPL-3.0 | NVDA `copying.txt`, `readme.md` ("a modified GNU General Public License version 2 or later") |
| The emulator's runtime, extension and tables | GPL-3.0 (this repository's `LICENSE`) | the same; the corresponding source is this repository at the release tag, with `pins.env` and `middleware/bundle/build.sh` | `LICENSE`, README |
| Tables derived from Chromium's Windows mapping | BSD-3-Clause | keep the copyright notice, the conditions and the disclaimer | README, "Licence" |
| CPython, from python-build-standalone | PSF licence, and the licences of the libraries it bundles | python-build-standalone says its builds are "governed by varied software use licenses", and that it builds against libedit and disables `_gdbm` to avoid GPL readline and GDBM, for builds from 2023 (the pinned release is 20261013). Ship its licence report with the Python. | python-build-standalone documentation, "Licensing" |
| The packages NVDA imports (`PYTHON_PACKAGES` in `pins.env`) | each its own | each package's notice. Their licences were **not checked** one by one; generate a notices file from the installed metadata when the bundle is built. | `pins.env` |
| CLDR names (`nvaccess/nvda-cldr`) | believed to be the Unicode licence (**not checked**: the licence file of `nvaccess/nvda-cldr` was not found at the path tried) | the Unicode copyright and permission notice | `pins.env` |

Chrome for Testing is no longer in the bundle under A11-228, so its licences (Chromium's BSD-3 and the codecs and other third-party licences of the browser) leave with it.

### Sources

- GNU GPL FAQ, https://www.gnu.org/licenses/gpl-faq.html, read 2026-10-24: `#MereAggregation`, `#GPLInProprietarySystem`, `#GPLPlugins`, `#IfLibraryIsGPL`, `#InternalDistribution`, `#GPLRequireSourcePostedPublic`, `#DistributingSourceIsInconvenient`, `#v2v3Compatibility`, `#GPLOutput`.
- Apache Software Foundation, "Apache License v2.0 and GPL Compatibility", https://www.apache.org/licenses/GPL-compatibility.html, read 2026-10-24.
- NVDA `copying.txt` and `readme.md`, https://github.com/nvaccess/nvda (master), read 2026-10-24.
- SPDX identifiers, https://spdx.org/licenses/Apache-2.0.html and https://spdx.org/licenses/GPL-3.0-or-later.html, read 2026-10-24.
- npm, "package.json: license", https://docs.npmjs.com/cli/v10/configuring-npm/package-json, read 2026-10-24 (SPDX expressions; `UNLICENSED`; `SEE LICENSE IN <filename>`).
- python-build-standalone, "Running Distributions: Licensing", https://gregoryszorc.com/docs/python-build-standalone/main/running.html, read 2026-10-24.
- This repository: `LICENSE`, `README.md` ("Licence"), `pins.env`, `middleware/package.json`, `middleware/README.md`, `middleware/src/runtime.ts`.
- ADR 0047 (`a11ign:docs/adr/0047-...md`), Decision 3 and "The name, and NV Access's position".

## 4. NV Access

**There is no message to NV Access in this document, and no contact address.** The chairman's direction of 2026-10-24: "no reason to reach out now. Do not draft the message."

### The requirement, as ADR 0047 states it

From "The name, and NV Access's position":

> 2. **Someone asks NV Access** before the first published release, and the answer goes on the spike's row. That is an outward-facing message from the organisation, so it is `ceo`'s to send or delegate; this ADR does not send it.
> 3. If NV Access replies that the name is welcome, renaming to include it is a one-row change. If it objects to the use at all, that is a falsifier (below).

And from "What would falsify this":

> - **NV Access objecting to the name or the derived use** (see above): the name changes; the architecture does not depend on it.

The ADR also records what it found on 2026-10-16: NV Access asserts registered marks for its logos, and a published position on the **word** "NVDA" in a third party's name, on "NVDA-compatible" wording, or on derived products was **not found**. "Absence is not permission."

A11-228 plans a **preview** and says the package improves every release. So "the first published release" is the preview.

### The amendment, three options

The ADR is in the `a11ign` repository. This ticket proposes the text and does not edit it; a follow-up amends the ADR once the chairman chooses.

**Keep.** No change. Item 2 reads as above; no release, the preview included, is published until NV Access has been asked and the answer is on the row. Item 3 and the falsifier stay.

**Drop.** Replace item 2 and item 3 with:

> 2. No one is required to ask NV Access before a release. Item 1 still binds: no "NVDA" in the identifier, and no claim that it is NVDA, is endorsed by NV Access or is "NVDA-compatible".
> 3. If NV Access objects to the name or the derived use, the name changes. The architecture does not depend on it.

The falsifier "NV Access objecting to the name or the derived use" stays, as an event to react to, not as a condition checked before release.

**Move to "before the first non-preview release".** Replace item 2 with:

> 2. **Someone asks NV Access before the first non-preview release**, and the answer goes on the release row. That is an outward-facing message from the organisation, so it is `ceo`'s to send or delegate; this ADR does not send it. Preview releases may be published before it is asked.

Item 3 and the falsifier stay as written. This option needs a definition of "preview" to be useful. A suggested one for the chairman to confirm or change: a release whose version has a `-preview.N` suffix and that is published under the npm dist-tag `preview` and not `latest`; the first release published as `latest` is the first non-preview release.

## 5. The worker's recommendations

Each is **the worker's recommendation, not a decision.** The chairman decides; a follow-up records the choice in this file.

### The name: Foresay

**Worker's recommendation, not a decision: `Foresay`, published as `@a11ign/foresay`.** Why:

- It says the product's job in one word: "to say beforehand; predict". It also keeps the advisory rule in the name itself, and says nothing about NVDA, endorsement or compatibility.
- Free on 2026-10-24 on npm unscoped and scoped, and as `a11ign/foresay`; no software product or trademark surfaced. (The only same-name GitHub item is an organisation with a `.github` repository and no code.)
- It reads in `npx foresay install` and `import { withAnnouncements } from "@a11ign/foresay"`.

The second choice is **Prespeak** (equally clean, a coined word), and then **Earshot** (the nicest word, but it is already in use by accessibility apps and by a repository with ★2,610 in the coding-agent space). **Hearsay** fits the advisory rule best and is not recommended: a registered software mark of that name surfaced in the same field, and the unscoped npm name is taken. **Echo** is not recommended: Amazon's marks, and a crowded name. This recommendation rests on a web search, not on a register check; before the chairman commits, a trademark search of the register (UK IPO, EUIPO and USPTO, classes 9 and 42) for the chosen word is worth the small cost, and is for the chairman or counsel to commission.

### The licence: option A

**Worker's recommendation, not a decision: option A, the chairman's lean. The npm package under Apache-2.0, spawning a separately downloaded GPL-3.0 runtime across the process boundary.** The runtime under `GPL-3.0-or-later`.

- It is the shape ADR 0047 Decision 3 already chose: "Apache-2.0 packages never import it... Data crosses a process boundary".
- It keeps the adoption path open: the package passes a team's licence policy, and the runtime is a separate download, outside the lockfile, that the team runs internally without distributing it.
- The package contains no NVDA code, and it talks to the runtime only by command-line options and JSON lines, which the GPL FAQ names as the normal communication between separate programs.
- Apache over MIT: an express patent grant. The cost is one `NOTICE` file.
- "Or later" matches `nvda-speech` and NVDA's own "2 or later".

The risk is that the boundary is a legal question that only a court settles (§3). If counsel is not comfortable, option B costs adoption by teams with a no-GPL policy and nothing else. **This is not legal advice**, and a lawyer should read §3 before the first release.

### NV Access: move the requirement to "before the first non-preview release"

**Worker's recommendation, not a decision: Move.**

- It matches the chairman's position that there is no reason to reach out now, without deleting a safeguard ADR 0047 put in on purpose.
- A preview published with the wording of §1 and with no "NVDA" in its name is the case ADR 0047 designed for. A rename costs little while the package has few users, and costs more later, so the question should be asked before the name has a following.
- Keep would hold the preview, which the chairman wants shipped; Drop would leave a registered-mark owner never asked.
- The preview must be defined (§4), and the wording rules of §1 must hold from the first preview.
