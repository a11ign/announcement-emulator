---
"@a11ign/foresay": patch
---

The runtime reads a page's accessibility tree again from what changed and not whole after each key (the nodes that can have changed are read again and the list of nodes is brought up to date), and the reporter's `verify` option, which checked the companion extension's cache, also makes the runtime read the page from scratch after each incremental read and record where the two differ. The emulator no longer looks for each node's reverse relations in every other node, so the buffer of a page of 3,700 nodes is built in 0.09 s, not 4.6 s.
