"""The flags: three things in a test run that a screen-reader user would meet and the test would not (A11-208, question 4).

Each rule is fixed here, with the window it waits in, and was fixed before any corpus page was run. A flag is a prediction about the prediction: it says what the predicted
speech lacks, never what NVDA said (ADR 0047, Decision 2).

    focus-without-name   focus landed on an element that has no accessible name, and what is predicted for it has no name in it.
    silent-dialog        a dialog opened and nothing was predicted for it: no focus move into it and no live-region speech, from LAG_MS before it to WINDOW_MS after.
    unheard-error        an error message appeared for a field and its words are in none of the speech predicted in that window.
"""
import re

WINDOW_MS = 1000      # how long after an event the speech that answers it may come: the slack for a later one.
LAG_MS = 20      # how long before the page reports a dialog or an error the speech for it may be dated: a focus move into a dialog happens inside the call that opens it, and its report may be dated a few ms either side
CONTROL_ROLES = {'button', 'link', 'textField', 'searchBox', 'checkBox', 'radioButton', 'comboBoxSelect', 'comboBoxGrouping', 'comboBoxMenuButton', 'listBox', 'menuItem', 'menuItemCheckBox',
                 'menuItemRadio', 'tab', 'switch', 'slider', 'spinButton', 'textFieldWithComboBox', 'popUpButton', 'toggleButton', 'treeItem', 'disclosureTriangle', 'image', 'imageMap'}


def words(text): return re.findall(r"\w+", str(text).lower())


def derive_flags(records):
    """The flags for a run's records, in time order. `records` are the runtime's speech and observation records (see predict.py)."""
    speech = [r for r in records if r['kind'] == 'speech']
    flags = []
    for r in speech:
        if r['cause'] == 'focus' and unnamed_control(r): flags.append(flag('focus-without-name', r, f"focus landed on a {r['node']['role']} with no accessible name; predicted: {r['text']!r}"))
    for o in (r for r in records if r['kind'] == 'observe'):
        window = [s for s in speech if o['t'] - LAG_MS <= s['t'] <= o['t'] + WINDOW_MS and s.get('page') == o.get('page')]
        about_dialog = [s for s in window if s['cause'] == 'live' or (s.get('node') or {}).get('inDialog')]      # the control that opened it takes the focus first, and is not the dialog being heard
        if o['what'] == 'dialog' and not about_dialog:
            flags.append(flag('silent-dialog', o, f"a dialog{' named ' + repr(o['node']['name']) if o['node'].get('name') else ''} opened and nothing was predicted for it (no focus into it, no live-region speech) from {LAG_MS} ms before it to {WINDOW_MS} ms after"))
        elif o['what'] == 'error' and not said(o['text'], window):
            flags.append(flag('unheard-error', o, f"the error message {o['text']!r} for {o['node'].get('name') or 'a field'!r} is in none of the speech predicted from {LAG_MS} ms before it to {WINDOW_MS} ms after"))
    return sorted(flags, key=lambda f: f['t'])


def unnamed_control(r):
    n = r['node']
    return n['role'] in CONTROL_ROLES and not (n.get('name') or '').strip() and 'NAME' not in r['shape']


def said(text, window):
    heard = set(w for s in window for w in words(s['text']))
    return all(w in heard for w in words(text))


def flag(name, record, detail):
    return {'kind': 'flag', 'flag': name, 't': record['t'], 'page': record.get('page'), 'detail': detail, 'node': record.get('node')}
