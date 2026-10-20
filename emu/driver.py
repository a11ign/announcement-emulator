"""Layer 0/5 shim for the spike: an NVDA Gecko_ia2 treeInterceptor whose buffer comes from the stand-in, with the pieces that
need a live Windows NVDAObject (the root object, focus, the app module) replaced by values taken from the Q1 tree."""
import boot, json, textInfos, controlTypes
import IAccessibleHandler  # NVDA imports this first (circular otherwise)
import virtualBuffers.gecko_ia2 as g
from NVDAObjects.IAccessible import chromium   # the buffer class NVDA really uses for Chrome (ChromeVBuf, ChromeVBufTextInfo)
import speech.speech as ss
from speech.commands import BeepCommand, EndUtteranceCommand

L = boot.LOCALLIB


class EmuBuffer(chromium.ChromeVBuf):
    def __init__(self, handle, url, title):
        import baseObject; baseObject.ScriptableObject.__init__(self)   # builds _gestureMap from the class's __gestures, as NVDA does
        self.VBufHandle = handle; self._emuUrl = url; self._emuTitle = title
        self._passThrough = False
        # attributes that BrowseModeDocumentTreeInterceptor.__init__ / VirtualBuffer.__init__ set (browseMode.py:1609-1624, virtualBuffers/__init__.py:520-526)
        self.backendName = 'gecko_ia2'; self.isLoading = False
        self._lastProgrammaticScrollTime = None; self._lastCachedDocumentConstantIdentifier = url
        self._lastFocusObj = None; self._objPendingFocusBeforeActivate = None
        self._hadFirstGainFocus = False; self._enteringFromOutside = True
        self._lastCaretPosition = None; self._lastCaretMoveWasFocus = False
        self.currentExpandedControl = None

    def _get_documentURL(self): return self._emuUrl
    def _get_documentConstantIdentifier(self): return self._emuUrl



def load(path):
    flat = json.load(open(path))
    root = flat[0]
    L.register_tree((1, root['ix']), flat)
    h = L.VBuf_createBuffer(None, 1, root['ix'], 'gecko_ia2')
    vh = L.VBufRemote_bufferHandle_t(); vh.value = h
    b = EmuBuffer.__new__(EmuBuffer)
    b.__init__(vh, root.get('url'), root.get('name'))
    b._h = h
    return b


def flat_speech(seq):
    out = []
    for x in seq:
        if isinstance(x, str): out.append(x)
        elif isinstance(x, (BeepCommand, EndUtteranceCommand)): pass
        else: out.append('<%s>' % type(x).__name__)
    return out


def lines(b):
    """(start, end, text) of every line, by NVDA's own UNIT_LINE expansion over the stand-in's line offsets."""
    n = L.VBuf_getTextLength(b._h); off = 0; out = []
    while off < n:
        ti = b.makeTextInfo(textInfos.offsets.Offsets(off, off)); ti.expand(textInfos.UNIT_LINE)
        out.append((ti._startOffset, ti._endOffset, ti.text)); off = max(ti._endOffset, off + 1)
    return out


def speak_line(b, start, reason=controlTypes.OutputReason.CARET):
    ti = b.makeTextInfo(textInfos.offsets.Offsets(start, start)); ti.expand(textInfos.UNIT_LINE)
    seq = list(ss.getTextInfoSpeech(ti, unit=textInfos.UNIT_LINE, reason=reason, useCache=False))
    return [flat_speech(s) if isinstance(s, list) else s for s in seq]


# ---- the speech oracle: what the system tests' speech spy sees (speechSpyGlobalPlugin.py + speech.speech.speak)
import speech, speech.speech
from speech.extensions import pre_speechQueued

class Spy:
    """Stands where speech.manager._SpeechManager stands. NVDA's own speak() has already normalised the sequence and appended
    CHUNK_SEPARATOR to every string by the time it calls manager.speak(); the spy joins each sequence's strings and strips it."""
    def __init__(self): self.sequences = []; self.callbacks = []
    def speak(self, seq, priority=None):
        self.sequences.append(list(seq))
        # The synth reaches a CallbackCommand when it has spoken what precedes it; say-all advances from these. Run them in order, at once.
        from speech.commands import CallbackCommand
        for item in list(seq):
            if isinstance(item, CallbackCommand): self.callbacks.append(item)      # the synth runs them when it gets there, not inside speak(): say-all is re-entered from them
    def __getattr__(self, n): return lambda *a, **k: None
    def text_since(self, i=0):  # SystemTestSpy get_speech_at_index_until_now
        parts = ["".join(c for c in s if isinstance(c, str)).strip() for s in self.sequences[i:]]
        return "\n".join(p for p in parts if p and not p.isspace())

