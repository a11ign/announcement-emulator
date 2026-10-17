"""Classify NVDA's 43 Chrome system tests by what the emulator would need to run them. Counts are from the AST of chromeTests.py."""
import ast, collections, extract_cases
src = extract_cases.SRC.read_text(); tree = ast.parse(src)
calls = collections.Counter()
for c in ast.walk(tree):
    if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute): calls[c.func.attr] += 1
print({k: v for k, v in calls.items() if k in ('strings_match', 'speech_matches', 'speech_contains', 'braille_matches', 'braille_contains', 'string_contains_strings', 'getSpeechAfterKey', 'getSpeechAfterAction', 'prepareChrome')})
FOCUS = {'tab', 'shift+tab', 'NVDA+space', 'nvda+space', 'enter', 'space', 'NVDA+tab', 'alt+downArrow'}
REVIEW = {'numpad8', 'numpad6', 'numpad4', 'numpad2', 'numpad5'}
TABLE = {k for k in ('control+alt+downArrow', 'control+alt+upArrow', 'control+alt+rightArrow', 'control+alt+leftArrow', 'control+alt+pageUp', 'control+alt+pageDown', 'control+alt+home', 'control+alt+end')}
SAYALL = {'NVDA+downArrow', 'NVDA+control+alt+downArrow', 'NVDA+control+alt+rightArrow', 'NVDA+control+alt+leftArrow', 'NVDA+control+alt+upArrow'}
BUF = {'downArrow', 'upArrow', 'control+rightArrow', 'control+leftArrow', 'rightArrow', 'leftArrow', 'end', 'control+home', 'NVDA+upArrow', 'NVDA+control+upArrow'}
QUICK = {'h', 't', 'e', 'p', 'shift+p', '2', '3', 'x', 'k', 'f', 'b', 'l', 'i'}
def cls(keys, issues, html_ok):
    ks = set(k for k in keys if isinstance(k, str)); tags = set()
    if any(i.startswith('other assertion: braille') for i in issues): tags.add('asserts braille')
    if not html_ok: tags.add('page/expectation not evaluable')
    if ks & FOCUS: tags.add('needs focus/object layer')
    if ks & REVIEW: tags.add('needs review cursor')
    if ks & TABLE: tags.add('needs table navigation')
    if ks & SAYALL: tags.add('needs say-all/table say-all')
    if ks - FOCUS - REVIEW - TABLE - SAYALL - BUF - QUICK: tags.add('other keys: ' + ','.join(sorted(ks - FOCUS - REVIEW - TABLE - SAYALL - BUF - QUICK)))
    return tags
rows = collections.Counter(); per = {}
cs = extract_cases.cases()
for c in cs:
    t = cls([k for k, _ in c['steps']], c['issues'], c['html'] is not None and not any('not evaluable' in i for i in c['issues']))
    key = ' + '.join(sorted(t)) or 'runnable now (buffer keys + quick nav)'
    rows[key] += 1; per.setdefault(key, []).append((c['name'], len(c['steps'])))
for k, n in rows.most_common(): print(f'{n:3d} tests  {sum(a for _, a in per[k]):3d} steps  {k}')

print('--- non-exclusive tag counts')
tagc = collections.Counter(); tags_steps = collections.Counter(); none = 0
for c in cs:
    t = cls([k for k, _ in c['steps']], c['issues'], c['html'] is not None and not any('not evaluable' in i for i in c['issues']))
    for x in t: tagc[x] += 1; tags_steps[x] += len(c['steps'])
    if not t: none += 1
for k, n in tagc.most_common(): print(n, 'tests', tags_steps[k], 'steps', k)
print('no tag:', none)
