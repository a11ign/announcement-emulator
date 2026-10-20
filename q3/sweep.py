"""Q3, the emulator's side: the fleet worker's structural sweep, driven through the emulator instead of through Guidepup and a real NVDA.

The procedure is a re-implementation of the worker's (screenreader-worker `src/capture-probes.mjs`: `sweepEveryStructuralType`, `collectByType`,
`sweepInDirection`, and `src/capture-pure.mjs`: `sweepStepFromSpeech`, `dedupeKey`), read at the release the fleet runs. It is not an import of
them (ADR 0045). What the comparison measures is the NVDA speech; the loop that asks for it must be the same loop, or a difference could be
the loop's.

One thing to hold on to: the worker does not record what NVDA said. It records what Guidepup logged for the key, and Guidepup (0.31.0,
`NVDAClient.js`) logs, for each action, ONLY THE FIRST `speak` message NVDA's Remote Access sent after the key (capture mode "initial", the
default; `CAPTURE_OPTIONS` is undefined in `capture-setup.mjs`); a message is the strings of one speech sequence, trimmed and with runs of
whitespace collapsed, joined with ", ". `phrase_of` does that over the sequences the emulator's speech spy saw.
"""
import re, time

MAX_SWEEP_STEPS = 250            # capture-probes.mjs
MAX_CONSECUTIVE_REPEATS = 25     # capture-pure.mjs
MIN_CONTROL_NAME_LEN = 3         # capture-pure.mjs: shorter is a stray key echo, not a control name
DEDUPE_KEY_LEN = 80
MAX_CONTAINER_DEPTH = 4
CONTAINER_PREFIX = re.compile(r"^(?:\w[\w\s'-]*[,\s]\s*)?(?:landmark|region|banner|navigation|main|complementary|content info|form|section|article),\s*", re.I)
EMBEDDED_CONTENT_ROLE = re.compile(r"(?:^|,\s*)(?:frame|embedded object)\s*(?:,|$)", re.I)      # probeKindFor: never operate a control inside embedded content
NO_MORE = re.compile(r"\bno (next|previous|more)\b", re.I)
JS_SPACE = r"[\s﻿]"        # what JavaScript's \s and String.trim() treat as white space beyond Python's


def js_trim(s): return re.sub(r"^%s+|%s+$" % (JS_SPACE, JS_SPACE), "", s)


def phrase_of(sequences):
    """Guidepup's logged phrase for one action: the first speak message, its strings trimmed and whitespace-run-collapsed, joined by ', '.
    Non-string items (speech commands) are skipped; an action with no speech logs ''."""
    if not sequences: return ""
    parts = [re.sub(r"%s{2,}" % JS_SPACE, " ", js_trim(x)) for x in sequences[0] if isinstance(x, str)]
    return ", ".join(parts)


def dedupe_key(phrase):
    key = str(phrase)
    for _ in range(MAX_CONTAINER_DEPTH):
        stripped = CONTAINER_PREFIX.sub("", key, count=1)
        if stripped == key: break
        key = stripped
    return key[:DEDUPE_KEY_LEN]


def sweep_step(entries, seen, prev, repeats=0):
    """sweepStepFromSpeech: did the last jump MOVE, and what was announced? Returns (stop, phrase, seen, repeats)."""
    if len(entries) < seen: return "channelReset", None, len(entries), repeats
    spoken = [js_trim(str(p)) for p in entries[seen:]]; spoken = [p for p in spoken if p]
    advanced = len(entries)
    if not spoken: return "silent", None, advanced, repeats
    phrase = spoken[-1]
    if NO_MORE.search(phrase): return "exhausted", None, advanced, repeats
    if phrase == prev:
        consecutive = repeats + 1
        return ("repeat", None, advanced, consecutive) if consecutive >= MAX_CONSECUTIVE_REPEATS else (None, phrase, advanced, consecutive)
    return None, phrase, advanced, 0


class Walker:
    """The worker's `nvda` object over an emulated session: one `perform` is one key and one entry in the phrase log."""
    def __init__(self, doc, driver):
        self.d = doc; self.driver = driver; self.log = []; self.errors = []; self.actions = 0

    def perform(self, key):
        i = len(self.driver.SPY.sequences)
        self.actions += 1
        try: self.d.quick_press(key)
        except BaseException as e:
            import traceback
            self.errors.append(f"{key}: {type(e).__name__}: {e}")
            if len(self.errors) <= 3: traceback.print_exc(limit=-4)
            self.log.append("")
            raise ActionError(self.errors[-1])
        self.log.append(phrase_of(self.driver.SPY.sequences[i:]))
        return self.log[-1]


class ActionError(Exception): pass


