"""Writes roles.json: Chromium's role numbers (ui/accessibility/ax_enums.mojom, the Role enum) and the names chrome.automation gives them.

`Accessibility.getFullAXTree` says `chromeRole` (the number) for each node, and the number is the one thing that is the same in every browser version of one milestone;
chrome.automation's `RoleType` is the enum's name with a lowercase first letter (kTextField -> textField). Run once, by hand, for the Chrome the bundle pins (pins.env CHROME):

    python3 gen_roles.py <ax_enums.mojom> > roles.json
    # the file: curl -fsSL "https://chromium.googlesource.com/chromium/src/+/refs/tags/$CHROME/ui/accessibility/ax_enums.mojom?format=TEXT" | base64 -d
"""
import json, re, sys

lines = open(sys.argv[1]).read().split('\n')
start = next(i for i, line in enumerate(lines) if line.startswith('enum Role {'))
roles = {}
for line in lines[start + 1:]:
    if line.startswith('};'): break
    m = re.match(r'\s*(?:\[Default\])?k([A-Za-z0-9]+)\s*=\s*(\d+)', line)
    if m: roles[int(m.group(2))] = m.group(1)[0].lower() + m.group(1)[1:]
print(json.dumps({str(k): roles[k] for k in sorted(roles)}, indent=0, separators=(',', ':')).replace('\n', ''))
