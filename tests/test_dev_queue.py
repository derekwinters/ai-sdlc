"""DEV-001 to DEV-033 — stated, not run.

`build_queue` was pure and would have worked in a consumer; `take(api, …)` was
not and could not. They shipped together as one skill, and a skill that is half
usable is a skill nobody can rely on (#153).

Both are instructions now. `test_dev_agent.py` has always covered `DEV-040`
onwards this way — the agent's contract was prose before any of this — so the
pattern here is the existing one, extended to the queue it operates on.
"""

import unittest

from _dev import stated


class TestEligibility(unittest.TestCase):
    def test_the_approved_state_is_required(self):  # DEV-001
        self.assertIn("carries the **approved** state label", stated())

    def test_a_closed_issue_is_never_eligible(self):  # DEV-002
        self.assertIn("closed issue is never eligible", stated())

    def test_a_parked_issue_is_never_eligible(self):  # DEV-003
        self.assertIn("not parked", stated())

    def test_an_issue_already_building_is_taken(self):  # DEV-004
        self.assertIn("not already building", stated())

    def test_an_unresolved_hard_blocker_gates(self):  # DEV-005
        self.assertIn("every hard blocker is resolved", stated())

    def test_resolution_needs_nothing_to_notice(self):  # DEV-006
        self.assertIn("becomes eligible on its own", stated())

    def test_an_unknown_blocker_gates(self):  # DEV-007
        self.assertIn("unknown** blocker is not eligible", stated())

    def test_an_open_pull_request_gates(self):  # DEV-008
        self.assertIn("no open pull request", stated())


class TestOrdering(unittest.TestCase):
    def test_a_dependency_is_built_first(self):  # DEV-010
        self.assertIn("built **after** what it follows", stated())

    def test_an_ineligible_dependency_does_not_remove_the_dependent(self):  # DEV-011
        self.assertIn(
            "soft dependency on an ineligible issue does not remove the dependent", stated()
        )

    def test_unrelated_issues_keep_number_order(self):  # DEV-012
        self.assertIn("keep **issue-number order**", stated())

    def test_a_cycle_degrades_rather_than_loops(self):  # DEV-013
        text = stated()
        self.assertIn("cycle among soft dependencies degrades to issue-number order", text)
        self.assertIn("would hang the run", text)

    def test_the_focus_milestone_is_preferred_but_yields(self):  # DEV-014
        text = stated()
        self.assertIn("then the focus milestone, then issue number", text)
        self.assertIn("dependency always beats the focus preference", text)


class TestTheCap(unittest.TestCase):
    def test_the_cap_limits_the_queue(self):  # DEV-020
        self.assertIn("concurrency cap limits the queue", stated())

    def test_issues_building_count_against_it(self):  # DEV-021
        self.assertIn("already building count against it", stated())

    def test_a_met_cap_is_an_empty_queue(self):  # DEV-022
        self.assertIn("empty queue, not an error", stated())

    def test_no_cap_means_no_limit(self):  # DEV-023
        self.assertIn("no cap configured means no limit", stated())

    def test_truncation_is_reported(self):  # DEV-024
        """A silent cap makes a partial run look like a complete one."""
        self.assertIn("say how many were left", stated())


class TestClaiming(unittest.TestCase):
    def test_taking_moves_it_to_building(self):  # DEV-030
        self.assertIn("move the issue to the **building** state", stated())

    def test_eligibility_is_rechecked_before_writing(self):  # DEV-031
        text = stated()
        self.assertIn("re-check eligibility immediately before writing", text)
        self.assertIn("two builders end up on one issue", text)

    def test_one_issue_at_a_time(self):  # DEV-032
        self.assertIn("one issue at a time", stated())

    def test_the_branch_derives_from_the_number(self):  # DEV-033
        self.assertIn("claude/issue-<number>", stated())


if __name__ == "__main__":
    unittest.main()