def sweep_in_direction(w, key, label, out, seen_keys, on_item, deadline):
    """sweepInDirection. Returns {stop, steps, stopPhrase}."""
    prev, repeats, recoveries, seen = "", 0, 0, len(w.log)
    for i in range(MAX_SWEEP_STEPS):
        if time.time() > deadline: return {"stop": "deadline", "steps": i, "stopPhrase": prev}
        try:
            w.perform(key)
            stop, phrase, seen, repeats = sweep_step(w.log, seen, prev, repeats)
        except ActionError as e:
            return {"stop": "error", "steps": i, "stopPhrase": prev, "error": str(e)}
        if stop == "silent":      # the emulator is synchronous: speech that has not arrived by now will not (Guidepup's late-speech retries have nothing to wait for)
            return {"stop": "silent", "steps": i, "stopPhrase": prev}
        if stop: return {"stop": stop, "steps": i, "stopPhrase": prev}
        prev = phrase
        if len(phrase) < MIN_CONTROL_NAME_LEN:      # a key echo: focus mode. The worker's remedies: Escape, then moveToContainingBrowseModeDocument
            recoveries += 1
            if recoveries > 2: return {"stop": "focusModeStuck", "steps": i, "stopPhrase": phrase}
            if recoveries == 1:
                try: w.perform("escape")
                except ActionError: pass
            prev = ""
            continue
        k = dedupe_key(phrase)
        if k in seen_keys: continue
        seen_keys.add(k); out.append(phrase)
        if on_item: on_item(phrase)
    return {"stop": "cap", "steps": MAX_SWEEP_STEPS}


def collect_by_type(w, prev_key, next_key, label, deadline, on_item=None):
    out, seen_keys = [], set()
    p = sweep_in_direction(w, prev_key, label, out, seen_keys, on_item, deadline)
    prev_count = len(out)
    n = sweep_in_direction(w, next_key, label, out, seen_keys, on_item, deadline)
    return out, {"type": label, "found": len(out), "prevStop": p["stop"], "nextStop": n["stop"], "prevStopPhrase": p.get("stopPhrase"),
                 "nextStopPhrase": n.get("stopPhrase"), "prevCount": prev_count, "prevSteps": p["steps"], "nextSteps": n["steps"],
                 **({"error": p.get("error") or n.get("error")} if p.get("error") or n.get("error") else {})}


def anchor_to_top(w):
    """anchorToTop: Escape, then Control+Home (`nvda.press`, so each is an action with an entry in the log)."""
    for key in ("escape", "control+home"):
        try: w.perform(key)
        except ActionError: pass


def disclosure_probe(w, phrase):
    """probeKindFor with probeForms off: only a control announced `collapsed` is operated, and never one inside a frame. Enter on it
    (`nvda.act()`), ask NVDA to re-announce the focus (`reportCurrentFocus`, NVDA+Tab), then Escape back to browse mode (`operateControl`'s
    `finally`). Each is an action with its own entry in the phrase log, and those entries sit AFTER the sweep's `seen`: the next step's
    `slice(seen)` starts with them, which is how the worker behaves and so how this does."""
    if EMBEDDED_CONTENT_ROLE.search(phrase) or not re.search(r"\bcollapsed\b", phrase, re.I): return None
    for key in ("enter", "nvda+tab", "escape"):
        try: w.perform(key)
        except ActionError: pass
    return True


def read_through(w, steps=600):
    """readPageInOrder with the line strategy: Down arrow until the page bottom (the caret stops) or `steps`. Leaves the caret at the bottom,
    which is where the sweeps start. Returns the lines read."""
    lines = []
    for _ in range(steps):
        before = w.d.caret()
        try: w.perform("downArrow")
        except ActionError: break
        if w.d.caret() == before: break
        if w.log[-1]: lines.append(w.log[-1])
    return lines


def structure_sweep(w, deadline):
    """sweepEveryStructuralType + sweepExtraTypes (probeTables is off on real pages, so tableCells is not swept)."""
    structure, marks = {}, []
    for ch, label, pk, nk, hook, anchor in (
        ("headings", "heading", "shift+h", "h", None, False),
        ("landmarks", "landmark", "shift+d", "d", None, False),
        ("formFields", "formField", "shift+f", "f", lambda ph: disclosure_probe(w, ph), False),
        ("graphics", "graphic", "shift+g", "g", None, False),
        ("links", "link", "shift+k", "k", None, False),
        ("lists", "list", "shift+l", "l", None, True),
        ("frames", "frame", "shift+m", "m", None, True)):
        if anchor: anchor_to_top(w)
        structure[ch], mark = collect_by_type(w, pk, nk, label, deadline, hook)
        marks.append(mark)
    structure["tableCells"] = []
    return structure, marks
