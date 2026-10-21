"""The announcement shape, as the fleet's own measure defines it.

A re-implementation, not an import (ADR 0045), of `classify()` and the tokenising in screenreader-worker `packages/nvda-speech/scripts/measure_announcement_shapes.py`,
the script whose header says "18,371 announcements, 33 distinct shapes, top 10 covering 94.3%". It tokenises an announcement on "," and labels each token
ROLE, STATE, LEVEL, COUNT, POSITION or NAME; a shape is the tuple of the non-empty labels. The role and state vocabularies are read, here, from the NVDA
source this spike runs (controlTypes/role.py and state.py at the pinned release) the way that package's `generate_labels.py` reads them.
"""
import re, sys, os, pathlib, collections, functools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'emu'))
from paths import DOWNLOADS

ENTRY = re.compile(r"^\s*(?:Role|State)\.(?P<key>[A-Z0-9_]+)\s*:\s*(?:_\(\s*(?P<q>[\"'])(?P<plain>.*?)(?P=q)\s*\)|pgettext\(\s*[\"'].*?[\"']\s*,\s*(?P<q2>[\"'])(?P<ctx>.*?)(?P=q2)\s*\))")
LANDMARKS = {"banner", "navigation", "main", "complementary", "content info", "region", "search", "form"}
FIELDS = ("headings", "landmarks", "formFields", "links", "lists", "graphics", "tableCells")


def _extract(source, name):
    anchor = re.search(r"^%s\b[^=\n]*=\s*\{" % re.escape(name), source, re.M)
    if not anchor: raise SystemExit(f"no assignment found for {name}")
    depth, body = 0, []
    for line in source[anchor.start():].split("\n"):
        depth += line.count("{") - line.count("}"); body.append(line)
        if depth == 0 and body[0].count("{"): break
    out = {}
    for line in body:
        m = ENTRY.match(line)
        if m: out[m.group("key")] = m.group("plain") or m.group("ctx")
    if not out: raise SystemExit(f"extracted nothing for {name}")
    return out


@functools.lru_cache(maxsize=1)
def vocabularies():
    ct = DOWNLOADS / "nvda-src/source/controlTypes"
    roles = _extract((ct / "role.py").read_text(), "_roleLabels")
    states = _extract((ct / "state.py").read_text(), "_stateLabels")
    negative = _extract((ct / "state.py").read_text(), "_negativeStateLabels")
    return ({v.lower() for v in roles.values() if v}, {v.lower() for v in [*states.values(), *negative.values()] if v}, len(roles), len(states), len(negative))


def classify(token):
    roles, states = vocabularies()[:2]
    text = token.strip().lower()
    if not text: return ""
    if text in roles: return "ROLE"
    if text in states: return "STATE"
    if re.fullmatch(r"level \d+", text): return "LEVEL"
    if re.fullmatch(r"with \d+ items?", text): return "COUNT"
    if re.fullmatch(r"\d+ of \d+", text): return "POSITION"
    if text.endswith(" landmark") and text[: -len(" landmark")] in LANDMARKS: return "ROLE"
    return "NAME"


def shape_of(announcement):
    return tuple(k for k in (classify(t) for t in str(announcement).split(",")) if k)


if __name__ == "__main__":
    print(vocabularies()[2:])
    for a in ["main landmark, Order details, heading, level 1", "Reference note 01, heading, level 2", "Save details, button", "list, with 6 items, Room hire rates 06, same page, link"]:
        print(shape_of(a), a)
