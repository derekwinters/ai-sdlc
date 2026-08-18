"""TRI-001 to TRI-008 — which issues a triage run picks up."""

import unittest

import _triage  # noqa: F401
from lib.config import STATES
from select_triage import select

LABELS = dict(STATES)


def issue(number, labels=("ai-triage-queued",), state="open"):
    return {"number": number, "state": state,
            "labels": [{"name": name} for name in labels]}


def chosen(issues, **kwargs):
    return [i["number"] for i in select(issues, labels=LABELS, **kwargs).issues]


class TestEligibility(unittest.TestCase):
    def test_a_triage_labelled_issue_is_selected(self):  # TRI-001
        self.assertEqual(chosen([issue(7)]), [7])

    def test_an_issue_without_the_label_is_not(self):  # TRI-001
        self.assertEqual(chosen([issue(7, labels=())]), [])

    def test_a_closed_issue_is_not(self):  # TRI-002
        self.assertEqual(chosen([issue(7, state="closed")]), [])

    def test_a_parked_issue_is_not(self):  # TRI-003
        self.assertEqual(chosen([issue(7, labels=("ai-triage-queued", "parked"))]), [])

    def test_an_issue_at_pending_approval_is_not(self):  # TRI-004
        self.assertEqual(chosen([issue(7, labels=("pending-approval",))]), [])

    def test_an_issue_with_both_labels_is_not(self):  # TRI-004
        self.assertEqual(chosen([issue(7, labels=("ai-triage-queued", "pending-approval"))]), [])

    def test_an_epic_is_not(self):  # TRI-005
        self.assertEqual(chosen([issue(7, labels=("ai-triage-queued", "type:epic"))]), [])

    def test_a_needs_clarification_issue_is_not(self):  # TRI-004
        self.assertEqual(chosen([issue(7, labels=("needs-clarification",))]), [])


class TestAStalledIssueIsNotEligible(unittest.TestCase):
    """TRI-009 — the sweep gave up on it deliberately.

    Only `/admit` puts it back in the queue, because another session is a
    person's decision. Selecting it here would be the automatic retry the whole
    design removed, arriving through the back door.
    """

    def test_a_stalled_issue_is_not_selected(self):  # TRI-009
        self.assertEqual(chosen([issue(7, ["ai-triage-stalled"])]), [])

    def test_a_queued_issue_still_is(self):  # TRI-001
        self.assertEqual(chosen([issue(7, ["ai-triage-queued"])]), [7])

    def test_a_running_issue_still_is(self):  # TRI-001
        """Firing and recording are two operations, so a session can reach this
        check before its own `running` label lands. Refusing it would make the
        routine reject the very issue it was woken for."""
        self.assertEqual(chosen([issue(7, ["ai-triage-running"])]), [7])


class TestOrdering(unittest.TestCase):
    def test_selection_is_by_issue_number(self):  # TRI-006
        self.assertEqual(chosen([issue(9), issue(7), issue(8)]), [7, 8, 9])

    def test_the_same_input_selects_the_same_issues(self):  # TRI-006
        issues = [issue(9), issue(7)]
        self.assertEqual(chosen(issues), chosen(issues))


class TestTheCap(unittest.TestCase):
    def test_selection_is_capped(self):  # TRI-007
        self.assertEqual(chosen([issue(n) for n in range(1, 10)], cap=3), [1, 2, 3])

    def test_truncation_is_reported(self):  # TRI-007
        result = select([issue(n) for n in range(1, 10)], labels=LABELS, cap=3)
        self.assertTrue(result.truncated)

    def test_the_report_says_how_many_were_left(self):  # TRI-007
        result = select([issue(n) for n in range(1, 10)], labels=LABELS, cap=3)
        self.assertEqual(result.remaining, 6)

    def test_no_truncation_is_reported_when_under_the_cap(self):  # TRI-007
        result = select([issue(7)], labels=LABELS, cap=3)
        self.assertFalse(result.truncated)


class TestItReadsLabelsOnly(unittest.TestCase):
    def test_a_body_is_never_consulted(self):  # TRI-008
        """Eligibility must not depend on prose, or it becomes unpredictable."""
        with_body = issue(7)
        with_body["body"] = "please do not triage me"
        self.assertEqual(chosen([with_body]), [7])

    def test_selection_is_pure(self):  # TRI-008
        import ast

        from _support import ROOT

        source = (ROOT / "skills" / "pipeline" / "triage-issue" / "select_triage.py").read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("lib.github", imported)


if __name__ == "__main__":
    unittest.main()
