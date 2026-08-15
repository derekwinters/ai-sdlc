"""TRI-020 to TRI-033 — what a plan must contain, and when to ask instead."""

import unittest

import _triage  # noqa: F401
from triage_route import Outcome, PlanError


def plan(**kwargs):
    kwargs.setdefault("summary", "The widget does not spin when the lever is pulled.")
    kwargs.setdefault("milestone", "v0.2")
    kwargs.setdefault("checks", ["pulling the lever spins the widget"])
    return Outcome.plan(**kwargs)


def refused(**kwargs):
    try:
        plan(**kwargs)
    except PlanError as error:
        return str(error)
    raise AssertionError("expected a PlanError")


class TestWhatAPlanContains(unittest.TestCase):
    def test_it_has_a_summary(self):  # TRI-020
        self.assertIn("widget", plan().summary)

    def test_the_summary_comes_first_in_the_rendered_comment(self):  # TRI-020
        body = plan().render(7)
        self.assertLess(body.index("widget"), body.index("Acceptance"))

    def test_it_proposes_a_milestone(self):  # TRI-021
        self.assertEqual(plan().milestone, "v0.2")

    def test_the_milestone_appears_in_the_comment(self):  # TRI-021
        self.assertIn("v0.2", plan().render(7))

    def test_it_lists_acceptance_checks(self):  # TRI-022
        self.assertEqual(len(plan().checks), 1)

    def test_the_checks_appear_in_the_comment(self):  # TRI-022
        self.assertIn("spins the widget", plan().render(7))

    def test_it_names_affected_specification_pages(self):  # TRI-023
        made = plan(specs=["docs/spec/widgets.md"])
        self.assertIn("docs/spec/widgets.md", made.render(7))

    def test_no_specification_change_is_stated_explicitly(self):  # TRI-023
        self.assertIn("none", plan(specs=[]).render(7).lower())

    def test_a_specification_change_says_how_it_changes(self):  # TRI-024
        made = plan(specs=["docs/spec/widgets.md"],
                    spec_change="the lever was undefined; it now spins the widget")
        self.assertIn("undefined", made.render(7))


class TestAPlanMustBeVerifiable(unittest.TestCase):
    def test_no_checks_is_refused(self):  # TRI-025
        self.assertIn("acceptance", refused(checks=[]).lower())

    def test_empty_checks_are_refused(self):  # TRI-025
        self.assertIn("acceptance", refused(checks=["", "  "]).lower())

    def test_no_summary_is_refused(self):  # TRI-020
        self.assertIn("summary", refused(summary="").lower())

    def test_no_milestone_is_refused(self):  # TRI-021
        self.assertIn("milestone", refused(milestone=None).lower())


class TestAskingInsteadOfGuessing(unittest.TestCase):
    def test_a_question_states_what_is_undecided(self):  # TRI-030
        made = Outcome.question("Should the lever latch?", options=["latch", "spring back"])
        self.assertIn("latch", made.render(7))

    def test_it_lists_the_options(self):  # TRI-030
        made = Outcome.question("Should the lever latch?", options=["latch", "spring back"])
        body = made.render(7)
        self.assertIn("spring back", body)

    def test_a_question_with_no_options_is_refused(self):  # TRI-030
        with self.assertRaises(PlanError):
            Outcome.question("Should the lever latch?", options=[])

    def test_it_never_recommends_one(self):  # TRI-031
        made = Outcome.question("Should the lever latch?", options=["latch", "spring back"])
        body = made.render(7).lower()
        for word in ("recommend", "suggest", "probably", "i would"):
            self.assertNotIn(word, body)

    def test_the_comment_asks_the_owner_to_decide(self):  # TRI-032
        made = Outcome.question("Should the lever latch?", options=["a", "b"])
        self.assertIn("decide", made.render(7).lower())

    def test_a_question_carries_no_milestone(self):  # TRI-031
        made = Outcome.question("q", options=["a", "b"])
        self.assertIsNone(getattr(made, "milestone", None))


class TestFailure(unittest.TestCase):
    def test_a_failure_states_the_reason(self):  # TRI-043
        self.assertIn("no specification", Outcome.failed("no specification covers this").render(7))

    def test_a_failure_is_not_a_plan(self):  # TRI-012
        self.assertNotEqual(Outcome.failed("x").kind, "plan")


if __name__ == "__main__":
    unittest.main()