SPY = Spy()
# The synth: the tests' own speechSpySynthDriver (tests/system/libraries/SystemTestSpy), instantiated as NVDA would.
import sys, synthDriverHandler, config
import speechDictHandler; speechDictHandler.initialize()
import characterProcessing; characterProcessing.initialize()
sys.path.insert(0, str(boot.R / 'nvda-src/tests/system/libraries/SystemTestSpy'))
import speechSpySynthDriver as _spy_mod
_synth = _spy_mod.SpeechSpySynthDriver()
synthDriverHandler._curSynth = _synth
_synth.initSettings()
speech.speech.initialize()
speech.speech._manager = SPY
# the rest of speech.initialize() (speech/__init__.py:156-168) that does not need a live synth: say-all and the language filter
import speech.sayAll
speech.sayAll.initialize(speech.speak, speech.speakObject, speech.getTextInfoSpeech, speech.SpeakTextInfoState)
speech.filter_speechSequence.register(speech.getSpeechSequenceWithLangs)
speech.speech.cancelSpeech = lambda *a, **k: None


class Gesture:
    """A key gesture as far as getScript() and the browse-mode scripts look at it."""
    def __init__(self, key):
        import inputCore
        self.identifier = 'kb:' + key; self.displayName = key
        self.normalizedIdentifiers = [inputCore.normalizeGestureIdentifier('kb:' + key)]
        self.isNVDAModifierKey = False


def _flush():
    import queueHandler; queueHandler.flushQueue(queueHandler.eventQueue)   # NVDA services its event queue after each script/event
    for _ in range(2000):          # and runs its generator objects and the synth's callbacks (say-all advances from them) until nothing is left
        if SPY.callbacks: SPY.callbacks.pop(0).run(); queueHandler.flushQueue(queueHandler.eventQueue); continue
        if not queueHandler.generators: break
        queueHandler.pumpAll()


def press(b, key):
    """Press `key` on the buffer: NVDA's own browse-mode script bound to it, or (for NVDA+upArrow, a global command) the same
    lines as globalCommands.script_reportCurrentLine:268-275. Returns what the spy saw."""
    i = len(SPY.sequences)
    g = Gesture(key)
    if key.lower() == 'nvda+downarrow':      # globalCommands.script_sayAll: read from the caret
        import speech.sayAll as _sa
        _sa.SayAllHandler.readText(_sa.CURSOR.CARET); _flush(); return SPY.text_since(i)
    GLOBAL = {'nvda+d': 'reportDetailsSummary', 'nvda+tab': 'reportCurrentFocus', 'numpad8': 'review_currentLine', 'numpad6': 'review_nextWord', 'nvda+uparrow': 'reportCurrentLine'}      # global commands: the real script on the real GlobalCommands instance
    if key.lower() in GLOBAL:
        import globalCommands; getattr(globalCommands.commands, 'script_' + GLOBAL[key.lower()])(g)
        _flush(); return SPY.text_since(i)
    if False:      # globalCommands.script_reportDetailsSummary, the real script on the real GlobalCommands instance
        import globalCommands; globalCommands.commands.script_reportDetailsSummary(g)
        _flush(); return SPY.text_since(i)
    if key.lower() == 'nvda+space':      # globalCommands.script_toggleVirtualBufferPassThrough, the part after the tree interceptor exists (2483-2492)
        import browseMode
        b.passThrough = not b.passThrough
        b.disableAutoPassThrough = b.passThrough
        browseMode.reportPassThrough(b)
        _flush(); return SPY.text_since(i)
    import scriptHandler, inputCore      # scriptHandler._findScript: user gesture map first (spy.assignGesture), then the object's own bindings
    mgr = getattr(inputCore, 'manager', None)
    maps = [s for ident in g.normalizedIdentifiers for s in mgr.userGestureMap.getScriptsForGesture(ident)] if mgr else []
    sc = scriptHandler._getObjScript(b, g, maps)
    if sc is None: raise NotImplementedError(f'no browse-mode script bound to {key}')
    sc(g)
    _flush(); return SPY.text_since(i)


def set_caret(b, offset):
    b._setSelectionOffsetsForEmu = None
    L.VBuf_setSelectionOffsets(b.VBufHandle, offset, offset)
