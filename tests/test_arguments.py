"""GK-040 to GK-043 — what an argument must be for the command to mean anything."""

import unittest

import _gatekeeper  # noqa: F401
from arguments import check_arguments, match_milestone
from parse_commands import parse

MILESTONES = [
    {"number": 1, "title": "v0.1 — Gatekeeper pilot", "state": "open"},
    {"number": 2, "title": "v0.2 — Pipeline state", "state": "open"},
    {"number": 6, "title": "Direct Involvement Needed", "state": "open"},
    {"number": 9, "title": "v0.0 — closed one", "state": "closed"},
]


def check(text, milestones=MILESTONES):
    return check_arguments(parse(text).actions, milestones)


def applied(result):
    return [a.command for a in result.actions]


def skip(result):
    return result.skips[0]


class TestCap(unittest.TestCase):
    def test_a_positive_integer_is_accepted(self):  # GK-040
        self.assertEqual(applied(check("/cap 3")), ["cap"])

    def test_the_value_is_carried_as_an_integer(self):  # GK-040
        self.assertEqual(check("/cap 3").actions[0].value, 3)

    def test_a_non_numeric_argument_is_refused(self):  # GK-040
        self.assertEqual(skip(check("/cap lots")).reason, "cap-not-a-number")

    def test_an_empty_argument_is_refused(self):  # GK-040
        self.assertEqual(skip(check("/cap")).reason, "cap-not-a-number")

    def test_zero_is_refused(self):  # GK-041
        self.assertEqual(skip(check("/cap 0")).reason, "cap-not-positive")

    def test_a_negative_number_is_refused(self):  # GK-041
        self.assertEqual(skip(check("/cap -1")).reason, "cap-not-positive")

    def test_a_decimal_is_refused(self):  # GK-040
        self.assertEqual(skip(check("/cap 1.5")).reason, "cap-not-a-number")


class TestMatchingAMilestone(unittest.TestCase):
    def test_an_exact_title_matches(self):  # GK-042
        self.assertEqual(match_milestone("v0.1 — Gatekeeper pilot", MILESTONES)["number"], 1)

    def test_a_number_prefix_matches(self):  # GK-042
        self.assertEqual(match_milestone("v0.1", MILESTONES)["number"], 1)

    def test_matching_is_case_insensitive(self):  # GK-042
        self.assertEqual(match_milestone("V0.1", MILESTONES)["number"], 1)

    def test_a_non_version_title_matches_by_prefix_too(self):  # GK-042
        self.assertEqual(match_milestone("Direct Involvement", MILESTONES)["number"], 6)

    def test_a_closed_milestone_does_not_match(self):  # GK-042
        self.assertIsNone(match_milestone("v0.0", MILESTONES))

    def test_an_unmatched_title_is_none(self):  # GK-043
        self.assertIsNone(match_milestone("v9.9", MILESTONES))

    def test_an_ambiguous_prefix_is_none(self):  # GK-043
        """Two candidates is not a match; picking one would be a guess."""
        self.assertIsNone(match_milestone("v0.", MILESTONES))


class TestMilestoneArguments(unittest.TestCase):
    def test_a_matched_milestone_is_applied(self):  # GK-042
        self.assertEqual(applied(check("/milestone v0.1")), ["milestone"])

    def test_the_resolved_number_is_carried(self):  # GK-042
        self.assertEqual(check("/milestone v0.1").actions[0].value, 1)

    def test_an_unmatched_milestone_is_refused(self):  # GK-043
        self.assertEqual(skip(check("/milestone v9.9")).reason, "no-such-milestone")

    def test_the_refusal_lists_the_open_milestones(self):  # GK-043
        detail = skip(check("/milestone v9.9")).detail
        self.assertIn("v0.1 — Gatekeeper pilot", detail)
        self.assertIn("Direct Involvement Needed", detail)

    def test_the_refusal_does_not_list_closed_ones(self):  # GK-043
        self.assertNotIn("closed one", skip(check("/milestone v9.9")).detail)

    def test_an_empty_milestone_argument_is_refused(self):  # GK-043
        self.assertEqual(skip(check("/milestone")).reason, "no-such-milestone")

    def test_focus_resolves_the_same_way(self):  # GK-042
        self.assertEqual(check("/focus v0.2").actions[0].value, 2)

    def test_an_unmatched_focus_is_refused(self):  # GK-043
        self.assertEqual(skip(check("/focus v9.9")).reason, "no-such-milestone")


class TestOtherCommandsAreUnaffected(unittest.TestCase):
    def test_approve_needs_no_argument(self):  # GK-040
        self.assertEqual(applied(check("/approve")), ["approve"])

    def test_revise_keeps_its_free_text(self):  # GK-024
        self.assertEqual(check("/revise try again").actions[0].argument, "try again")

    def test_revise_is_not_milestone_matched(self):  # GK-042
        self.assertEqual(applied(check("/revise v9.9")), ["revise"])


if __name__ == "__main__":
    unittest.main()
