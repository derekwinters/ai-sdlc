"""DASH-001, DASH-005 and DASH-030 to DASH-032 — gathering the state."""

import unittest

import _dashboard  # noqa: F401
from fetch_state import fetch
from lib.config import STATES
from lib.fake_github import FakeFailure, FakeGitHub

LABELS = dict(STATES)
BOT = "sdlc-bot[bot]"


def issue(number, labels=(), state="open", milestone="v0.2", body=""):
    return {
        "number": number,
        "title": f"Issue {number}",
        "state": state,
        "body": body,
        "labels": [{"name": name} for name in labels],
        "milestone": {"title": milestone} if milestone else None,
    }


def api(issues=None, milestones=None, **kwargs):
    return FakeGitHub(
        issues=issues if issues is not None else [issue(7, ["ready-for-work"])],
        milestones=milestones if milestones is not None else
        [{"number": 2, "title": "v0.2", "state": "open", "description": "focus. state",
          "open_issues": 1, "closed_issues": 0}],
        actor=BOT,
        **kwargs,
    )


def state(github=None, **kwargs):
    kwargs.setdefault("labels", LABELS)
    kwargs.setdefault("bot_login", BOT)
    kwargs.setdefault("dashboard_issue", 193)
    return fetch(github or api(), **kwargs)


class TestItReturnsPlainData(unittest.TestCase):
    def test_the_result_is_a_dictionary(self):  # DASH-001
        self.assertIsInstance(state(), dict)

    def test_it_carries_the_issues(self):  # DASH-001
        self.assertEqual([i["number"] for i in state()["issues"]], [7])

    def test_each_issue_carries_its_state_label(self):  # DASH-001
        self.assertEqual(state()["issues"][0]["state_label"], "ready-for-work")

    def test_it_carries_the_focus_milestone(self):  # DASH-001
        self.assertEqual(state()["focus"]["title"], "v0.2")

    def test_the_dashboard_issue_is_not_listed_as_work(self):  # DASH-032
        github = api([issue(7, ["ready-for-work"]), issue(193, [])])
        self.assertEqual([i["number"] for i in state(github)["issues"]], [7])


class TestDegradation(unittest.TestCase):
    def test_a_failing_milestone_read_still_renders(self):  # DASH-005
        github = api(fail={"milestones": FakeFailure("down")})
        self.assertIsNone(state(github)["focus"])

    def test_a_failing_milestone_read_keeps_the_issues(self):  # DASH-005
        github = api(fail={"milestones": FakeFailure("down")})
        self.assertEqual(len(state(github)["issues"]), 1)

    def test_a_failing_blocker_read_does_not_lose_the_page(self):  # DASH-005
        github = api(fail={"blocked_by": FakeFailure("down")})
        self.assertEqual(len(state(github)["issues"]), 1)


class TestOverrides(unittest.TestCase):
    def test_a_focus_override_wins(self):  # DASH-030, DASH-031
        result = state(overrides={"focus": "v0.9"})
        self.assertEqual(result["focus"]["title"], "v0.9")

    def test_without_an_override_the_marker_decides(self):  # DASH-031
        self.assertEqual(state()["focus"]["title"], "v0.2")

    def test_a_cap_override_is_carried(self):  # DASH-030
        self.assertEqual(state(overrides={"cap": 3})["cap"], 3)

    def test_no_cap_override_leaves_it_unset(self):  # DASH-030
        self.assertIsNone(state()["cap"])


class TestItNeverWrites(unittest.TestCase):
    def test_fetching_makes_no_write_request(self):  # DASH-032
        github = api()
        state(github)
        writes = [name for name, _ in github.calls
                  if name in ("set_labels", "comment", "set_milestone", "react")]
        self.assertEqual(writes, [])


class TestFaultDetection(unittest.TestCase):
    def test_an_untracked_open_issue_is_flagged(self):  # DASH-024
        github = api([issue(7, [])])
        self.assertEqual([f["issue"] for f in state(github)["faults"]["untracked"]], [7])

    def test_a_closed_issue_with_state_is_flagged(self):  # DASH-025
        github = api([issue(7, ["in-progress"], state="closed")])
        self.assertEqual([f["issue"] for f in state(github)["faults"]["stale_state"]], [7])

    def test_a_prose_dependency_is_flagged(self):  # DASH-026
        github = api([issue(7, ["ready-for-work"], body="Blocked by #42")])
        found = state(github)["faults"]["prose_dependency"]
        self.assertEqual(found[0]["numbers"], [42])

    def test_a_healthy_issue_raises_no_fault(self):  # DASH-027
        self.assertEqual(sum(len(v) for v in state()["faults"].values()), 0)


if __name__ == "__main__":
    unittest.main()
