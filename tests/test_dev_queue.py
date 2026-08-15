"""DEV-001 to DEV-024 — who is eligible, in what order, and how many."""

import unittest

import _dev  # noqa: F401
from lib.config import STATES
from select_queue import build_queue

LABELS = dict(STATES)


def issue(number, labels=("ready-for-work",), state="open", milestone="v0.3",
          blockers=(), depends_on=(), has_pr=False):
    return {
        "number": number,
        "state": state,
        "labels": [{"name": name} for name in labels],
        "milestone": milestone,
        "blockers": [dict(b) for b in blockers],
        "depends_on": list(depends_on),
        "has_open_pr": has_pr,
    }


def blocker(number, resolved=False, unknown=False):
    return {"number": number, "resolved": resolved, "unknown": unknown}


def queue(issues, **kwargs):
    kwargs.setdefault("labels", LABELS)
    return [i["number"] for i in build_queue(issues, **kwargs).issues]


class TestEligibility(unittest.TestCase):
    def test_an_approved_issue_is_eligible(self):  # DEV-001
        self.assertEqual(queue([issue(7)]), [7])

    def test_an_issue_in_another_state_is_not(self):  # DEV-001
        self.assertEqual(queue([issue(7, labels=("ai-triage",))]), [])

    def test_a_closed_issue_is_not(self):  # DEV-002
        self.assertEqual(queue([issue(7, state="closed")]), [])

    def test_a_parked_issue_is_not(self):  # DEV-003
        self.assertEqual(queue([issue(7, labels=("ready-for-work", "parked"))]), [])

    def test_an_issue_already_building_is_not(self):  # DEV-004
        self.assertEqual(queue([issue(7, labels=("in-progress",))]), [])

    def test_an_issue_with_an_open_pull_request_is_not(self):  # DEV-008
        self.assertEqual(queue([issue(7, has_pr=True)]), [])


class TestBlockedness(unittest.TestCase):
    def test_an_unresolved_blocker_makes_it_ineligible(self):  # DEV-005
        self.assertEqual(queue([issue(7, blockers=[blocker(42)])]), [])

    def test_a_resolved_blocker_does_not(self):  # DEV-006
        self.assertEqual(queue([issue(7, blockers=[blocker(42, resolved=True)])]), [7])

    def test_nothing_had_to_update_the_issue(self):  # DEV-006
        """The whole point of deriving: no label, no sweep, no wake-up."""
        unblocked = issue(7, blockers=[blocker(42, resolved=True)])
        self.assertNotIn("blocked", str(unblocked["labels"]))
        self.assertEqual(queue([unblocked]), [7])

    def test_one_unresolved_among_several_is_enough(self):  # DEV-005
        blockers = [blocker(42, resolved=True), blocker(43)]
        self.assertEqual(queue([issue(7, blockers=blockers)]), [])

    def test_an_unknown_blocker_makes_it_ineligible(self):  # DEV-007
        self.assertEqual(queue([issue(7, blockers=[blocker(42, unknown=True)])]), [])


class TestOrdering(unittest.TestCase):
    def test_a_soft_dependency_is_built_first(self):  # DEV-010
        self.assertEqual(queue([issue(7, depends_on=[8]), issue(8)]), [8, 7])

    def test_a_chain_is_ordered(self):  # DEV-010
        issues = [issue(7, depends_on=[8]), issue(8, depends_on=[9]), issue(9)]
        self.assertEqual(queue(issues), [9, 8, 7])

    def test_a_dependency_outside_the_queue_does_not_remove_it(self):  # DEV-011
        self.assertEqual(queue([issue(7, depends_on=[99])]), [7])

    def test_unrelated_issues_keep_number_order(self):  # DEV-012
        self.assertEqual(queue([issue(9), issue(7), issue(8)]), [7, 8, 9])

    def test_a_cycle_degrades_to_number_order(self):  # DEV-013
        issues = [issue(7, depends_on=[8]), issue(8, depends_on=[7])]
        self.assertEqual(queue(issues), [7, 8])

    def test_a_cycle_drops_nothing(self):  # DEV-013
        issues = [issue(7, depends_on=[8]), issue(8, depends_on=[7]), issue(9)]
        self.assertEqual(sorted(queue(issues)), [7, 8, 9])

    def test_the_focus_milestone_comes_first(self):  # DEV-014
        issues = [issue(7, milestone="v0.9"), issue(8, milestone="v0.3")]
        self.assertEqual(queue(issues, focus="v0.3"), [8, 7])

    def test_within_the_focus_number_order_holds(self):  # DEV-014
        issues = [issue(9, milestone="v0.3"), issue(8, milestone="v0.3")]
        self.assertEqual(queue(issues, focus="v0.3"), [8, 9])

    def test_a_dependency_beats_the_focus_preference(self):  # DEV-010
        """Building a dependent before its dependency is always wrong."""
        issues = [issue(7, milestone="v0.3", depends_on=[8]), issue(8, milestone="v0.9")]
        self.assertEqual(queue(issues, focus="v0.3"), [8, 7])


class TestTheCap(unittest.TestCase):
    def test_the_queue_is_capped(self):  # DEV-020
        self.assertEqual(queue([issue(n) for n in range(1, 6)], cap=2), [1, 2])

    def test_issues_already_building_count_against_it(self):  # DEV-021
        issues = [issue(1, labels=("in-progress",)), issue(2), issue(3)]
        self.assertEqual(queue(issues, cap=2), [2])

    def test_a_met_cap_yields_an_empty_queue(self):  # DEV-022
        issues = [issue(1, labels=("in-progress",)), issue(2, labels=("in-progress",)),
                  issue(3)]
        self.assertEqual(queue(issues, cap=2), [])

    def test_no_cap_means_no_limit(self):  # DEV-023
        self.assertEqual(len(queue([issue(n) for n in range(1, 6)], cap=None)), 5)

    def test_truncation_is_reported(self):  # DEV-024
        result = build_queue([issue(n) for n in range(1, 6)], labels=LABELS, cap=2)
        self.assertEqual(result.remaining, 3)

    def test_no_truncation_reports_nothing_left(self):  # DEV-024
        result = build_queue([issue(7)], labels=LABELS, cap=2)
        self.assertEqual(result.remaining, 0)


if __name__ == "__main__":
    unittest.main()
