"""The runtime's two rules for an extension that does not come up (fallback.py), and the record main.py writes for a browser it reached (A11-230). None needs NVDA or a browser."""
import unittest

import fallback, main


class Due(unittest.TestCase):
    def test_it_is_due_when_a_page_was_seen_and_the_extension_has_said_nothing_for_as_long_as_it_was_to_wait(self):
        self.assertTrue(fallback.due(5, 100.0, False, False, 105.0))
        self.assertTrue(fallback.due(5, 100.0, False, False, 130.0))

    def test_it_is_not_due_before_that_time(self):
        self.assertFalse(fallback.due(5, 100.0, False, False, 104.9))

    def test_it_is_not_due_before_any_page_was_seen(self):
        self.assertFalse(fallback.due(5, None, False, False, 1000.0))

    def test_it_is_not_due_once_the_extension_has_spoken_or_the_switch_is_made_or_nobody_asked_for_it(self):
        self.assertFalse(fallback.due(5, 100.0, True, False, 200.0))
        self.assertFalse(fallback.due(5, 100.0, False, True, 200.0))
        self.assertFalse(fallback.due(0, 100.0, False, False, 200.0))


class AfterTheSwitch(unittest.TestCase):
    def test_the_extensions_trees_and_restarts_are_dropped_and_the_ports_are_kept(self):
        self.assertTrue(fallback.from_extension_after_switch('snap', {'seq': 1}))
        self.assertFalse(fallback.from_extension_after_switch('snap', {'seq': 1, 'devtools': True}))
        self.assertTrue(fallback.from_extension_after_switch('ready', {'t': 1}))
        self.assertFalse(fallback.from_extension_after_switch('ready', {'t': 1, 'source': 'devtools'}))

    def test_what_the_page_itself_says_is_kept(self):
        for kind in ('page', 'attached', 'error', 'hello'): self.assertFalse(fallback.from_extension_after_switch(kind, {}))

    def test_the_reason_says_how_long_it_waited_and_where_the_trees_come_from_now(self):
        self.assertEqual(fallback.reason(5), 'the extension did not come up within 5 s of the first page, so the trees are read through the DevTools port')


class StartRecords(unittest.TestCase):
    def test_the_record_for_a_browser_that_was_reached_carries_its_build(self):
        self.assertEqual(main.start_record('attached', {'target': 't', 'browser': '156.0.8078.4'}, 12.5),
                         {'kind': 'start', 'what': 'devtools', 't': 12500, 'browser': '156.0.8078.4'})

    def test_a_browser_that_named_no_build_has_none_in_its_record(self):
        self.assertIsNone(main.start_record('attached', {'target': 't', 'browser': None}, 1.0)['browser'])

    def test_the_extension_and_the_port_each_say_when_they_came_up(self):
        self.assertEqual(main.start_record('ready', {'t': 5, 'desktopChildren': 1}, 0)['what'], 'extension')
        self.assertEqual(main.start_record('ready', {'t': 5, 'source': 'devtools'}, 0)['what'], 'tree-source')

    def test_what_is_no_start_has_no_record(self):
        self.assertIsNone(main.start_record('page', {}, 0))


if __name__ == '__main__': unittest.main()
