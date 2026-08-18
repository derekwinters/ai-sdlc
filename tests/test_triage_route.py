"""TRI-010 to TRI-015 and TRI-040 to TRI-043 — where a triaged issue ends up."""

import unittest

import _triage  # noqa: F401
from lib.config import STATES
from lib.fake_github import FakeGitHub
from triage_route import Outcome, route

LABELS = dict(STATES)


def api(labels=("ai-triage-queued",)):
    return FakeGitHub(
        issues=[{"number": 7, "labels": [{"name": n} for n in labels]}],
        actor="sdlc-bot[bot]",
    )


def labels_of(github):
    return [label["name"] for label in github.issue(7)["labels"]]


def comments_of(github):
    return [c["body"] for c in github.comments(7)]


class TestRouting(unittest.TestCase):
    def test_a_plan_goes_to_pending_approval(self):  # TRI-010
        github = api()
        route(github, 7, Outcome.plan("A summary", milestone="v0.2", checks=["it works"]),
              labels=LABELS)
        self.assertIn("pending-approval", labels_of(github))

    def test_a_question_goes_to_clarification(self):  # TRI-011
        github = api()
        route(github, 7, Outcome.question("What should it do?", options=["a", "b"]),
              labels=LABELS)
        self.assertIn("needs-clarification", labels_of(github))

    def test_an_unactionable_issue_stays_in_triage(self):  # TRI-012
        github = api()
        route(github, 7, Outcome.failed("could not read the specification"), labels=LABELS)
        self.assertIn("ai-triage-queued", labels_of(github))

    def test_exactly_one_state_label_results(self):  # TRI-013
        github = api()
        route(github, 7, Outcome.plan("s", milestone="v0.2", checks=["c"]), labels=LABELS)
        states = set(LABELS.values()) & set(labels_of(github))
        self.assertEqual(len(states), 1)

    def test_the_previous_state_is_replaced(self):  # TRI-013
        github = api()
        route(github, 7, Outcome.plan("s", milestone="v0.2", checks=["c"]), labels=LABELS)
        self.assertNotIn("ai-triage-queued", labels_of(github))

    def test_classification_labels_survive(self):  # TRI-013
        github = api(labels=("ai-triage-queued", "type:bug"))
        route(github, 7, Outcome.plan("s", milestone="v0.2", checks=["c"]), labels=LABELS)
        self.assertIn("type:bug", labels_of(github))


class TestItNeverQueuesWork(unittest.TestCase):
    """TRI-014 — the one thing triage must not do."""

    def test_no_outcome_writes_the_approved_state(self):
        for outcome in (
            Outcome.plan("s", milestone="v0.2", checks=["c"]),
            Outcome.question("q", options=["a", "b"]),
            Outcome.failed("x"),
        ):
            github = api()
            route(github, 7, outcome, labels=LABELS)
            self.assertNotIn("ready-for-work", labels_of(github))

    def test_no_outcome_writes_the_building_state(self):
        github = api()
        route(github, 7, Outcome.plan("s", milestone="v0.2", checks=["c"]), labels=LABELS)
        self.assertNotIn("in-progress", labels_of(github))


class TestHandBack(unittest.TestCase):
    def test_every_routing_leaves_a_comment(self):  # TRI-040
        github = api()
        route(github, 7, Outcome.plan("A summary", milestone="v0.2", checks=["c"]),
              labels=LABELS)
        self.assertEqual(len(comments_of(github)), 1)

    def test_the_comment_says_what_happens_next(self):  # TRI-041
        github = api()
        route(github, 7, Outcome.plan("A summary", milestone="v0.2", checks=["c"]),
              labels=LABELS)
        self.assertIn("/approve", comments_of(github)[0])

    def test_a_question_asks_for_an_answer(self):  # TRI-041
        github = api()
        route(github, 7, Outcome.question("What should it do?", options=["a", "b"]),
              labels=LABELS)
        self.assertIn("What should it do?", comments_of(github)[0])

    def test_one_comment_per_routing(self):  # TRI-042
        github = api()
        outcome = Outcome.plan("s", milestone="v0.2", checks=["c"])
        route(github, 7, outcome, labels=LABELS)
        self.assertEqual(len(comments_of(github)), 1)

    def test_a_failure_says_why(self):  # TRI-043
        github = api()
        route(github, 7, Outcome.failed("could not read the specification"), labels=LABELS)
        self.assertIn("specification", comments_of(github)[0])

    def test_a_failure_writes_no_label(self):  # TRI-043
        github = api()
        route(github, 7, Outcome.failed("x"), labels=LABELS)
        self.assertNotIn("set_labels", [name for name, _ in github.calls])


class TestTheReport(unittest.TestCase):
    def test_the_routing_is_returned(self):  # TRI-015
        github = api()
        result = route(github, 7, Outcome.plan("s", milestone="v0.2", checks=["c"]),
                       labels=LABELS)
        self.assertEqual(result.state, "pending_approval")

    def test_a_question_reports_its_state(self):  # TRI-015
        github = api()
        result = route(github, 7, Outcome.question("q", options=["a", "b"]), labels=LABELS)
        self.assertEqual(result.state, "clarification")


if __name__ == "__main__":
    unittest.main()
