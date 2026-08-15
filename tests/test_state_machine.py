"""GK-001 to GK-005 — applying a command to an issue's labels.

One state at a time, and only state labels are touched. The triage decision
lives in the other labels — area, type, skip-docs — and a state change that
dropped them would discard it.
"""

import unittest

import _gatekeeper  # noqa: F401
from apply_actions import MOVES, WRITTEN_BY_OTHERS, plan_labels
from lib.config import STATES
from parse_commands import Action

LABELS = dict(STATES)
ALL_STATES = set(LABELS.values())


def plan(current, *commands):
    return plan_labels(current, [Action(c) for c in commands], labels=LABELS)


class TestOneStateAtATime(unittest.TestCase):
    def test_applying_a_state_leaves_exactly_one(self):  # GK-001
        result = plan(["ai-triage"], "approve")
        self.assertEqual(len(set(result) & ALL_STATES), 1)

    def test_the_previous_state_is_replaced(self):  # GK-002
        self.assertNotIn("ai-triage", plan(["ai-triage"], "approve"))

    def test_the_new_state_is_present(self):  # GK-002
        self.assertIn("ready-for-work", plan(["ai-triage"], "approve"))

    def test_starting_from_no_state_still_ends_with_one(self):  # GK-001
        self.assertEqual(set(plan([], "admit")) & ALL_STATES, {"ai-triage"})

    def test_a_malformed_issue_with_two_states_is_reduced_to_one(self):  # GK-001
        result = plan(["ai-triage", "parked"], "approve")
        self.assertEqual(set(result) & ALL_STATES, {"ready-for-work"})

    def test_several_commands_apply_in_order(self):  # GK-025
        self.assertEqual(set(plan([], "admit", "park")) & ALL_STATES, {"parked"})


class TestOnlyStateLabelsAreTouched(unittest.TestCase):
    def test_classification_labels_survive(self):  # GK-003
        result = plan(["ai-triage", "area:build", "type:bug"], "approve")
        self.assertIn("area:build", result)
        self.assertIn("type:bug", result)

    def test_skip_docs_survives(self):  # GK-003
        self.assertIn("skip-docs", plan(["ai-triage", "skip-docs"], "approve"))

    def test_an_epic_label_survives(self):  # GK-004
        self.assertIn("type:epic", plan(["type:epic", "ai-triage"], "park"))

    def test_a_wireframe_label_survives(self):  # GK-004
        self.assertIn("type:wireframe", plan(["type:wireframe"], "admit"))

    def test_no_classification_label_is_ever_added(self):  # GK-003
        before = ["area:build"]
        after = plan(before, "approve")
        self.assertEqual(set(after) - ALL_STATES, set(before))


class TestWhichCommandsMoveState(unittest.TestCase):
    def test_admit_goes_to_triage(self):  # GK-002
        self.assertIn("ai-triage", plan([], "admit"))

    def test_approve_goes_to_ready(self):  # GK-002
        self.assertIn("ready-for-work", plan(["pending-approval"], "approve"))

    def test_unpark_returns_to_triage(self):  # GK-002
        self.assertIn("ai-triage", plan(["parked"], "unpark"))

    def test_redo_returns_to_ready(self):  # GK-002
        self.assertIn("ready-for-work", plan([], "redo"))

    def test_revise_returns_to_triage(self):  # GK-002
        self.assertIn("ai-triage", plan(["pending-approval"], "revise"))

    def test_propose_goes_to_triage(self):  # GK-002
        self.assertIn("ai-triage", plan([], "propose"))

    def test_milestone_changes_no_labels(self):  # GK-002
        self.assertEqual(plan(["ai-triage"], "milestone"), ["ai-triage"])

    def test_focus_changes_no_labels(self):  # GK-002
        self.assertEqual(plan(["ai-triage"], "focus"), ["ai-triage"])

    def test_cap_changes_no_labels(self):  # GK-002
        self.assertEqual(plan(["ai-triage"], "cap"), ["ai-triage"])

    def test_retry_changes_no_labels_itself(self):  # GK-002
        self.assertEqual(plan(["ai-triage"], "retry"), ["ai-triage"])


class TestStatesTheGatekeeperNeverWrites(unittest.TestCase):
    """GK-005 — analysis and the builder own these.

    The gatekeeper reads them and moves issues out of them, but writing one
    would let it manufacture a state implying work it has not done.
    """

    def test_the_set_is_the_three(self):
        self.assertEqual(
            WRITTEN_BY_OTHERS,
            {"pending_approval", "clarification", "building"},
        )

    def test_no_command_moves_to_a_state_owned_by_another(self):
        forbidden = {LABELS[state] for state in WRITTEN_BY_OTHERS}
        self.assertEqual(set(MOVES.values()) & forbidden, set())

    def test_moving_out_of_pending_approval_is_allowed(self):
        self.assertIn("ready-for-work", plan(["pending-approval"], "approve"))

    def test_moving_out_of_in_progress_is_allowed(self):
        self.assertIn("ready-for-work", plan(["in-progress"], "redo"))

    def test_moving_out_of_needs_clarification_is_allowed(self):
        self.assertIn("ai-triage", plan(["needs-clarification"], "revise"))


class TestTheLabelNamesAreConfigured(unittest.TestCase):
    def test_a_renamed_state_is_honoured(self):  # GK-002
        renamed = dict(LABELS, approved="queued")
        result = plan_labels(["ai-triage"], [Action("approve")], labels=renamed)
        self.assertIn("queued", result)

    def test_the_default_name_is_not_used_when_renamed(self):  # GK-002
        renamed = dict(LABELS, approved="queued")
        result = plan_labels(["ai-triage"], [Action("approve")], labels=renamed)
        self.assertNotIn("ready-for-work", result)


if __name__ == "__main__":
    unittest.main()
