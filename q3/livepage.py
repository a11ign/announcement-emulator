"""A live page in the emulator, driven the way the worker drives NVDA: keys NVDA's own scripts answer, with the browser told what NVDA would tell it."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'emu'))
import boot, driver, live, globalVars


class LivePage(live.LiveDoc):
    scroll_browser = False      # sweeps run in seconds, not minutes: NVDA's scrollIntoView is not delivered to the browser (see live.LiveDoc.scroll_browser)

    def caret(self): return tuple(driver.L.buffers[self.b._h].sel)

    def quick_press(self, key):
        """One key as `nvda.perform` / `nvda.press` sends it. In focus mode a letter is the page's input, not NVDA's command (the worker met this on
        2,122 captures and answers it with Escape); otherwise it is NVDA's own script, and a focus change the script asked for reaches the browser
        and comes back as the focus event."""
        self._focus_requested = False; self._focus_moved = False; self._acted = False
        k = key.lower()
        if k == 'escape': return self._escape()
        if k in ('enter', 'tab', 'shift+tab', 'space'): return self.press(key)
        if self.b.passThrough and (len(k) == 1 or (k.startswith('shift+') and len(k) == 7)):      # focus mode: NVDA speaks the typed character
            import speech; speech.speakTypedCharacters(k[-1].upper() if k.startswith('shift+') else k) if hasattr(speech, 'speakTypedCharacters') else speech.speak([k[-1]])
            driver._flush(); return
        driver.press(self.b, key)
        if self._focus_requested: self.settle(moves_focus=True)

    def _escape(self):
        """kb:escape is browse mode's disablePassThrough: out of focus mode if in it; in browse mode it sends the key on to the page."""
        g = driver.Gesture('escape')
        def send(_=None): self.s.key('Escape'); self.settle()
        g.send = send
        import scriptHandler
        sc = scriptHandler._getObjScript(self.b, g, [])
        if sc is None: send(); return
        sc(g); driver._flush()

    def census(self):
        """Counts by chrome.automation role, to compare with the worker's accessibility-tree census (`censusFromAXTree`)."""
        n = {}
        for node in self.world.by_ix.values():
            r = node.raw.get('role')
            n[r] = n.get(r, 0) + 1
        landmarks = sum(n.get(r, 0) for r in ('banner', 'complementary', 'contentInfo', 'main', 'navigation', 'search', 'form', 'region'))
        return {'heading': n.get('heading', 0), 'link': n.get('link', 0), 'graphic': n.get('image', 0) + n.get('graphicsSymbol', 0), 'landmark': landmarks, 'roles': n}
