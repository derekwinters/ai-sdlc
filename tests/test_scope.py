"""GK-030 to GK-035 — where a command is valid.

Two kinds of scope. Some commands configure the pipeline and only mean
something on the dashboard issue; the rest act on the issue they are written
on. And an epic is a container whose children are the work, so the commands
that would queue it for building are refused.
"""

import unittest

import _gatekeeper  # noqa: F401
from parse_commands import parse
from scope import DASHBOARD_ONLY, EPIC_EXCLUDED, Subject, check_scope


def on_issue(text, number=7, labels=(), dashboard=193):
    """Parse, then scope — carrying parse-time skips through, as the runner does."""
    subject = Subject(number=number, labels=list(labels), dashboard_issue=dashboard)
    parsed = parse(text)
    return check_scope(parsed.actions, subject, skips=parsed.skips)


def applied(result):
    return [action.command for action in result.actions]


def refused(result):
    return [skip.command for skip in result.skips]


class TestDashboardOnlyCommands(unittest.TestCase):
    def test_focus_is_honoured_on_the_dashboard(self):  # GK-030
        self.assertEqual(applied(on_issue("/focus v0.4", number=193)), ["focus"])

    def test_cap_is_honoured_on_the_dashboard(self):  # GK-030
        self.assertEqual(applied(on_issue("/cap 2", number=193)), ["cap"])

    def test_focus_elsewhere_is_refused(self):  # GK-031
        self.assertEqual(refused(on_issue("/focus v0.4", number=7)), ["focus"])

    def test_cap_elsewhere_is_refused(self):  # GK-031
        self.assertEqual(refused(on_issue("/cap 2", number=7)), ["cap"])

    def test_the_refusal_says_where_it_belongs(self):  # GK-031
        skip = on_issue("/focus v0.4", number=7).skips[0]
        self.assertEqual(skip.reason, "dashboard-only")

    def test_the_set_is_exactly_focus_and_cap(self):  # GK-030
        self.assertEqual(set(DASHBOARD_ONLY), {"focus", "cap"})


class TestIssueCommandsOnTheDashboard(unittest.TestCase):
    def test_approve_on_the_dashboard_is_refused(self):  # GK-032
        self.assertEqual(refused(on_issue("/approve", number=193)), ["approve"])

    def test_the_refusal_says_why(self):  # GK-032
        skip = on_issue("/approve", number=193).skips[0]
        self.assertEqual(skip.reason, "not-on-dashboard")

    def test_park_on_the_dashboard_is_refused(self):  # GK-032
        self.assertEqual(refused(on_issue("/park", number=193)), ["park"])


class TestMixedOnTheDashboard(unittest.TestCase):
    def test_focus_applies_and_the_issue_command_is_refused(self):  # GK-033
        result = on_issue("/focus v0.4\n/approve", number=193)
        self.assertEqual(applied(result), ["focus"])
        self.assertEqual(refused(result), ["approve"])

    def test_order_does_not_change_the_outcome(self):  # GK-033
        result = on_issue("/approve\n/focus v0.4", number=193)
        self.assertEqual(applied(result), ["focus"])
        self.assertEqual(refused(result), ["approve"])


class TestEpics(unittest.TestCase):
    """GK-034, GK-035 — an epic is a container; its children are the work."""

    def epic(self, text):
        return on_issue(text, labels=["type:epic"])

    def test_admit_is_refused_on_an_epic(self):
        self.assertEqual(refused(self.epic("/admit")), ["admit"])

    def test_approve_is_refused_on_an_epic(self):
        self.assertEqual(refused(self.epic("/approve")), ["approve"])

    def test_revise_redo_and_propose_are_refused(self):
        for command in ("revise", "redo", "propose"):
            self.assertEqual(refused(self.epic(f"/{command} x")), [command], command)

    def test_the_refusal_says_it_is_an_epic(self):
        self.assertEqual(self.epic("/approve").skips[0].reason, "epic")

    def test_park_is_allowed_on_an_epic(self):
        self.assertEqual(applied(self.epic("/park")), ["park"])

    def test_unpark_is_allowed_on_an_epic(self):
        self.assertEqual(applied(self.epic("/unpark")), ["unpark"])

    def test_milestone_is_allowed_on_an_epic(self):
        self.assertEqual(applied(self.epic("/milestone v0.4")), ["milestone"])

    def test_the_excluded_set_is_the_building_commands(self):
        self.assertEqual(set(EPIC_EXCLUDED), {"admit", "approve", "revise", "redo", "propose"})

    def test_a_non_epic_is_unaffected(self):
        self.assertEqual(applied(on_issue("/approve")), ["approve"])


class TestScopesCompose(unittest.TestCase):
    def test_an_epic_dashboard_is_not_a_thing_but_does_not_crash(self):
        result = on_issue("/approve", number=193, labels=["type:epic"], dashboard=193)
        self.assertEqual(applied(result), [])

    def test_skips_from_parsing_are_carried_through(self):  # GK-027
        result = on_issue("/xyzzy")
        self.assertEqual(len(result.skips), 1)


if __name__ == "__main__":
    unittest.main()
