"""DASH-001, DASH-005 to DASH-008, and DASH-030 to DASH-034 — gathering state."""

import unittest

import _dashboard  # noqa: F401
from fetch_state import fetch
from lib.config import STATES
from lib.fake_github import FakeFailure, FakeGitHub

LABELS = dict(STATES)
BOT = "sdlc-bot[bot]"


def issue(number, labels=(), state="open", milestone="v0.2", body="",
          milestone_number=2, pull_request=False):
    found = {
        "number": number,
        "title": f"Issue {number}",
        "state": state,
        "body": body,
        "labels": [{"name": name} for name in labels],
        "milestone": {"title": milestone, "number": milestone_number} if milestone else None,
    }
    if pull_request:
        # How GitHub marks a pull request in the issues listing.
        found["pull_request"] = {"url": f"https://api.github.com/pulls/{number}"}
    return found


def dashboard(body=""):
    return {"number": 193, "title": "Dashboard", "state": "open", "body": body,
            "labels": [], "milestone": None}


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
        """Over the marker, and over the fallback.

        The override names a live milestone; one that names nothing is
        refused instead, which is DASH-034 and is asserted separately.
        """
        github = api(milestones=[
            {"number": 2, "title": "v0.2", "state": "open",
             "open_issues": 1, "closed_issues": 0},
            {"number": 9, "title": "v0.9", "state": "open",
             "open_issues": 1, "closed_issues": 0},
        ])
        result = state(github, overrides={"focus": "v0.9"})
        self.assertEqual(result["focus"]["title"], "v0.9")

    def test_without_an_override_the_fallback_decides(self):  # DASH-031
        """No marker in the body, so the lowest version with ready work."""
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
    def test_an_issue_with_no_state_raises_no_fault(self):  # DASH-027
        """It is the Waiting for triage section, not a problem.

        That section is the complement of the five claimed states, so it
        already lists every such issue; flagging them again read as 28
        problems when the real answer was none.
        """
        github = api([issue(7, [])])
        self.assertEqual(sum(len(v) for v in state(github)["faults"].values()), 0)

    def test_a_closed_issue_with_state_is_flagged(self):  # DASH-025
        github = api([issue(7, ["in-progress"], state="closed")])
        self.assertEqual([f["issue"] for f in state(github)["faults"]["stale_state"]], [7])

    def test_a_stalled_triage_is_flagged(self):  # DASH-029
        """Bounding the retries turns "retried for ever" into "ignored for
        ever" unless somebody is told. Without this the issue sits in Waiting
        for triage looking exactly like ordinary waiting work."""
        github = api([issue(7, ["ai-triage", "ai-triage-stalled"])])
        self.assertEqual(
            [f["issue"] for f in state(github)["faults"]["stalled_triage"]], [7])

    def test_an_ordinary_triage_raises_no_stalled_fault(self):  # DASH-029
        github = api([issue(7, ["ai-triage"])])
        self.assertEqual(state(github)["faults"]["stalled_triage"], [])

    def test_a_prose_dependency_is_flagged(self):  # DASH-026
        github = api([issue(7, ["ready-for-work"], body="Blocked by #42")])
        found = state(github)["faults"]["prose_dependency"]
        self.assertEqual(found[0]["numbers"], [42])

    def test_a_healthy_issue_raises_no_fault(self):  # DASH-027
        self.assertEqual(sum(len(v) for v in state()["faults"].values()), 0)


class TestWhatIsCounted(unittest.TestCase):
    """DASH-006 to DASH-008 — who belongs in the numbers."""

    def test_a_pull_request_is_not_an_issue(self):  # DASH-006
        """GitHub's issues endpoint returns both.

        Counting them together made every open pull request appear on the
        board as an untracked issue.
        """
        github = api([issue(7, ["ready-for-work"]), issue(8, [], pull_request=True)])
        self.assertEqual([i["number"] for i in state(github)["issues"]], [7])

    def test_a_pull_request_reaches_no_section(self):  # DASH-006
        github = api([issue(8, [], pull_request=True)])
        self.assertEqual(state(github)["issues"], [])

    def test_closed_issues_are_requested(self):  # DASH-007
        """Asserted on the request, not the fixture.

        A fake that returns closed issues to a caller that never asked for
        them is exactly how DASH-025 kept a green test while being dead in
        production.
        """
        github = api()
        state(github)
        filters = [args[0] for name, args in github.calls if name == "issues"]
        self.assertTrue(filters, "the fetch never listed issues")
        self.assertEqual(filters[0].get("state"), "all")

    def test_a_closed_issue_is_carried_for_the_done_bucket(self):  # DASH-008
        github = api([issue(7, [], state="closed")])
        found = state(github)["issues"]
        self.assertEqual([i["number"] for i in found], [7])
        self.assertTrue(found[0]["closed"])

    def test_each_issue_carries_its_milestone_number(self):  # DASH-001
        self.assertEqual(state()["issues"][0]["milestone_number"], 2)


