# Incremental reads of the DevTools tree (A11-229, step 2)

Recorded in Playwright 1.64.1's Chromium (156.0.8078.4) on Linux, with the DevTools port as the tree source and the reporter's `verify` option on (`ANNOUNCEMENT_EMULATOR_VERIFY=1`).

| file | what it is | made with |
|---|---|---|
| `form.conversation.gz`, `basket.conversation.gz` | the first 18 and 12 reads of the `paced` project's two local tests (`tests/paced/local.spec.ts`): for each read, what the browser had said since the last one (`told`), the commands the reader sent and what the browser answered (`conversation`), and the tree it made (`tree`). `verified` is `same` where `verify` found an incremental read the same as a read from scratch made at the same moment, and `the page changed` where the page moved on while it was checked. `test_incremental.py` (`Recorded`) plays them in order and holds the reader to the same commands and the same trees. | `AE_CONVERSATION=<file>` |
| `devtools-basket-live.jsonl.gz`, `devtools-error-alert.jsonl.gz`, `devtools-spa-route.jsonl.gz` | what the runtime was told while the `fixtures` project's tests of the same names as `../basket-live`, `../error-alert` and `../spa-route` ran, with the tree read through the DevTools port. `test_replay.py` holds their live-region, dialog and error events to those of the extension's recordings of the same pages. | `AE_RECORD=<file>` |

The conversations are not named `*.jsonl.gz` on purpose: `middleware/bundle/compare_bundles.py replay` replays every `*.jsonl.gz` under `fixtures` through `replay.py`, which reads page events and not these (CI's `trace` and `transcripts` jobs failed on them at e34c7e2).

To record again (a conversation is written as plain lines; `gzip` it to `*.conversation.gz`), in a project that has the package and the sample suite, with `ANNOUNCEMENT_EMULATOR_BUNDLE` naming a bundle:

```sh
ANNOUNCEMENT_EMULATOR_VERIFY=1 AE_CONVERSATION=form.conversation   npx playwright test --project=paced -g "a form is filled in key by key" --workers=1
ANNOUNCEMENT_EMULATOR_VERIFY=1 AE_CONVERSATION=basket.conversation npx playwright test --project=paced -g "a basket counts" --workers=1
AE_RECORD=devtools-basket-live.jsonl npx playwright test --project=fixtures -g "adding a mug" --workers=1
```

A recorded read depends on the commands the reader sends, in order: a change to what `incremental.py` asks the browser for makes `Recorded` fail until the files are recorded again (keep the first lines of each file and the rows `verified: same`).
