"""MS-001 to MS-007 — reading milestones."""

import unittest

from _milestones import DEFAULT, milestone
from lib.fake_github import FakeGitHub
from milestone_ops import Milestones


def ops(items=None):
    return Milestones(FakeGitHub(milestones=items if items is not None else DEFAULT))


class TestListing(unittest.TestCase):
    def test_it_returns_every_milestone(self):  # MS-001
        self.assertEqual(len(ops().list()), 4)

    def test_each_carries_its_number_and_state(self):  # MS-001
        first = ops().list()[0]
        self.assertEqual((first["number"], first["state"]), (1, "closed"))

    def test_each_carries_its_issue_counts(self):  # MS-001
        found = {m["number"]: m for m in ops().list()}
        self.assertEqual(found[2]["open_issues"], 4)
        self.assertEqual(found[1]["closed_issues"], 14)

    def test_the_order_is_by_number(self):  # MS-002
        numbers = [m["number"] for m in ops().list()]
        self.assertEqual(numbers, sorted(numbers))

    def test_the_order_is_stable_across_calls(self):  # MS-002
        self.assertEqual([m["number"] for m in ops().list()],
                         [m["number"] for m in ops().list()])


class TestFinding(unittest.TestCase):
    def test_an_exact_title(self):  # MS-003
        self.assertEqual(ops().find("v0.2 — Pipeline state")["number"], 2)

    def test_a_unique_prefix(self):  # MS-004
        self.assertEqual(ops().find("v0.2")["number"], 2)

    def test_matching_is_case_insensitive(self):  # MS-004
        self.assertEqual(ops().find("V0.2")["number"], 2)

    def test_a_non_version_title_by_prefix(self):  # MS-004
        self.assertEqual(ops().find("Direct Involvement")["number"], 6)

    def test_an_ambiguous_prefix_finds_nothing(self):  # MS-005
        self.assertIsNone(ops().find("v0."))

    def test_an_unmatched_title_finds_nothing(self):  # MS-005
        self.assertIsNone(ops().find("v9.9"))

    def test_it_searches_closed_milestones_too(self):  # MS-006
        self.assertEqual(ops().find("v0.1")["number"], 1)

    def test_open_only_can_be_requested(self):  # MS-006
        self.assertIsNone(ops().find("v0.1", state="open"))

    def test_an_exact_match_beats_a_prefix(self):  # MS-003
        items = [milestone(1, "v0.4"), milestone(2, "v0.4 — extended")]
        self.assertEqual(Milestones(FakeGitHub(milestones=items)).find("v0.4")["number"], 1)


class TestCounting(unittest.TestCase):
    def test_it_reports_open_work(self):  # MS-007
        self.assertEqual(ops().open_issue_count("v0.2"), 4)

    def test_a_finished_milestone_reports_zero(self):  # MS-007
        self.assertEqual(ops().open_issue_count("v0.1"), 0)

    def test_an_unknown_milestone_raises(self):  # MS-007
        with self.assertRaises(Exception):
            ops().open_issue_count("v9.9")


if __name__ == "__main__":
    unittest.main()