class TestTheMilestoneList(unittest.TestCase):
    """DASH-010 — the data behind the first chart."""

    MILESTONES = [
        {"number": 2, "title": "v0.2", "state": "open", "open_issues": 1, "closed_issues": 0},
        {"number": 9, "title": "v0.9", "state": "open", "open_issues": 0, "closed_issues": 0},
        {"number": 1, "title": "v0.1", "state": "closed", "open_issues": 0, "closed_issues": 5},
    ]

    def test_open_milestones_are_carried(self):  # DASH-010
        github = api(milestones=self.MILESTONES)
        titles = [m["title"] for m in state(github)["milestones"]]
        self.assertIn("v0.2", titles)

    def test_an_empty_open_milestone_is_kept(self):  # DASH-010
        github = api(milestones=self.MILESTONES)
        titles = [m["title"] for m in state(github)["milestones"]]
        self.assertIn("v0.9", titles)

    def test_closed_milestones_are_left_out(self):  # DASH-010
        github = api(milestones=self.MILESTONES)
        titles = [m["title"] for m in state(github)["milestones"]]
        self.assertNotIn("v0.1", titles)


class TestFocusResolution(unittest.TestCase):
    """DASH-030, DASH-031, DASH-033, DASH-034 — override, marker, fallback."""

    MILESTONES = [
        {"number": 2, "title": "v0.2", "state": "open", "open_issues": 1, "closed_issues": 0},
        {"number": 9, "title": "v0.9", "state": "open", "open_issues": 1, "closed_issues": 0},
    ]

    def _api(self, body="", issues=None):
        return api(
            (issues if issues is not None else [issue(7, ["ready-for-work"])]) + [dashboard(body)],
            milestones=self.MILESTONES,
        )

    def test_the_marker_in_the_dashboard_body_decides(self):  # DASH-030
        github = self._api("<!-- pipeline-focus: v0.9 -->")
        self.assertEqual(state(github)["focus"]["title"], "v0.9")

    def test_the_cap_marker_is_read_too(self):  # DASH-030
        github = self._api("<!-- pipeline-cap: 5 -->")
        self.assertEqual(state(github)["cap"], 5)

    def test_an_override_beats_the_marker(self):  # DASH-031
        github = self._api("<!-- pipeline-focus: v0.9 -->")
        self.assertEqual(state(github, overrides={"focus": "v0.2"})["focus"]["title"], "v0.2")

    def test_an_override_naming_nothing_is_refused(self):  # DASH-034
        """Rather than stored.

        A mistyped focus renders a board where every section is empty, which
        is indistinguishable from a milestone whose work is finished.
        """
        github = self._api("<!-- pipeline-focus: v0.9 -->")
        result = state(github, overrides={"focus": "v9.9"})
        self.assertEqual(result["focus"]["title"], "v0.9")

    def test_with_no_marker_the_fallback_is_the_lowest_with_ready_work(self):  # DASH-033
        github = self._api("", issues=[issue(7, ["ready-for-work"], milestone="v0.9",
                                              milestone_number=9)])
        self.assertEqual(state(github)["focus"]["title"], "v0.9")

    def test_the_fallback_prefers_the_lowest_version(self):  # DASH-033
        github = self._api("", issues=[
            issue(7, ["ready-for-work"], milestone="v0.9", milestone_number=9),
            issue(8, ["ready-for-work"], milestone="v0.2", milestone_number=2),
        ])
        self.assertEqual(state(github)["focus"]["title"], "v0.2")

    def test_a_milestone_with_no_ready_work_is_not_the_fallback(self):  # DASH-033
        github = self._api("", issues=[issue(7, ["ai-triage"], milestone="v0.2",
                                              milestone_number=2),
                                       issue(8, ["ready-for-work"], milestone="v0.9",
                                             milestone_number=9)])
        self.assertEqual(state(github)["focus"]["title"], "v0.9")


if __name__ == "__main__":
    unittest.main()
