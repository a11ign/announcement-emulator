---
"@a11ign/announcement-emulator": patch
---

The runtime reads a page's accessibility tree again from what changed and not whole after each key (the nodes that can have changed are read again and the list of nodes is brought up to date), and the reporter's `verify` option, which checked the companion extension's cache, also makes the runtime read the page from scratch after each incremental read and record where the two differ. Predicting speech for a page of a thousand tab stops no longer takes hours.
