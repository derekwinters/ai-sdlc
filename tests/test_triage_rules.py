"""TRI-001 to TRI-043 — stated, not run.

Triage is the clearest case for the conversion in #153: the judgement was
always the agent's, and the Python around it existed only to hold the agent's
answer and write two labels. `Outcome.plan(...)` refusing a plan with no
acceptance checks was a real check — but only ever against a value the agent
had already decided, and only in a process no consumer runs.
"""

import unittest

from _triage import stated


class TestSelecting(unittest.TestCase):
    def test_queued_and_running_are_both_eligible(self):  # TRI-001
        """A session that died mid-run left the running label behind, and the
        issue would otherwise never be picked up again."""
        self.assertIn("queued for triage or already running", stated())

    def test_a_closed_issue_is_not(self):  # TRI-002
        self.assertIn("closed", stated())

    def test_a_parked_issue_is_not(self):  # TRI-003
        self.assertIn("parked", stated())

    def test_one_already_at_pending_approval_is_not(self):  # TRI-004
        self.assertIn("already at pending approval", stated())

    def test_an_epic_is_not(self):  # TRI-005
        self.assertIn("its children are the work", stated())

    def test_the_order_is_reproducible(self):  # TRI-006
        self.assertIn("issue number**, so a run is reproducible", stated())

    def test_the_cap_is_reported_when_it_truncates(self):  # TRI-007
        self.assertIn("silent cap makes a partial run look like a complete one", stated())

    def test_eligibility_never_reads_a_body(self):  # TRI-008
        text = stated()
        self.assertIn("never read issue bodies to decide it", text)
        self.assertIn("talk its way into or out of the queue", text)

    def test_a_stalled_issue_is_not_eligible(self):  # TRI-009
        self.assertIn("only a person restarts it", stated())


class TestRouting(unittest.TestCase):
    def test_a_plan_goes_to_pending_approval(self):  # TRI-010
        self.assertIn("pending-approval", stated())

    def test_a_question_goes_to_clarification(self):  # TRI-011
        self.assertIn("needs-clarification", stated())

    def test_an_unactionable_issue_stays_in_triage(self):  # TRI-012
        self.assertIn("failed triage leaves the issue in triage", stated())

    def test_exactly_one_state_label_is_written(self):  # TRI-013
        text = stated()
        self.assertIn("writes exactly one state label", text)
        self.assertIn("leaves an issue in two states", text)

    def test_triage_never_queues_work(self):  # TRI-014
        text = stated()
        self.assertIn("never writes the approved or building states", text)
        self.assertIn("triage proposes; the owner approves", text)

    def test_the_decision_is_reported(self):  # TRI-015
        self.assertIn("report the routing decision", stated())


class TestWhatAPlanContains(unittest.TestCase):
    def test_it_opens_in_plain_english(self):  # TRI-020
        self.assertIn("before any file or class name", stated())

    def test_it_proposes_a_milestone(self):  # TRI-021
        self.assertIn("proposed milestone", stated())

    def test_it_lists_acceptance_checks(self):  # TRI-022
        self.assertIn("acceptance checks", stated())

    def test_it_names_the_pages_it_affects(self):  # TRI-023
        self.assertIn("or an explicit statement that none change", stated())

    def test_it_says_how_the_specification_changes(self):  # TRI-024
        self.assertIn("what it used to say, what it now says", stated())

    def test_a_plan_without_checks_is_refused(self):  # TRI-025
        self.assertIn("plan nobody can verify is a wish", stated())


class TestAskingInsteadOfGuessing(unittest.TestCase):
    def test_a_question_states_the_options(self):  # TRI-030
        self.assertIn("what is undecided and what the options are", stated())

    def test_it_never_picks_one(self):  # TRI-031
        text = stated()
        self.assertIn("must not recommend one", text)
        self.assertIn("decision wearing a question mark", text)

    def test_one_option_is_refused(self):  # TRI-031
        self.assertIn("one option is not a question", stated())

    def test_it_names_who_must_answer(self):  # TRI-032
        self.assertIn("name who must answer", stated())

    def test_an_answerable_question_is_unread_specification(self):  # TRI-033
        self.assertIn("it is unread specification", stated())


class TestHandBack(unittest.TestCase):
    def test_every_routed_issue_gets_a_comment(self):  # TRI-040
        self.assertIn("every routed issue gets a comment", stated())

    def test_the_comment_says_what_happens_next(self):  # TRI-041
        self.assertIn("saying what happens next", stated())

    def test_it_is_posted_once_per_routing(self):  # TRI-042
        self.assertIn("one comment per routing, not one per run", stated())

    def test_a_failure_reports_rather_than_relocating(self):  # TRI-043
        self.assertIn("does not route it somewhere convenient", stated())


if __name__ == "__main__":
    unittest.main()
