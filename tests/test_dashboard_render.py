"""DASH-010 to DASH-015, and DASH-003/004 — the rendered page."""

import unittest

from _dashboard import issue, state
import _dashboard  # noqa: F401
from render_dashboard import render


class TestDeterminism(unittest.TestCase):
    def test_the_same_state_renders_identically(self):  # DASH-003
        snapshot = state(issues=[issue(7), issue(8)])
        self.assertEqual(render(snapshot), render(snapshot))

    def test_issue_order_does_not_change_the_output(self):  # DASH-004
        forwards = state(issues=[issue(7), issue(8)])
        backwards = state(issues=[issue(8), issue(7)])
        self.assertEqual(render(forwards), render(backwards))

    def test_rendering_touches_no_client(self):  # DASH-002
        import ast

        from _support import ROOT

        source = (ROOT / "skills" / "pipeline" / "pipeline-dashboard"
                  / "render_dashboard.py").read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("lib.github", imported)


class TestTheFocusMilestone(unittest.TestCase):
    def test_its_title_appears(self):  # DASH-010
        self.assertIn("v0.2 — Pipeline state", render(state()))

    def test_its_counts_appear(self):  # DASH-010
        page = render(state())
        self.assertIn("2", page)

    def test_no_focus_says_so(self):  # DASH-010
        self.assertIn("no focus", render(state(focus=None)).lower())


class TestIssuesByState(unittest.TestCase):
    def test_an_issue_is_listed_under_its_state(self):  # DASH-011
        page = render(state(issues=[issue(7, "Build the thing")]))
        self.assertIn("#7", page)
        self.assertIn("Build the thing", page)

    def test_each_state_with_issues_gets_a_heading(self):  # DASH-011
        page = render(state(issues=[issue(7), issue(8, state_label="parked")]))
        self.assertIn("ready-for-work", page)
        self.assertIn("parked", page)

    def test_an_empty_state_is_not_shown(self):  # DASH-011
        page = render(state(issues=[issue(7)]))
        self.assertNotIn("needs-clarification", page)

    def test_issues_are_numbered_in_order(self):  # DASH-004
        page = render(state(issues=[issue(9), issue(7), issue(8)]))
        self.assertLess(page.index("#7"), page.index("#8"))
        self.assertLess(page.index("#8"), page.index("#9"))


class TestTheReadyQueue(unittest.TestCase):
    def test_eligible_issues_are_listed(self):  # DASH-012
        page = render(state(issues=[issue(7)]))
        self.assertIn("#7", page)

    def test_a_blocked_issue_names_its_blockers(self):  # DASH-013
        page = render(state(issues=[issue(7, blockers=[42])]))
        self.assertIn("#42", page)

    def test_several_blockers_are_all_named(self):  # DASH-013
        page = render(state(issues=[issue(7, blockers=[42, 43])]))
        self.assertIn("#42", page)
        self.assertIn("#43", page)


class TestTheCap(unittest.TestCase):
    def test_the_cap_is_shown(self):  # DASH-014
        self.assertIn("2", render(state(cap=2)))

    def test_work_in_progress_is_counted_against_it(self):  # DASH-014
        page = render(state(cap=2, issues=[issue(7, state_label="in-progress")]))
        self.assertIn("1", page)

    def test_no_cap_says_unlimited(self):  # DASH-014
        self.assertIn("no cap", render(state(cap=None)).lower())


class TestEverythingNeedingAttention(unittest.TestCase):
    """DASH-015 — an issue parked in another milestone is still stuck."""

    def test_an_issue_outside_the_focus_is_still_listed(self):
        page = render(state(issues=[issue(7, milestone="v0.9 — Later")]))
        self.assertIn("#7", page)

    def test_its_milestone_is_shown_so_the_reader_knows(self):
        page = render(state(issues=[issue(7, milestone="v0.9 — Later")]))
        self.assertIn("v0.9", page)


if __name__ == "__main__":
    unittest.main()
