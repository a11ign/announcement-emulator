"""python3 -m unittest discover -s middleware/runtime -t middleware/runtime   (from the repository root)

The three flags, each with a case that must raise it and a case that must not. The rules are in flags.py and were fixed before any corpus page was run; these are what they are held to."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flags


def speech(t, text, shape, cause='focus', role='button', name='Save', page=1, in_dialog=False):
    return {'kind': 'speech', 'cause': cause, 't': t, 'page': page, 'text': text, 'shape': shape, 'node': {'role': role, 'name': name, 'inDialog': in_dialog}}


def observe(t, what, text='', name=None, page=1):
    return {'kind': 'observe', 'what': what, 't': t, 'page': page, 'text': text, 'node': {'role': 'dialog' if what == 'dialog' else 'input', 'name': name}}


def names(records): return [f['flag'] for f in flags.derive_flags(records)]


class FocusWithoutName(unittest.TestCase):
    def test_a_button_with_no_name_is_flagged(self):
        self.assertEqual(names([speech(10, 'button', ['ROLE'], name=None)]), ['focus-without-name'])

    def test_a_button_with_a_name_is_not(self):
        self.assertEqual(names([speech(10, 'Save, button', ['NAME', 'ROLE'])]), [])

    def test_an_element_with_no_name_that_is_spoken_by_a_name_of_its_own_is_not(self):
        """An image link NVDA names by its address has no accessible name, and is not silent."""
        self.assertEqual(names([speech(10, 'example.com/x, link', ['NAME', 'ROLE'], role='link', name='')]), [])

    def test_the_document_taking_focus_is_not_a_control(self):
        self.assertEqual(names([speech(10, 'document', ['ROLE'], role='rootWebArea', name=None)]), [])

    def test_only_a_focus_move_is_judged(self):
        self.assertEqual(names([speech(10, 'button', ['ROLE'], cause='load', name=None)]), [])


class SilentDialog(unittest.TestCase):
    def test_a_dialog_with_nothing_said_for_it_is_flagged(self):
        self.assertEqual(names([observe(100, 'dialog', name='Cookies'), speech(95, 'Cookie settings, button', ['NAME', 'ROLE'])]), ['silent-dialog'])

    def test_focus_moving_into_the_dialog_is_it_being_said(self):
        self.assertEqual(names([observe(100, 'dialog'), speech(101, 'Keep, button', ['NAME', 'ROLE'], in_dialog=True)]), [])

    def test_the_focus_move_dated_a_few_ms_before_the_report_still_counts(self):
        self.assertEqual(names([observe(100, 'dialog'), speech(100 - flags.LAG_MS + 1, 'Keep, button', ['NAME', 'ROLE'], in_dialog=True)]), [])

    def test_a_live_region_saying_it_counts(self):
        self.assertEqual(names([observe(100, 'dialog'), speech(300, 'Session expired', ['NAME'], cause='live', role=None)]), [])

    def test_speech_after_the_window_does_not(self):
        self.assertEqual(names([observe(100, 'dialog'), speech(100 + flags.WINDOW_MS + 1, 'Keep, button', ['NAME', 'ROLE'], in_dialog=True)]), ['silent-dialog'])

    def test_speech_of_another_page_does_not(self):
        self.assertEqual(names([observe(100, 'dialog'), speech(101, 'Keep, button', ['NAME', 'ROLE'], in_dialog=True, page=2)]), ['silent-dialog'])


class UnheardError(unittest.TestCase):
    def test_an_error_that_nothing_says_is_flagged(self):
        self.assertEqual(names([observe(100, 'error', 'Enter an email address', name='Email'), speech(101, 'Email, edit, invalid entry', ['NAME', 'ROLE', 'STATE'])]), ['unheard-error'])

    def test_an_error_a_live_region_says_is_not(self):
        self.assertEqual(names([observe(100, 'error', 'Enter an email address'), speech(120, 'Enter an email address', ['NAME'], cause='live', role=None)]), [])

    def test_the_words_may_be_spread_over_several_utterances(self):
        self.assertEqual(names([observe(100, 'error', 'Enter an email address'), speech(110, 'Enter an email', ['NAME'], cause='live'), speech(120, 'address', ['NAME'], cause='live')]), [])

    def test_one_word_missing_is_not_heard(self):
        self.assertEqual(names([observe(100, 'error', 'Enter an email address'), speech(110, 'Enter an email', ['NAME'], cause='live')]), ['unheard-error'])

    def test_flags_come_back_in_time_order(self):
        records = [observe(300, 'error', 'Bad'), observe(100, 'dialog')]
        self.assertEqual(names(records), ['silent-dialog', 'unheard-error'])


if __name__ == '__main__': unittest.main()
