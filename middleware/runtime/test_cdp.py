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
    c.ws = FakeSocket(); c.lock = threading.Lock(); c.next_id = 0; c.replies = {}; c.wanted = {}; c.wake = threading.Condition(); c.on_tree = None; c.converters = {}; c.generation = 0; c.target_of = {}; c.outbox = []; c.out = threading.Lock()
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


class KeepingTheReads(unittest.TestCase):
    """AE_RAW=<file>: what a tree read was given is kept, one line for each read, for the fixtures test_axtree.py converts (A11-229)."""
    def test_each_read_is_one_line_of_the_file(self):
        import os, tempfile
        raw = {'ax': [{'nodeId': '1'}], 'dom': {'strings': [], 'documents': []}}
        with tempfile.TemporaryDirectory() as dir:
            path = os.path.join(dir, 'raw.jsonl'); c = reader(); was = cdp.RAW_LOG
            try:
                cdp.RAW_LOG = path; c._keep(raw); c._keep({'ax': []})
                self.assertEqual([json.loads(line) for line in open(path)], [raw, {'ax': []}])
            finally: cdp.RAW_LOG = was


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


class Resolving(unittest.TestCase):
    """A11-234: a `focusin` is told on once the browser has said which DOM node the element is, and what role and name it computed; and told on as it was if the browser cannot say."""
    def setUp(self):
        self.c = reader(); self.c.on_tree = lambda snap: None; self.c.target_of = {'s': 't'}; self.c.url_of = {'t': 'http://x/'}; self.told = []; self.c.on_event = self.told.append
        self.c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'executionContextId': 7, 'payload': json.dumps({'e': 'focusin', 'seq': 3, 'tag': 'a', 'names': ['Read more']})}})

    def answer(self, method, result=None, error=None):
        sent = next(m for m in self.c.ws.sent if m['method'] == method)
        self.c._handle({'id': sent['id'], **({'error': {'message': error}} if error else {'result': result})})
        return sent

    def test_the_element_is_asked_for_in_the_frame_it_was_focused_in_and_nothing_is_told_before_it_is_answered(self):
        first = self.c.ws.sent[0]
        self.assertEqual((first['method'], first['sessionId'], first['params']['contextId']), ('Runtime.evaluate', 's', 7))
        self.assertIn('__aeFocused', first['params']['expression']); self.assertIn('get(3)', first['params']['expression'])
        self.assertEqual(self.told, []); self.assertEqual(self.c.wanted, {})      # the tree is read after the element is resolved, not ahead of it

    def test_the_dom_node_and_the_role_and_name_the_browser_computed_are_added_and_the_element_is_let_go(self):
        self.answer('Runtime.evaluate', {'result': {'objectId': 'obj-1'}})
        node = self.answer('DOM.describeNode', {'node': {'backendNodeId': 41}})
        ax = next(m for m in self.c.ws.sent if m['method'] == 'Accessibility.getPartialAXTree')
        self.assertEqual((node['params'], ax['params']), ({'objectId': 'obj-1'}, {'objectId': 'obj-1', 'fetchRelatives': False}))
        self.assertEqual(self.told, [])      # both answers are needed
        self.answer('Accessibility.getPartialAXTree', {'nodes': [{'backendDOMNodeId': 41, 'name': {'value': 'Read more (link opens a new window)'}, 'chromeRole': {'value': 110}}]})
        self.assertEqual(len(self.told), 1)
        self.assertEqual({k: self.told[0][k] for k in ('backendNodeId', 'axName', 'axRole')}, {'backendNodeId': 41, 'axName': 'Read more (link opens a new window)', 'axRole': 'link'})
        self.assertIn('Runtime.releaseObject', [m['method'] for m in self.c.ws.sent])
        self.assertEqual(self.c.wanted, {'s': {'focusin'}})      # and now the tree is read

    def test_an_element_that_is_gone_is_told_on_as_the_page_sent_it(self):
        self.answer('Runtime.evaluate', {'result': {'type': 'undefined'}})
        self.assertEqual(len(self.told), 1); self.assertNotIn('backendNodeId', self.told[0]); self.assertEqual(self.told[0]['names'], ['Read more']); self.assertEqual(self.c.wanted, {'s': {'focusin'}})

    def test_a_page_that_is_closed_before_the_browser_answers_is_told_on_as_the_page_sent_it_once(self):
        self.c._handle({'method': 'Target.detachedFromTarget', 'params': {'sessionId': 's'}})
        self.assertEqual(len(self.told), 1); self.assertNotIn('backendNodeId', self.told[0])

    def test_an_element_the_browser_can_name_a_node_for_but_not_a_role_is_told_with_the_node(self):
        self.answer('Runtime.evaluate', {'result': {'objectId': 'obj-1'}})
        self.answer('DOM.describeNode', {'node': {'backendNodeId': 41}})
        self.answer('Accessibility.getPartialAXTree', {'nodes': [{'backendDOMNodeId': 41, 'ignored': True}]})
        self.assertEqual({k: self.told[0].get(k) for k in ('backendNodeId', 'axName', 'axRole')}, {'backendNodeId': 41, 'axName': None, 'axRole': None})

    def test_an_event_from_an_older_listener_with_no_number_is_told_at_once(self):
        c = reader(); c.on_tree = lambda snap: None; c.target_of = {'s': 't'}; c.url_of = {}; told = []; c.on_event = told.append
        c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'payload': json.dumps({'e': 'focusin', 'tag': 'a'})}})
        self.assertEqual(len(told), 1); self.assertEqual(c.ws.sent, [])


    def binding(self, payload, context=7):
        self.c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'executionContextId': context, 'payload': json.dumps(payload)}})

    def test_an_event_after_a_focus_that_waits_for_the_browser_is_told_after_it_and_not_before(self):
        """A key typed after a focus move is heard after the move: events are handed on in the order the page made them."""
        self.binding({'e': 'keydown', 'key': 'a'})
        self.assertEqual(self.told, [])
        self.answer('Runtime.evaluate', {'result': {'type': 'undefined'}})      # the focus is told on, and the key with it
        self.assertEqual([e['e'] for e in self.told], ['focusin', 'keydown'])

    def test_a_browser_that_does_not_answer_leaves_the_event_as_it_was_after_a_while_and_the_events_behind_it_are_not_held_for_ever(self):
        import time
        cdp.Resolution.WAIT = 0.05
        try:
            self.setUp(); self.binding({'e': 'keydown', 'key': 'a'})
            for _ in range(100):
                if len(self.told) == 2: break
                time.sleep(0.02)
        finally: cdp.Resolution.WAIT = 1.5
        self.assertEqual([e['e'] for e in self.told], ['focusin', 'keydown']); self.assertNotIn('backendNodeId', self.told[0])
        self.assertEqual(self.c.wanted, {'s': {'focusin', 'keydown'}})

    def test_a_number_that_is_not_one_is_not_asked_about_and_does_not_end_the_reader(self):
        for seq in ('x', None, [1], True):
            c = reader(); c.on_tree = lambda snap: None; c.target_of = {'s': 't'}; c.url_of = {}; told = []; c.on_event = told.append
            c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'payload': json.dumps({'e': 'focusin', 'seq': seq, 'tag': 'a'})}})
            self.assertEqual(len(told), 1, seq); self.assertEqual(c.ws.sent, [], seq)

    def test_a_frame_that_is_not_named_is_asked_in_the_default_context_and_the_page_is_not_left_holding_the_element(self):
        c = reader(); c.on_tree = lambda snap: None; c.target_of = {'s': 't'}; c.url_of = {}; c.on_event = lambda e: None
        c._handle({'method': 'Runtime.bindingCalled', 'sessionId': 's', 'params': {'name': '__ae', 'payload': json.dumps({'e': 'focusin', 'seq': 5, 'tag': 'a'})}})
        self.assertNotIn('contextId', c.ws.sent[0]['params'])
        for m in list(c.ws.sent): c._handle({'id': m['id'], 'result': {'result': {'objectId': 'o'}}})
        c._handle({'id': c.ws.sent[1]['id'], 'result': {'node': {'backendNodeId': 4}}}); c._handle({'id': c.ws.sent[2]['id'], 'result': {'nodes': []}})
        self.assertTrue(any(m['method'] == 'Runtime.evaluate' and 'delete(5)' in m['params']['expression'] for m in c.ws.sent))


