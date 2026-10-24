"""The part of cdp.py that routes answers: commands sent together are answered in the order they were sent, and what waits for a page that is closed is told so and does not wait for the timeout (A11-208:
a tree read of a page the test had just closed held the reading of every page after it for twenty seconds)."""
import json, threading, unittest

import cdp


class FakeSocket:
    def __init__(self): self.sent = []
    def send(self, text): self.sent.append(json.loads(text))
    def close(self): pass


def reader():
    c = cdp.Cdp.__new__(cdp.Cdp)      # not connected: nothing is read from a browser
    c.ws = FakeSocket(); c.lock = threading.Lock(); c.next_id = 0; c.replies = {}; c.wanted = {}; c.wake = threading.Condition(); c.on_tree = None; c.converters = {}; c.generation = 0; c.target_of = {}
    return c


class BrowserBuild(unittest.TestCase):
    def test_the_build_is_read_from_what_the_browser_calls_itself(self):
        self.assertEqual(cdp.browser_build('HeadlessChrome/156.0.8078.4'), '156.0.8078.4')
        self.assertEqual(cdp.browser_build('Chrome/153.0.8010.12'), '153.0.8010.12')
        self.assertEqual(cdp.browser_build('Edg/155.0.4283.1'), '155.0.4283.1')

    def test_a_browser_that_names_no_build_has_none(self):
        self.assertIsNone(cdp.browser_build(None))
        self.assertIsNone(cdp.browser_build('Chrome'))

    def test_the_build_is_told_to_whoever_wants_to_know_a_page_was_attached(self):
        c = reader(); c.browser = '156.0.8078.4'; told = []; c.on_attach = lambda target, browser: told.append((target, browser)); c.installed = set(); c.on_tree = None
        c._install('s', 't')
        self.assertEqual(told, [('t', '156.0.8078.4')])


class TakingOverTheTrees(unittest.TestCase):
    """The extension did not come up (fallback.py): the pages that are open are told to note their changes, and the port is where the trees come from from then on."""
    def test_open_pages_are_told_to_note_their_changes_and_are_read_once_and_later_pages_are_held_for_their_listener(self):
        c = reader(); c.target_of = {'s1': 't1', 's2': 't2'}; c.stopped = True      # the tree reader thread starts and ends at once
        c.enable_trees(lambda snap: None)
        sent = [(m['method'], m.get('sessionId'), m['params']) for m in c.ws.sent]
        self.assertIn(('Target.setAutoAttach', None, {'autoAttach': True, 'waitForDebuggerOnStart': True, 'flatten': True}), sent)
        for session in ('s1', 's2'):
            self.assertIn(('Runtime.evaluate', session, {'expression': cdp.TICKS_ON}), sent)
            self.assertIn(('Page.addScriptToEvaluateOnNewDocument', session, {'source': cdp.TICKS_ON}), sent)
        self.assertEqual(c.wanted, {'s1': {'fallback'}, 's2': {'fallback'}})

    def test_it_does_nothing_when_the_trees_already_come_from_the_port(self):
        c = reader(); c.on_tree = lambda snap: None; c.target_of = {'s1': 't1'}
        c.enable_trees(lambda snap: None)
        self.assertEqual(c.ws.sent, [])

    def test_the_listener_notes_changes_only_where_asked_to_or_once_told_to(self):
        self.assertIn("const ticksOn = () => __TICKS__ || window.__aeTicksOn === true", cdp.LISTENER)
        self.assertEqual(cdp.TICKS_ON, 'window.__aeTicksOn = true')


class Routing(unittest.TestCase):
    def test_commands_sent_together_are_answered_in_the_order_they_were_sent_whatever_order_the_browser_answers_in(self):
        c = reader(); out = []
        thread = threading.Thread(target=lambda: out.extend(c.call_many([('A.one', {}), ('B.two', {'x': 1})], session='s')))
        thread.start()
        while len(c.ws.sent) < 2: pass
        first, second = c.ws.sent
        self.assertEqual((first['method'], second['method'], second['params'], first['sessionId']), ('A.one', 'B.two', {'x': 1}, 's'))
        c._handle({'id': second['id'], 'result': {'n': 2}}); c._handle({'id': first['id'], 'result': {'n': 1}})
        thread.join(2)
        self.assertEqual(out, [{'n': 1}, {'n': 2}])

    def test_what_waits_for_a_page_is_told_when_the_page_goes_and_does_not_wait_for_the_timeout(self):
        c = reader(); errors = []
        def ask():
            try: c.call_many([('Accessibility.getFullAXTree', {})], session='gone', timeout=30)
            except RuntimeError as e: errors.append(str(e))
        thread = threading.Thread(target=ask); thread.start()
        while not c.ws.sent: pass
        c._handle({'method': 'Target.detachedFromTarget', 'params': {'sessionId': 'gone'}})
        thread.join(2)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, ['Accessibility.getFullAXTree: the page was closed'])

    def test_a_page_that_goes_takes_what_was_wanted_of_it_and_its_converter_with_it(self):
        c = reader(); c.target_of = {'gone': 't'}; c.wanted = {'gone': {'focusin'}, 'other': {'tick'}}; c.converters = {(0, 't'): object(), (0, 'u'): object()}
        c._handle({'method': 'Target.detachedFromTarget', 'params': {'sessionId': 'gone'}})
        self.assertEqual(c.wanted, {'other': {'tick'}}); self.assertEqual(list(c.converters), [(0, 'u')])

    def test_a_note_from_the_page_asks_for_a_tree_and_is_not_an_event_for_the_predictor(self):
        c = reader(); c.on_tree = lambda snap: None; c.target_of = {'s': 't'}; c.url_of = {'t': 'http://x/'}; events = []; c.on_event = events.append
        c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'payload': json.dumps({'e': 'tick', 'why': 'mutation'})}})
        c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'payload': json.dumps({'e': 'focusin', 'tag': 'a'})}})
        self.assertEqual([e['e'] for e in events], ['focusin']); self.assertEqual(events[0]['pageUrl'], 'http://x/')
        self.assertEqual(c.wanted, {'s': {'mutation', 'focusin'}})

    def test_without_a_tree_reader_a_note_from_the_page_asks_for_nothing(self):
        c = reader(); c.target_of = {'s': 't'}; c.url_of = {}; c.on_event = lambda e: None
        c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'payload': json.dumps({'e': 'focusin', 'tag': 'a'})}})
        self.assertEqual(c.wanted, {})


if __name__ == '__main__': unittest.main()
