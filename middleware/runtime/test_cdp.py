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