class Converting(unittest.TestCase):
    def test_a_page_that_went_while_it_was_read_leaves_no_converter_behind(self):
        import axtree
        c = reader(); c.target_of = {'s': 't'}
        raw = {'ax': [{'nodeId': '1', 'chromeRole': {'value': 5}, 'childIds': []}], 'dom': {'documents': [], 'strings': []}, 'viewport': {}, 'page': {'url': 'http://x/', 'title': 't', 'readyState': 'complete', 'lang': 'en', 'caret': None}, 'frames': {}}
        real = axtree.fetch
        axtree.fetch = lambda call: (c._handle({'method': 'Target.detachedFromTarget', 'params': {'sessionId': 's'}}), raw)[1]
        try: c._read('s', 't', 0)
        finally: axtree.fetch = real
        self.assertEqual(c.converters, {})

    def test_a_page_closed_while_it_is_read_is_converted_by_the_converter_it_had_so_that_its_nodes_keep_their_numbers(self):
        """The converter is forgotten when the page goes (`Target.detachedFromTarget`); a read in flight that took a new one would number the document's nodes again, and the predictor would speak the page's load again."""
        import axtree
        made = []
        class Counting(axtree.Converter):
            def __init__(self): super().__init__(); made.append(self)
        c = reader(); c.target_of = {'s': 't'}
        real_fetch, real_converter = axtree.fetch, axtree.Converter
        raw = {'ax': [{'nodeId': '1', 'chromeRole': {'value': 5}, 'childIds': []}], 'dom': {'documents': [], 'strings': []}, 'viewport': {}, 'page': {'url': 'http://x/', 'title': 't', 'readyState': 'complete', 'lang': 'en', 'caret': None}, 'frames': {}}
        reads = []
        def fetch(call):
            reads.append(1)
            if len(reads) == 2: c._handle({'method': 'Target.detachedFromTarget', 'params': {'sessionId': 's'}})      # the page goes while its second tree is being read
            return raw
        axtree.fetch, axtree.Converter = fetch, Counting
        try:
            first = c._read('s', 't', 0); second = c._read('s', 't', 0)
        finally: axtree.fetch, axtree.Converter = real_fetch, real_converter
        self.assertEqual(len(made), 1)
        self.assertEqual(first['nodes'][0]['uid'], second['nodes'][0]['uid'])


if __name__ == '__main__': unittest.main()
