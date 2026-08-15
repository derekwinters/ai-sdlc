"""DEV-030 to DEV-033 — a builder claiming an issue."""

import unittest

import _dev  # noqa: F401
from lib.config import STATES
from lib.fake_github import FakeGitHub
from take_issue import TakeRefused, branch_name, take

LABELS = dict(STATES)


def api(labels=("ready-for-work",), state="open"):
    return FakeGitHub(
        issues=[{"number": 7, "state": state,
                 "labels": [{"name": n} for n in labels]}],
        actor="sdlc-bot[bot]",
    )


def labels_of(github):
    return [label["name"] for label in github.issue(7)["labels"]]


class TestTaking(unittest.TestCase):
    def test_it_moves_to_building(self):  # DEV-030
        github = api()
        take(github, 7, labels=LABELS)
        self.assertIn("in-progress", labels_of(github))

    def test_the_approved_state_is_replaced(self):  # DEV-030
        github = api()
        take(github, 7, labels=LABELS)
        self.assertNotIn("ready-for-work", labels_of(github))

    def test_classification_labels_survive(self):  # DEV-030
        github = api(labels=("ready-for-work", "area:build"))
        take(github, 7, labels=LABELS)
        self.assertIn("area:build", labels_of(github))

    def test_it_returns_the_branch(self):  # DEV-033
        github = api()
        self.assertIn("7", take(github, 7, labels=LABELS).branch)


class TestRefusal(unittest.TestCase):
    """DEV-031 — the world may have changed since the queue was built."""

    def test_an_issue_no_longer_approved_is_refused(self):
        github = api(labels=("parked",))
        with self.assertRaises(TakeRefused):
            take(github, 7, labels=LABELS)

    def test_an_issue_already_building_is_refused(self):
        github = api(labels=("in-progress",))
        with self.assertRaises(TakeRefused):
            take(github, 7, labels=LABELS)

    def test_a_closed_issue_is_refused(self):
        github = api(state="closed")
        with self.assertRaises(TakeRefused):
            take(github, 7, labels=LABELS)

    def test_a_refusal_writes_nothing(self):
        github = api(labels=("parked",))
        try:
            take(github, 7, labels=LABELS)
        except TakeRefused:
            pass
        self.assertNotIn("set_labels", [name for name, _ in github.calls])

    def test_the_refusal_says_what_state_it_found(self):
        github = api(labels=("parked",))
        try:
            take(github, 7, labels=LABELS)
        except TakeRefused as error:
            self.assertIn("parked", str(error))


class TestTheBranchName(unittest.TestCase):
    def test_it_contains_the_issue_number(self):  # DEV-033
        self.assertIn("7", branch_name(7))

    def test_it_is_recoverable_from_the_branch_alone(self):  # DEV-033
        import re

        self.assertEqual(int(re.search(r"(\d+)", branch_name(7)).group(1)), 7)

    def test_it_is_stable(self):  # DEV-033
        self.assertEqual(branch_name(7), branch_name(7))

    def test_two_issues_get_different_branches(self):  # DEV-032
        self.assertNotEqual(branch_name(7), branch_name(8))

    def test_it_is_a_legal_git_ref(self):  # DEV-033
        import re

        self.assertRegex(branch_name(7), r"^[A-Za-z0-9._/-]+$")


if __name__ == "__main__":
    unittest.main()
