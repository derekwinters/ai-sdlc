"""GK-100 to GK-106 — what happens when an issue closes or a pull request merges.

Almost nothing, deliberately. Closing an issue strips its pipeline labels and
touches nothing else; a merge without a closing keyword is respected as a
decision rather than corrected. The old reconcile sweep existed to repair
states nobody had asked it to repair.
"""

import unittest

import _gatekeeper  # noqa: F401
from lib.config import STATES
from lib.fake_github import FakeGitHub
from lifecycle import on_issue_closed, on_pull_request_closed

LABELS = dict(STATES)


def issue(number=7, labels=()):
    return {"number": number, "labels": [{"name": name} for name in labels]}


def api(*issues):
    return FakeGitHub(issues=list(issues), actor="sdlc-bot[bot]")


def labels_of(github, number):
    return [label["name"] for label in github.issue(number)["labels"]]


class TestClosingAnIssue(unittest.TestCase):
    def test_a_state_label_is_stripped(self):  # GK-100
        github = api(issue(labels=["in-progress"]))
        on_issue_closed(github, 7, labels=LABELS)
        self.assertEqual(labels_of(github, 7), [])

    def test_every_state_label_is_stripped(self):  # GK-100
        for state in LABELS.values():
            github = api(issue(labels=[state]))
            on_issue_closed(github, 7, labels=LABELS)
            self.assertEqual(labels_of(github, 7), [], state)

    def test_classification_labels_are_kept(self):  # GK-003
        github = api(issue(labels=["in-progress", "area:build", "type:bug"]))
        on_issue_closed(github, 7, labels=LABELS)
        self.assertEqual(sorted(labels_of(github, 7)), ["area:build", "type:bug"])

    def test_an_issue_with_no_state_label_is_left_alone(self):  # GK-100
        github = api(issue(labels=["area:build"]))
        on_issue_closed(github, 7, labels=LABELS)
        self.assertNotIn("set_labels", [name for name, _ in github.calls])

    def test_an_issue_with_no_labels_at_all_is_left_alone(self):  # GK-100
        github = api(issue())
        on_issue_closed(github, 7, labels=LABELS)
        self.assertNotIn("set_labels", [name for name, _ in github.calls])

    def test_it_returns_what_it_removed(self):  # GK-100
        github = api(issue(labels=["in-progress"]))
        self.assertEqual(on_issue_closed(github, 7, labels=LABELS), ["in-progress"])


class TestItTouchesNoOtherIssue(unittest.TestCase):
    """GK-101 — closing #42 must not wake #50.

    Blockedness is derived at selection time, so an issue blocked by this one
    becomes eligible on its own. There is nothing to wake, and waking is what
    the deleted revisit machinery existed to do.
    """

    def test_no_other_issue_is_read(self):
        github = api(issue(7, ["in-progress"]), issue(8, ["ready-for-work"]))
        on_issue_closed(github, 7, labels=LABELS)
        touched = {args[0] for name, args in github.calls if name in ("issue", "set_labels")}
        self.assertEqual(touched, {7})

    def test_no_other_issue_is_written(self):
        github = api(issue(7, ["in-progress"]), issue(8, ["ready-for-work"]))
        on_issue_closed(github, 7, labels=LABELS)
        self.assertEqual(labels_of(github, 8), ["ready-for-work"])

    def test_dependencies_are_not_even_looked_up(self):
        github = api(issue(7, ["in-progress"]))
        on_issue_closed(github, 7, labels=LABELS)
        self.assertNotIn("blocked_by", [name for name, _ in github.calls])


class TestMergedPullRequests(unittest.TestCase):
    def test_a_merge_without_a_closing_keyword_changes_nothing(self):  # GK-103
        github = api(issue(7, ["in-progress"]))
        on_pull_request_closed(github, {"merged": True, "body": "Refs #7"}, labels=LABELS)
        self.assertEqual(labels_of(github, 7), ["in-progress"])

    def test_a_merge_without_a_keyword_writes_nothing_at_all(self):  # GK-103
        github = api(issue(7, ["in-progress"]))
        on_pull_request_closed(github, {"merged": True, "body": "Refs #7"}, labels=LABELS)
        self.assertEqual(github.calls, [])

    def test_a_merge_with_a_keyword_takes_no_separate_action(self):  # GK-102
        """GitHub closes the issue, which raises issues.closed; GK-100 applies."""
        github = api(issue(7, ["in-progress"]))
        on_pull_request_closed(github, {"merged": True, "body": "Closes #7"}, labels=LABELS)
        self.assertEqual(github.calls, [])

    def test_an_unmerged_close_changes_nothing(self):  # GK-105
        github = api(issue(7, ["in-progress"]))
        on_pull_request_closed(github, {"merged": False, "body": "Closes #7"}, labels=LABELS)
        self.assertEqual(github.calls, [])

    def test_a_missing_body_does_not_throw(self):  # GK-103
        github = api(issue(7, ["in-progress"]))
        on_pull_request_closed(github, {"merged": True}, labels=LABELS)
        self.assertEqual(github.calls, [])


class TestStalledWorkIsReportedNotRepaired(unittest.TestCase):
    """GK-104 — an issue left in-progress is a dashboard flag, never a write.

    Merging without a keyword is sometimes deliberate: the work landed, the
    issue is not finished. Advancing it automatically would overrule that.
    """

    def test_nothing_here_advances_a_stalled_issue(self):
        github = api(issue(7, ["in-progress"]))
        on_pull_request_closed(github, {"merged": True, "body": ""}, labels=LABELS)
        on_issue_closed  # the only writer, and only on a real close
        self.assertEqual(labels_of(github, 7), ["in-progress"])


class TestNoScheduledWrites(unittest.TestCase):
    def test_the_module_exposes_no_sweep(self):  # GK-106
        import lifecycle

        exported = [name for name in dir(lifecycle) if not name.startswith("_")]
        for forbidden in ("sweep", "reconcile", "revisit", "cron"):
            self.assertFalse(
                any(forbidden in name.lower() for name in exported), forbidden
            )

    def test_only_event_handlers_are_exported(self):  # GK-106
        import lifecycle

        handlers = [n for n in dir(lifecycle) if n.startswith("on_")]
        self.assertEqual(sorted(handlers), ["on_issue_closed", "on_pull_request_closed"])


if __name__ == "__main__":
    unittest.main()
