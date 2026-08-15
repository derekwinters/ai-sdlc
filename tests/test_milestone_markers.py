"""MS-040 to MS-045 — the machine-read markers in a description.

The focus milestone is matched live from its description, so a milestone
created without the marker is invisible to the pipeline that consumes it.
"""

import unittest

from _milestones import DEFAULT
from lib.fake_github import FakeGitHub
from milestone_ops import Milestones, is_focus, is_frozen, set_marker, clear_marker


def ops(items=None):
    return Milestones(FakeGitHub(milestones=items if items is not None else DEFAULT))


class TestReadingMarkers(unittest.TestCase):
    def test_focus_is_recognised(self):  # MS-040
        self.assertTrue(is_focus("focus. the pilot"))

    def test_a_description_without_it_is_not_focus(self):  # MS-040
        self.assertFalse(is_focus("state and visibility"))

    def test_frozen_is_recognised(self):  # MS-042
        self.assertTrue(is_frozen("frozen. scope is settled"))

    def test_case_does_not_matter(self):  # MS-043
        self.assertTrue(is_focus("Focus. the pilot"))
        self.assertTrue(is_frozen("FROZEN. settled"))

    def test_a_marker_may_have_prose_around_it(self):  # MS-043
        self.assertTrue(is_frozen("the pilot. frozen. no more scope"))

    def test_an_empty_description_has_no_markers(self):  # MS-040
        self.assertFalse(is_focus(""))
        self.assertFalse(is_frozen(None))

    def test_a_word_containing_focus_is_not_the_marker(self):  # MS-040
        self.assertFalse(is_focus("refocusing the work"))


class TestSettingMarkers(unittest.TestCase):
    def test_setting_adds_the_marker(self):  # MS-044
        self.assertTrue(is_focus(set_marker("the pilot", "focus")))

    def test_setting_preserves_the_prose(self):  # MS-044
        self.assertIn("the pilot", set_marker("the pilot", "focus"))

    def test_setting_twice_does_not_duplicate(self):  # MS-044
        once = set_marker("the pilot", "focus")
        self.assertEqual(set_marker(once, "focus"), once)

    def test_setting_on_an_empty_description_works(self):  # MS-044
        self.assertTrue(is_focus(set_marker("", "focus")))

    def test_clearing_removes_it(self):  # MS-045
        self.assertFalse(is_focus(clear_marker("focus. the pilot", "focus")))

    def test_clearing_preserves_the_prose(self):  # MS-045
        self.assertIn("the pilot", clear_marker("focus. the pilot", "focus"))

    def test_clearing_an_absent_marker_changes_nothing(self):  # MS-045
        self.assertEqual(clear_marker("the pilot", "focus"), "the pilot")

    def test_clearing_one_marker_leaves_the_other(self):  # MS-045
        both = "focus. frozen. settled"
        self.assertTrue(is_frozen(clear_marker(both, "focus")))


class TestExactlyOneFocus(unittest.TestCase):
    def test_setting_focus_marks_the_target(self):  # MS-041
        api = FakeGitHub(milestones=list(DEFAULT))
        Milestones(api).set_focus("v0.2")
        self.assertTrue(is_focus(Milestones(api).find("v0.2")["description"]))

    def test_setting_focus_clears_the_previous_one(self):  # MS-041
        api = FakeGitHub(milestones=list(DEFAULT))
        Milestones(api).set_focus("v0.2")
        self.assertFalse(is_focus(Milestones(api).find("v0.1")["description"]))

    def test_the_previous_focus_keeps_its_prose(self):  # MS-041
        api = FakeGitHub(milestones=list(DEFAULT))
        Milestones(api).set_focus("v0.2")
        self.assertIn("the pilot", Milestones(api).find("v0.1")["description"])

    def test_setting_focus_on_the_current_focus_is_stable(self):  # MS-041
        api = FakeGitHub(milestones=list(DEFAULT))
        Milestones(api).set_focus("v0.1")
        self.assertTrue(is_focus(Milestones(api).find("v0.1")["description"]))

    def test_focus_reports_the_marked_milestone(self):  # MS-041
        self.assertEqual(ops().focus()["number"], 1)

    def test_no_focus_marked_reports_none(self):  # MS-041
        from _milestones import milestone

        self.assertIsNone(ops([milestone(1, "v0.1")]).focus())


if __name__ == "__main__":
    unittest.main()
