"""DASH-020 to DASH-028 — the faults the pipeline deliberately does not repair.

Every entry here is the other half of a decision made elsewhere: the reconcile
sweep was removed because auto-repair hid problems, on the promise that they
would be reported instead. This is that promise.
"""

import unittest

from _dashboard import issue, state
import _dashboard  # noqa: F401
from render_dashboard import FAULTS, render


def with_fault(kind, *entries):
    return state(faults={kind: list(entries)})


class TestEveryFaultIsRendered(unittest.TestCase):
    def test_a_stalled_command_appears(self):  # DASH-020
        page = render(with_fault("stalled_command", {"issue": 7, "comment": 55}))
        self.assertIn("#7", page)

    def test_it_explains_what_to_do(self):  # DASH-020
        page = render(with_fault("stalled_command", {"issue": 7, "comment": 55}))
        self.assertIn("/retry", page)

    def test_stalled_work_appears(self):  # DASH-021
        page = render(with_fault("stalled_work", {"issue": 7}))
        self.assertIn("#7", page)

    def test_stalled_work_explains_the_likely_cause(self):  # DASH-021
        page = render(with_fault("stalled_work", {"issue": 7}))
        self.assertIn("no open pull request", page.lower())

    def test_blocked_but_approved_appears(self):  # DASH-022
        page = render(with_fault("blocked_but_approved", {"issue": 7, "blockers": [42]}))
        self.assertIn("#42", page)

    def test_an_unverifiable_dependency_appears(self):  # DASH-023
        page = render(with_fault("unverifiable_dependency",
                                 {"issue": 7, "blocker": 42, "milestone": "Direct Involvement"}))
        self.assertIn("#42", page)

    def test_it_names_the_milestone_that_could_not_be_ordered(self):  # DASH-023
        page = render(with_fault("unverifiable_dependency",
                                 {"issue": 7, "blocker": 42, "milestone": "Direct Involvement"}))
        self.assertIn("Direct Involvement", page)

    def test_an_untracked_issue_appears(self):  # DASH-024
        self.assertIn("#7", render(with_fault("untracked", {"issue": 7})))

    def test_stale_state_appears(self):  # DASH-025
        page = render(with_fault("stale_state", {"issue": 7, "labels": ["in-progress"]}))
        self.assertIn("in-progress", page)

    def test_a_prose_dependency_appears(self):  # DASH-026
        page = render(with_fault("prose_dependency", {"issue": 7, "numbers": [42]}))
        self.assertIn("#42", page)

    def test_it_says_the_queue_cannot_see_it(self):  # DASH-026
        page = render(with_fault("prose_dependency", {"issue": 7, "numbers": [42]}))
        self.assertIn("queue", page.lower())

    def test_every_declared_fault_kind_has_a_renderer(self):  # DASH-027
        for kind in FAULTS:
            page = render(state(faults={kind: [{"issue": 7, "comment": 1, "blockers": [1],
                                                "blocker": 1, "numbers": [1], "labels": ["x"],
                                                "milestone": "m"}]}))
            self.assertIn("#7", page, kind)


class TestQuietWhenWell(unittest.TestCase):
    def test_an_empty_fault_section_is_omitted(self):  # DASH-027
        page = render(state(faults={"stalled_work": []}))
        self.assertNotIn("no open pull request", page.lower())

    def test_no_faults_at_all_says_so(self):  # DASH-027
        self.assertIn("nothing needs attention", render(state()).lower())

    def test_a_clean_page_is_short(self):  # DASH-027
        self.assertLess(len(render(state()).splitlines()), 30)


class TestTheCount(unittest.TestCase):
    def test_the_total_appears(self):  # DASH-028
        page = render(state(faults={"untracked": [{"issue": 7}, {"issue": 8}]}))
        self.assertIn("2", page)

    def test_faults_across_kinds_are_summed(self):  # DASH-028
        page = render(state(faults={"untracked": [{"issue": 7}],
                                    "stalled_work": [{"issue": 8}]}))
        self.assertIn("2", page)

    def test_the_count_is_near_the_top(self):  # DASH-028
        page = render(state(faults={"untracked": [{"issue": 7}]}))
        head = "\n".join(page.splitlines()[:8])
        self.assertIn("1", head)


if __name__ == "__main__":
    unittest.main()
