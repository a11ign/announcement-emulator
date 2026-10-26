# Structure fixtures (A11-229, step 1)

Three small pages (`middleware/sample-suite/pages/fields/`), each read twice in Playwright 1.64.1's Chromium (156.0.8078.4) on Linux, by the sample suite's `fields` project:

| file | what it is |
|---|---|
| `<page>.jsonl.gz` | what the companion extension told the runtime during the page's test (`AE_RECORD`), as the other `fixtures/*.jsonl.gz` are. Its last snapshot is the expected value of `test_axtree.py`. |
| `devtools-<page>.json.gz` | the answers of the DevTools port for the same page at its end: `getFullAXTree`, `DOMSnapshot`, the layout metrics, the page's state, the frame tree and the labels that carry a click listener (`AE_RAW`, the last read of the test). `test_axtree.py` converts it. |

`tables` is every way a table says where a cell is and which header words belong to it; `lists` is positions in a set, a field typed into, values and descriptions; `clickable` is an element of each kind with and without a
click listener. The extension recordings stay when the extension is removed (step 3 of A11-229): they are the reference the conversion is held to.

To record again, in a project that has the package and the sample suite, with `ANNOUNCEMENT_EMULATOR_BUNDLE` naming a bundle:

```sh
ANNOUNCEMENT_EMULATOR_TREE=extension AE_RECORD=tables.jsonl     npx playwright test --project=fields -g "tables is opened" --workers=1
ANNOUNCEMENT_EMULATOR_TREE=devtools  AE_RAW=devtools-tables.jsonl npx playwright test --project=fields -g "tables is opened" --workers=1   # the last line is the fixture
```

## What the DevTools tree does not give (the fixtures leave these out of the pages)

Seen when the two trees of the same pages were compared, and not forced (`axtree.py`, its docstring): ICU's word and sentence starts; the names of the parts inside a date or time field; a colour field's value and the file field's
"No file chosen"; ARIA radio buttons outside a radio group; the `relevant` of a live region by default; the display and tag of the editor inside a text field and of a line break; a node's `hovered` and `offscreen`.
